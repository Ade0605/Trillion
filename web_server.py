"""
Trillion — browser interface on localhost:7777
Run: python web_server.py
"""
import json
import threading
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from flask import Flask, Response, request, stream_with_context, send_from_directory
from trillion.agent import Agent
from trillion.tools.registry import build_registry
from trillion.memory import MemoryStore, register_memory_tools
from trillion import phone

app = Flask(__name__)

# One agent per session (keyed by session cookie); for simplicity, one global agent
_agent_lock = threading.Lock()
_agent: Agent | None = None


# Browser confirmation for gated actions. Only one confirmation is ever
# outstanding at a time (the turn blocks on it), so a single slot suffices.
_confirm_lock = threading.Lock()
_confirm_event: threading.Event | None = None
_confirm_result = False
CONFIRM_TIMEOUT = 120  # seconds; times out to a safe decline


def _web_confirm_waiter(name: str, inputs: dict) -> bool:
    """Block the turn until the browser answers /confirm (or we time out)."""
    global _confirm_event, _confirm_result
    ev = threading.Event()
    with _confirm_lock:
        _confirm_event = ev
        _confirm_result = False
    answered = ev.wait(timeout=CONFIRM_TIMEOUT)
    with _confirm_lock:
        result = _confirm_result
        _confirm_event = None
    return bool(answered and result)


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        with _agent_lock:
            if _agent is None:
                a = Agent()
                registry = build_registry()
                memory = MemoryStore()
                register_memory_tools(registry, memory)
                a.attach_tools(registry)
                a.attach_memory(memory)
                a.set_confirm_waiter(_web_confirm_waiter)
                try:  # mark this the live registry + hot-load approved agents
                    from trillion.factory.tool import wire_live
                    wire_live(registry)
                except Exception:
                    pass
                try:  # warm the calendar cache so the first ask isn't a ~5s CalDAV wait
                    from trillion import calendar_yahoo
                    if calendar_yahoo.configured():
                        calendar_yahoo.prewarm()
                except Exception:
                    pass
                try:
                    from trillion.heartbeat import Heartbeat
                    hb = Heartbeat()
                    hb.start()
                except Exception:
                    pass
                _agent = a
    return _agent


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Trillion</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#06060a;color:#e8e8ea;height:100vh;display:flex;flex-direction:column;overflow:hidden}
#orb-section{flex-shrink:0;display:flex;flex-direction:column;align-items:center;padding:20px 0 10px;position:relative}
#orb-canvas{display:block}
#orb-label{font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#2af5ff88;margin-top:6px}
#status-text{font-size:12px;color:#ffffff44;margin-top:2px;height:16px;text-align:center}
#voice-banner{font-size:11px;margin-top:8px;padding:4px 12px;border-radius:20px;max-width:520px;text-align:center;line-height:1.4;border:1px solid transparent}
#voice-banner.ok{color:#2af5ff;background:#2af5ff12;border-color:#2af5ff33}
#voice-banner.warn{color:#ffb84d;background:#ffb84d12;border-color:#ffb84d33}
#voice-banner.checking{color:#ffffff44}
#chat{flex:1;overflow-y:auto;padding:16px 24px;display:flex;flex-direction:column;gap:14px;scroll-behavior:smooth}
#chat::-webkit-scrollbar{width:4px}
#chat::-webkit-scrollbar-track{background:transparent}
#chat::-webkit-scrollbar-thumb{background:#2a2a3a;border-radius:2px}
.msg{max-width:680px;line-height:1.6;font-size:14px}
.msg.user{align-self:flex-end;background:#111128;border:1px solid #2a2a50;border-radius:14px 14px 3px 14px;padding:10px 16px;color:#c9d1f9}
.msg.assistant{align-self:flex-start;color:#e8e8ea;padding:0 2px;white-space:pre-wrap}
.msg.assistant .label{font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#2af5ff;margin-bottom:4px}
.cursor{display:inline-block;width:2px;height:.9em;background:#2af5ff;vertical-align:text-bottom;animation:blink .7s step-end infinite}
@keyframes blink{50%{opacity:0}}
footer{padding:12px 20px;border-top:1px solid #111128;display:flex;gap:8px;flex-shrink:0;background:#06060a}
#input{flex:1;background:#0d0d1a;border:1px solid #1e1e38;border-radius:10px;padding:10px 14px;color:#e8e8ea;font-size:14px;font-family:inherit;resize:none;outline:none;transition:border-color .15s;min-height:44px;max-height:120px}
#input:focus{border-color:#2af5ff44}
#input::placeholder{color:#333355}
.btn{background:none;border:1px solid #1e1e38;border-radius:10px;color:#555577;font-size:13px;padding:0 14px;height:44px;cursor:pointer;font-family:inherit;transition:all .15s;flex-shrink:0}
.btn:hover{border-color:#2af5ff44;color:#2af5ff}
#send{background:#2af5ff18;border-color:#2af5ff44;color:#2af5ff;padding:0 18px;font-weight:500}
#send:hover{background:#2af5ff28}
#send:disabled{background:none;border-color:#1e1e38;color:#333355;cursor:not-allowed}
#mic-btn.listening{border-color:#ff4466;color:#ff4466;background:#ff446618}
#tts-btn.active{border-color:#2af5ff44;color:#2af5ff}
</style>
</head>
<body>
<script>
(function(){
  try {
    const u = new URL(location.href);
    const q = u.searchParams.get('token');
    if (q){ localStorage.setItem('trillion_token', q); u.searchParams.delete('token'); history.replaceState({}, '', u.toString()); }
    const tk = localStorage.getItem('trillion_token');
    if (tk){ const _f = window.fetch; window.fetch = function(url, opt){ opt = opt || {}; opt.headers = Object.assign({}, opt.headers, { Authorization: 'Bearer ' + tk }); return _f(url, opt); }; }
  } catch(e){}
})();
</script>
<div id="orb-section">
  <canvas id="orb-canvas" width="220" height="220"></canvas>
  <div id="orb-label">Trillion</div>
  <div id="status-text">ready</div>
  <div id="voice-banner" title="Live ElevenLabs voice status">checking voice…</div>
</div>
<div id="chat"></div>
<footer>
  <textarea id="input" placeholder="Ask Trillion anything…" rows="1"></textarea>
  <button id="mic-btn" class="btn" title="Click to speak">🎤</button>
  <button id="tts-btn" class="btn active" title="Toggle voice">🔊</button>
  <button id="reset-btn" class="btn" title="Clear">↺</button>
  <button id="send" class="btn">Send</button>
</footer>
<script>
/* ── Orb animation ── */
const canvas = document.getElementById('orb-canvas');
const ctx = canvas.getContext('2d');
const W = canvas.width, H = canvas.height, CX = W/2, CY = H/2, R = 80;
let orbState = 'idle'; // idle | listening | speaking

const particles = Array.from({length: 55}, () => ({
  angle: Math.random() * Math.PI * 2,
  radius: Math.random() * R * 0.85,
  speed: (Math.random() - 0.5) * 0.008,
  size: Math.random() * 2.2 + 0.4,
  alpha: Math.random() * 0.7 + 0.2,
  drift: (Math.random() - 0.5) * 0.003,
}));

let t = 0;
function drawOrb() {
  ctx.clearRect(0, 0, W, H);
  t += 0.016;

  const isListening = orbState === 'listening';
  const isSpeaking = orbState === 'speaking';

  // outer glow rings
  const ringAlpha = isSpeaking ? 0.18 + 0.12 * Math.sin(t * 4) : isListening ? 0.22 : 0.08 + 0.04 * Math.sin(t);
  for (let i = 3; i >= 1; i--) {
    ctx.beginPath();
    ctx.arc(CX, CY, R + i * 14, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(42,245,255,${ringAlpha / i})`;
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  // main orb fill (deep navy)
  const grad = ctx.createRadialGradient(CX - 18, CY - 18, 4, CX, CY, R);
  grad.addColorStop(0, '#0a1a3a');
  grad.addColorStop(1, '#020510');
  ctx.beginPath();
  ctx.arc(CX, CY, R, 0, Math.PI * 2);
  ctx.fillStyle = grad;
  ctx.fill();

  // orb rim
  const rimAlpha = isSpeaking ? 0.9 : isListening ? 0.85 : 0.5 + 0.15 * Math.sin(t * 0.8);
  ctx.beginPath();
  ctx.arc(CX, CY, R, 0, Math.PI * 2);
  ctx.strokeStyle = `rgba(42,245,255,${rimAlpha})`;
  ctx.lineWidth = isSpeaking ? 2.5 : 1.8;
  ctx.stroke();

  // particles
  particles.forEach(p => {
    p.angle += p.speed * (isSpeaking ? 2.5 : isListening ? 1.8 : 1);
    p.drift += (Math.random() - 0.5) * 0.0002;
    const px = CX + Math.cos(p.angle) * p.radius;
    const py = CY + Math.sin(p.angle) * p.radius;
    const a = isSpeaking ? p.alpha * (0.7 + 0.3 * Math.sin(t * 6 + p.angle)) : p.alpha * 0.6;
    ctx.beginPath();
    ctx.arc(px, py, p.size, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(42,245,255,${a})`;
    ctx.fill();
  });

  // waveform bars (speaking & listening)
  if (isSpeaking || isListening) {
    const bars = 12, bw = 2.5, gap = 5;
    const totalW = bars * (bw + gap) - gap;
    const startX = CX - totalW / 2;
    for (let i = 0; i < bars; i++) {
      const phase = t * (isSpeaking ? 7 : 4) + i * 0.55;
      const h = isSpeaking
        ? 6 + 22 * Math.abs(Math.sin(phase))
        : 4 + 10 * Math.abs(Math.sin(phase));
      const bx = startX + i * (bw + gap);
      ctx.fillStyle = `rgba(42,245,255,${isSpeaking ? 0.85 : 0.5})`;
      ctx.fillRect(bx, CY - h / 2, bw, h);
    }
  } else {
    // idle: subtle pulse dot
    const pr = 3 + 1.5 * Math.sin(t * 1.2);
    ctx.beginPath();
    ctx.arc(CX, CY, pr, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(42,245,255,0.35)';
    ctx.fill();
  }

  requestAnimationFrame(drawOrb);
}
drawOrb();

function setOrbState(s) {
  orbState = s;
  document.getElementById('status-text').textContent =
    s === 'listening' ? 'listening…' : s === 'speaking' ? 'speaking…' : 'ready';
}

/* ── Chat ── */
const chat = document.getElementById('chat');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send');
const resetBtn = document.getElementById('reset-btn');
const ttsBtn = document.getElementById('tts-btn');
const micBtn = document.getElementById('mic-btn');
let ttsEnabled = true, currentAudio = null;
let audioQueue = [], isPlayingQueue = false;
let turnCount = 0;

ttsBtn.addEventListener('click', () => {
  ttsEnabled = !ttsEnabled;
  ttsBtn.classList.toggle('active', ttsEnabled);
  ttsBtn.textContent = ttsEnabled ? '🔊' : '🔇';
  if (!ttsEnabled) { stopAudio(); window.speechSynthesis && window.speechSynthesis.cancel(); }
});

function stopAudio() {
  audioQueue = [];
  isPlayingQueue = false;
  if (currentAudio) { currentAudio.pause(); currentAudio = null; }
  if ('speechSynthesis' in window) window.speechSynthesis.cancel();
  setOrbState('idle');
}

function playUrl(url) {
  return new Promise(resolve => {
    currentAudio = new Audio(url);
    currentAudio.onended = () => { URL.revokeObjectURL(url); currentAudio = null; resolve(); };
    currentAudio.onerror = () => { URL.revokeObjectURL(url); resolve(); };
    currentAudio.play().catch(resolve);
  });
}

// Browser speech fallback — used per-sentence whenever ElevenLabs isn't available
let _femaleVoice = null;
function pickFemaleVoice() {
  if (!('speechSynthesis' in window)) return null;
  const voices = window.speechSynthesis.getVoices();
  const prefer = ['zira','samantha','female','aria','jenny','hazel','susan','linda','eva'];
  for (const name of prefer) {
    const v = voices.find(v => v.name.toLowerCase().includes(name));
    if (v) return v;
  }
  return voices.find(v => v.lang && v.lang.startsWith('en')) || voices[0] || null;
}
if ('speechSynthesis' in window) {
  _femaleVoice = pickFemaleVoice();
  window.speechSynthesis.onvoiceschanged = () => { _femaleVoice = pickFemaleVoice(); };
}
function speakBrowser(text) {
  return new Promise(resolve => {
    if (!('speechSynthesis' in window)) return resolve();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1.05; u.pitch = 1.05;
    if (_femaleVoice) u.voice = _femaleVoice;
    u.onend = resolve; u.onerror = resolve;
    window.speechSynthesis.speak(u);
  });
}

async function drainQueue() {
  if (isPlayingQueue) return;
  isPlayingQueue = true;
  setOrbState('speaking');
  while (audioQueue.length > 0) {
    const item = await audioQueue.shift();
    if (!isPlayingQueue) break;
    if (item && item.url) await playUrl(item.url);
    else if (item && item.fallback) await speakBrowser(item.fallback);
  }
  isPlayingQueue = false;
  setOrbState('idle');
}

// Returns {url} for ElevenLabs audio, or {fallback} to speak with the browser voice
function fetchAudioItem(sentence) {
  return fetch('/speak', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text: sentence})})
    .then(r => r.ok ? r.blob() : null)
    .then(blob => blob ? {url: URL.createObjectURL(blob)} : {fallback: sentence})
    .catch(() => ({fallback: sentence}));
}

function enqueueSentence(sentence) {
  if (!ttsEnabled || !sentence.trim()) return;
  audioQueue.push(fetchAudioItem(sentence));
  drainQueue();
}

// Sign-off detection is handled server-side (trillion/turn_taking.py): the /chat
// stream returns {signoff:true} when Trillion should stay silent — no model call.

function addMsg(role, text='') {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  if (role === 'assistant') {
    const label = document.createElement('div');
    label.className = 'label'; label.textContent = 'Trillion';
    const content = document.createElement('div');
    content.className = 'text'; content.textContent = text;
    const cursor = document.createElement('span');
    cursor.className = 'cursor'; cursor.id = 'cursor';
    div.appendChild(label); div.appendChild(content); div.appendChild(cursor);
  } else { div.textContent = text; }
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

// Splits accumulated text into complete sentences + leftover fragment
function extractSentences(text) {
  const sentences = [];
  // Match ending in . ! ? followed by space/newline, or end of string after punctuation
  const re = /[^.!?]*[.!?]+(?:\s+|$)/g;
  let match, last = 0;
  while ((match = re.exec(text)) !== null) {
    sentences.push(match[0].trim());
    last = re.lastIndex;
  }
  return { sentences, remainder: text.slice(last) };
}

async function send() {
  const text = input.value.trim();
  if (!text) return;

  input.value = ''; input.style.height = 'auto';
  sendBtn.disabled = true;
  setOrbState('idle');
  turnCount++;
  addMsg('user', text);
  const aDiv = addMsg('assistant');
  const contentEl = aDiv.querySelector('.text');

  let sseBuf = '', ttsAccum = '', signoff = false;

  try {
    const resp = await fetch('/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message:text})});
    if (resp.status === 401) {
      const t = (window.prompt('Not signed in — this browser is missing its access token.\\nPaste your Trillion token to sign in:') || '').trim();
      if (t) { localStorage.setItem('trillion_token', t); location.reload(); return; }
      contentEl.textContent = 'Not signed in — missing access token. Open Trillion with your ?token= link.';
      sendBtn.disabled = false; return;
    }
    if (!resp.ok) { contentEl.textContent = 'Server error (' + resp.status + ').'; sendBtn.disabled = false; return; }
    const reader = resp.body.getReader();
    const dec = new TextDecoder();

    outer:
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      sseBuf += dec.decode(value, {stream:true});
      const lines = sseBuf.split('\n'); sseBuf = lines.pop();
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const p = line.slice(6);
        if (p === '[DONE]') break outer;
        try {
          const obj = JSON.parse(p);
          if (obj.signoff) { signoff = true; break outer; }
          if (obj.confirm) {
            const c = obj.confirm;
            const detail = Object.entries(c.input || {}).map(([k, v]) => `${k}: ${v}`).join('\n');
            const ok = window.confirm(`Trillion wants to run "${c.name}"` + (detail ? `\n\n${detail}` : '') + `\n\nAllow this action?`);
            fetch('/confirm', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({approved: ok})});
            continue;
          }
          if (obj.chunk == null) continue;   // tool events etc. — not shown in this view
          contentEl.textContent += obj.chunk;
          chat.scrollTop = chat.scrollHeight;
          ttsAccum += obj.chunk;
          // Dispatch complete sentences to TTS immediately as they arrive
          const {sentences, remainder} = extractSentences(ttsAccum);
          for (const s of sentences) enqueueSentence(s);
          ttsAccum = remainder;
        } catch {}
      }
    }
    // Flush any trailing fragment (reply ended without terminal punctuation)
    if (!signoff && ttsAccum.trim()) enqueueSentence(ttsAccum);
  } catch(e) { contentEl.textContent = 'Connection error — is the server running?'; }

  if (signoff) {
    // Trillion recognized a goodbye — let the conversation end, no last word.
    aDiv.remove();
  } else {
    document.getElementById('cursor')?.remove();
  }
  sendBtn.disabled = false;
  input.focus();
}

sendBtn.addEventListener('click', send);
input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } });
input.addEventListener('input', () => { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 120) + 'px'; });
resetBtn.addEventListener('click', async () => {
  await fetch('/reset', {method:'POST'});
  chat.innerHTML = '';
  addMsg('assistant', 'Conversation cleared. What can I help you with?');
});

/* ── Voice input ── */
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
if (!SR) { micBtn.style.opacity = '.3'; micBtn.style.cursor = 'not-allowed'; }
else {
  const rec = new SR();
  rec.continuous = false; rec.interimResults = true; rec.lang = 'en-US';
  let final = '';
  rec.onstart = () => { micBtn.classList.add('listening'); micBtn.textContent = '🔴'; final = ''; input.placeholder = 'Listening…'; setOrbState('listening'); };
  rec.onresult = e => {
    let interim = ''; final = '';
    for (const r of e.results) { if (r.isFinal) final += r[0].transcript; else interim += r[0].transcript; }
    input.value = final || interim;
    input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  };
  rec.onend = () => {
    micBtn.classList.remove('listening'); micBtn.textContent = '🎤';
    input.placeholder = 'Ask Trillion anything…'; setOrbState('idle');
    if (final.trim()) send();
  };
  rec.onerror = e => {
    micBtn.classList.remove('listening'); micBtn.textContent = '🎤';
    input.placeholder = 'Ask Trillion anything…'; setOrbState('idle');
  };
  micBtn.addEventListener('click', () => {
    if (micBtn.classList.contains('listening')) { rec.stop(); }
    else { stopAudio(); window.speechSynthesis && window.speechSynthesis.cancel(); input.value = ''; rec.start(); }
  });
}

async function checkVoice() {
  const banner = document.getElementById('voice-banner');
  banner.className = 'checking'; banner.textContent = 'checking voice…';
  try {
    const r = await fetch('/voice-status');
    if (r.status === 401) { banner.className = 'warn'; banner.textContent = '⚠ Not signed in — send a message and paste your token to enable voice.'; return; }
    if (r.status === 429) { banner.className = 'warn'; banner.textContent = '⚠ Rate-limited — wait a minute, then reload.'; return; }
    if (!r.ok) { banner.className = 'warn'; banner.textContent = '⚠ Voice check failed (HTTP ' + r.status + ').'; return; }
    const s = await r.json();
    if (s.ok) { banner.className = 'ok'; banner.textContent = '🔊 ' + s.reason; }
    else { banner.className = 'warn'; banner.textContent = '⚠ ' + s.reason; }
  } catch(e) {
    banner.className = 'warn'; banner.textContent = '⚠ Could not reach server for voice check.';
  }
}

window.addEventListener('load', () => {
  addMsg('assistant', "Hello sir — I'm Trillion. Wide awake and ready. What do you need?");
  checkVoice();
  enqueueSentence("Hello sir. I'm Trillion. Wide awake and ready.");
});
</script>
</body>
</html>"""


from flask import Response as _Response
from trillion.security import http_guard

# Page shells are served without a token so the browser can bootstrap; the JS
# then attaches the token to every API call. CSP reports are unauthenticated by
# nature. Everything else is guarded.
_OPEN_ENDPOINTS = {"index", "face", "csp_report", "phone_shell", "manifest", "service_worker", "phone_icon", "design_preview", "factory_page", "cosmos", "cosmos_agents"}

# CSP shipped report-only first (see security/audit_shield.CSP_MODE). Widen only
# by what actually gets blocked, then flip to enforcing.
_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "media-src 'self' blob: data:; "
    "connect-src 'self'; "
    "font-src 'self' data:; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'; "
    "report-uri /api/security/csp-report"
)


@app.before_request
def _auth_guard():
    """CSRF origin gate (always on) + bearer token + per-IP rate-limit (only when
    TRILLION_TOKEN is set)."""
    # CSRF: reject cross-site state-changing requests. CSP reports are exempt
    # (browsers may send them without a matching Origin).
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.endpoint != "csp_report":
        if not http_guard.check_origin(request.headers, request.host):
            return _Response("Bad origin", status=403)

    if not http_guard.token_required():
        return None
    if request.endpoint in _OPEN_ENDPOINTS and request.method == "GET":
        return None
    ip = http_guard.client_ip(request.headers, request.remote_addr)
    allowed, retry = http_guard.check_rate(ip)
    if not allowed:
        return _Response("Too many attempts. Try again later.", status=429,
                         headers={"Retry-After": str(int(retry))})
    # Token via header (fetch), X-Auth-Token, or ?token= (the only path the
    # <audio> element and a WebSocket upgrade can use).
    candidate = (request.headers.get("Authorization")
                 or request.headers.get("X-Auth-Token")
                 or request.args.get("token"))
    if not http_guard.check_token(candidate):
        # Only a WRONG token counts toward the brute-force lockout. A request
        # with NO token is just a page that hasn't been handed the token yet
        # (the UI auto-fires /voice-status + greeting TTS on load) — counting
        # those would let a token-less browser lock out its own IP, which via
        # `tailscale serve` (proxies as loopback) is shared with the phone.
        if candidate and candidate.strip():
            http_guard.record_fail(ip)
        return _Response("Unauthorized", status=401)
    return None  # authenticated — no counter change on success


@app.after_request
def _security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Permissions-Policy",
        "microphone=(self), autoplay=(self), camera=(), geolocation=(), interest-cohort=()")
    from trillion.security.audit_shield import CSP_MODE
    header = "Content-Security-Policy" if CSP_MODE == "enforcing" else "Content-Security-Policy-Report-Only"
    resp.headers.setdefault(header, _CSP)
    return resp


@app.get("/")
def index():
    return HTML, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.get("/face")
def face():
    """Full-screen cosmic interface (built tier by tier in static/face.html)."""
    path = Path(__file__).parent / "static" / "face.html"
    return path.read_text(encoding="utf-8"), 200, {"Content-Type": "text/html; charset=utf-8"}


@app.get("/design/<project>/preview/", defaults={"subpath": ""})
@app.get("/design/<project>/preview/<path:subpath>")
def design_preview(project, subpath):
    """Serve a design agent's static-export mockups (Next.js `out/`).
    trailingSlash export means directory routes resolve to <path>/index.html."""
    from trillion.design import docs as ddocs
    if not ddocs.valid_slug(project):
        return "not found", 404
    out = ddocs.resolve_project_root(project) / ".prism" / "preview" / "out"
    if not out.exists():
        return "No build output for this project yet — run design_screen first.", 404
    target = subpath or "index.html"
    if target.endswith("/"):
        target += "index.html"
    elif "." not in target.rsplit("/", 1)[-1]:
        target += "/index.html"   # directory route → index.html
    try:
        return send_from_directory(str(out), target)
    except Exception:
        return "not found", 404


@app.post("/chat")
def chat():
    data = request.get_json(force=True)
    user_message = data.get("message", "").strip()
    if not user_message:
        return Response("data: [DONE]\n\n", mimetype="text/event-stream")

    agent = get_agent()

    # Sign-off check runs before any model call: a goodbye costs zero tokens and
    # Trillion stays silent instead of grabbing the last word. Only applies once
    # the assistant has actually been part of the conversation.
    from trillion.turn_taking import is_signoff
    is_first_turn = len(agent.conversation) == 0
    if is_signoff(user_message, is_first_turn=is_first_turn):
        def signoff_gen():
            yield f"data: {json.dumps({'signoff': True})}\n\n"
            yield "data: [DONE]\n\n"
        return Response(signoff_gen(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    def generate():
        reply_parts = []
        try:
            for item in agent.run_turn(user_message):
                if isinstance(item, dict) and "tool_start" in item:
                    yield f"data: {json.dumps({'tool': item['tool_start']})}\n\n"
                elif isinstance(item, dict) and "confirm_request" in item:
                    yield f"data: {json.dumps({'confirm': item['confirm_request']})}\n\n"
                else:
                    reply_parts.append(item)
                    yield f"data: {json.dumps({'chunk': item})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'chunk': f'[Error: {e}]'})}\n\n"
        # Stash the full reply so the phone's <audio> can fetch it by turn_id.
        reply = "".join(reply_parts).strip()
        if reply:
            yield f"data: {json.dumps({'turn_id': phone.record_turn_text(reply)})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/reset")
def reset():
    agent = get_agent()
    agent.reset()
    return {"ok": True}


@app.get("/factory/pending")
def factory_pending():
    """Page-load hydration: all tasks awaiting approval (with their manifests).
    Without this, work finished while the page was closed is invisible."""
    from trillion.factory import store as fstore
    return {"pending": fstore.list_pending()}


@app.post("/factory/approve")
def factory_approve():
    from trillion.factory import approval
    data = request.get_json(force=True)
    try:
        return approval.handle_approve(data.get("task_id", ""))
    except Exception as e:
        return {"error": str(e)}, 400


@app.post("/factory/reject")
def factory_reject():
    from trillion.factory import approval
    data = request.get_json(force=True)
    try:
        return approval.handle_reject(data.get("task_id", ""), data.get("feedback", ""))
    except Exception as e:
        return {"error": str(e)}, 400


@app.get("/factory")
def factory_page():
    path = Path(__file__).parent / "static" / "factory.html"
    return path.read_text(encoding="utf-8"), 200, {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"}


@app.post("/api/security/csp-report")
def csp_report():
    """Log CSP violations during the report-only window."""
    try:
        from trillion import audit
        audit.log("csp_violation", report=request.get_data(as_text=True)[:2000])
    except Exception:
        pass
    return "", 204


@app.get("/api/security/status")
def security_status():
    from trillion.security.audit_shield import compute_status
    return compute_status()


@app.post("/api/security/audit")
def security_audit():
    from trillion.security.audit_shield import compute_status
    return compute_status()


@app.get("/api/security/cve-status")
def cve_status():
    from trillion.security.cve_scan import latest
    return latest() or {"cve_count": None, "error_message": "never run"}


@app.post("/api/security/cve-scan")
def cve_scan_run():
    from trillion.security.cve_scan import run_scan
    return run_scan()


@app.post("/confirm")
def confirm():
    """Answer a pending gated-action confirmation from the browser."""
    global _confirm_result
    data = request.get_json(force=True)
    with _confirm_lock:
        _confirm_result = bool(data.get("approved"))
        ev = _confirm_event
    if ev is not None:
        ev.set()
    return {"ok": True}


@app.get("/voice-status")
def voice_status():
    """Real ElevenLabs check so the UI can show ground truth about the voice."""
    import os
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not key:
        return {"ok": False, "reason": "No ELEVENLABS_API_KEY in .env — using browser fallback voice."}

    try:
        import yaml
        with open(Path(__file__).parent / "config.yml") as f:
            cfg = yaml.safe_load(f)
        voice_id = cfg.get("elevenlabs_voice_id", "EXAVITQu4vr4xnSDxMaL")
        model_id = cfg.get("elevenlabs_model", "eleven_turbo_v2_5")

        import urllib.request, urllib.error, json as _json
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            data=_json.dumps({"text": "ok", "model_id": model_id}).encode(),
            headers={"xi-api-key": key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                r.read(64)  # touch the stream to confirm audio flows
            return {"ok": True, "voice_id": voice_id, "reason": "ElevenLabs voice connected."}
        except urllib.error.HTTPError as he:
            body = he.read().decode(errors="replace")
            detail = body
            try:
                detail = _json.loads(body).get("detail", {}).get("message", body)
            except Exception:
                pass
            hint = ""
            if he.code == 402:
                hint = " This voice is paid-only — switch to a premade voice or upgrade the plan."
            elif he.code == 401:
                hint = " Key invalid or missing text_to_speech permission."
            return {"ok": False, "reason": f"ElevenLabs {he.code}: {detail}{hint} Using browser fallback."}
    except Exception as e:
        return {"ok": False, "reason": f"Voice check failed: {e}. Using browser fallback."}


def _stream_elevenlabs(text: str):
    """Shared ElevenLabs MP3 streamer. Returns a Flask Response or an error tuple."""
    import os
    text = (text or "").strip()
    if not text:
        return "", 204
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not key:
        return {"error": "ELEVENLABS_API_KEY not set"}, 503
    try:
        import elevenlabs
        import yaml
        with open(Path(__file__).parent / "config.yml") as f:
            cfg = yaml.safe_load(f)
        voice_id = cfg.get("elevenlabs_voice_id", "EXAVITQu4vr4xnSDxMaL")
        model_id = cfg.get("elevenlabs_model", "eleven_turbo_v2_5")
        client = elevenlabs.ElevenLabs(api_key=key)
        audio_stream = client.text_to_speech.stream(
            text=text, voice_id=voice_id, model_id=model_id, output_format="mp3_44100_128",
        )

        def generate():
            for chunk in audio_stream:
                if chunk:
                    yield chunk

        # iOS Safari fetches the audio source twice (metadata probe + play); MP3
        # is streamed fresh each time, and the turn store is TTL- not read-evicted.
        return Response(generate(), mimetype="audio/mpeg",
                        headers={"Cache-Control": "no-cache", "Accept-Ranges": "none"})
    except Exception as e:
        return {"error": str(e)}, 500


@app.post("/speak")
def speak():
    """Stream ElevenLabs TTS for text posted directly (desktop UIs)."""
    data = request.get_json(force=True)
    return _stream_elevenlabs(data.get("text", ""))


@app.get("/api/tts/<turn_id>")
def tts_by_turn(turn_id):
    """Non-evicting TTS lookup for the phone PWA's <audio> element (which GETs
    twice). Text is stored under a turn_id by /chat and pruned by TTL, never on
    read — so the second GET still finds it."""
    text = phone.get_turn_text(turn_id)
    if text is None:
        return {"error": "turn expired or not found"}, 404
    return _stream_elevenlabs(text)


@app.post("/transcribe")
def transcribe():
    """One-shot STT for the phone (iOS has no Web Speech API). Accepts an audio
    blob, runs Deepgram, returns the transcript."""
    audio = request.get_data()
    if not audio:
        return {"error": "no audio"}, 400
    mime = request.headers.get("Content-Type", "audio/webm").split(";")[0]
    try:
        from trillion.voice import stt
        text = stt.transcribe(audio, mime_type=mime)
        if text.startswith("[STT error]"):
            return {"error": text}, 502
        return {"text": text}
    except Exception as e:
        return {"error": str(e)}, 500


@app.get("/phone")
def phone_shell():
    """The installable voice-first PWA shell."""
    html = (Path(__file__).parent / "static" / "phone.html").read_text(encoding="utf-8")
    return html, 200, {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"}


@app.get("/cosmos")
def cosmos():
    """The living cosmic interface — full-screen 3D orb + sub-agent constellation."""
    html = (Path(__file__).parent / "static" / "cosmos.html").read_text(encoding="utf-8")
    return html, 200, {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"}


# Non-sensitive display list for the constellation (id/name/specialty/color only —
# no prompts, tools, or secrets). Open so the scene populates on a cold, token-less
# load; the four seeds are Trillion's own capabilities, then live Factory agents.
_COSMOS_SEEDS = [
    {"id": "scout",     "name": "Scout",     "specialty": "Web research & lookups",   "color": "#4de3ff"},
    {"id": "scribe",    "name": "Scribe",    "specialty": "Drafts messages & replies", "color": "#b98cff"},
    {"id": "librarian", "name": "Librarian", "specialty": "Notes & document recall",   "color": "#4dffa0"},
    {"id": "scheduler", "name": "Scheduler", "specialty": "Reminders & timing",        "color": "#ff7bd5"},
]
_FACTORY_PALETTE = ["#5ad1ff", "#c48bff", "#5affc0", "#ff9ad2", "#8fb4ff", "#7affe0"]


@app.get("/cosmos/agents")
def cosmos_agents():
    """Seed specialists + any live Factory agents, display-only."""
    agents = list(_COSMOS_SEEDS)
    try:
        from trillion.factory import store as fstore
        for i, row in enumerate(fstore.list_active_agents()):
            slug = row.get("slug") or row.get("id") or ""
            if not slug:
                continue
            agents.append({
                "id": f"factory:{slug}",
                "name": row.get("name") or slug.replace("-", " ").title(),
                "specialty": (row.get("specialty") or "Spawned specialist")[:60],
                "color": _FACTORY_PALETTE[i % len(_FACTORY_PALETTE)],
            })
    except Exception:
        pass
    return {"agents": agents}


@app.get("/manifest.webmanifest")
def manifest():
    body = (Path(__file__).parent / "static" / "manifest.webmanifest").read_text(encoding="utf-8")
    return body, 200, {"Content-Type": "application/manifest+json"}


@app.get("/sw.js")
def service_worker():
    body = (Path(__file__).parent / "static" / "phone-sw.js").read_text(encoding="utf-8")
    return body, 200, {"Content-Type": "application/javascript", "Cache-Control": "no-store"}


@app.get("/phone-icon.svg")
def phone_icon():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">'
        '<rect width="512" height="512" fill="#06060a"/>'
        '<circle cx="256" cy="256" r="150" fill="none" stroke="#2af5ff" stroke-width="6" opacity="0.9"/>'
        '<circle cx="256" cy="256" r="150" fill="#2af5ff" opacity="0.10"/>'
        '<circle cx="256" cy="256" r="90" fill="#2af5ff" opacity="0.18"/>'
        '</svg>'
    )
    return svg, 200, {"Content-Type": "image/svg+xml", "Cache-Control": "no-store"}


if __name__ == "__main__":
    import os

    token_set = http_guard.token_required()
    host = os.environ.get("TRILLION_BIND", "").strip()
    if not host:
        # Default: localhost-only. Expose publicly only when a token is set.
        host = "0.0.0.0" if token_set else "127.0.0.1"

    public = host not in ("127.0.0.1", "localhost", "::1")
    if public and not token_set:
        raise SystemExit(
            f"Refusing to bind {host} with no TRILLION_TOKEN set — that would expose "
            f"an unauthenticated agent to the network. Set TRILLION_TOKEN in .env to "
            f"expose Trillion, or leave it unset to bind localhost only."
        )

    port = int(os.environ.get("TRILLION_PORT", "7777"))
    shown = "localhost" if host in ("127.0.0.1", "localhost") else host
    print(f"\n  Trillion is running at http://{shown}:{port}")
    print(f"  auth: {'bearer token required' if token_set else 'localhost-only (no token)'}\n")
    app.run(host=host, port=port, debug=False, threaded=True)
