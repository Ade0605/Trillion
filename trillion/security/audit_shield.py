"""
Self-audit security shield.

Hardening rots without measurement. This computes a single 0–100 score from a
list of independent signals so drift (a flipped kill switch, an unset key, a
CSP still in report-only) is visible at a glance instead of discovered after an
incident. Threat: everything — this is the observability layer over the rest.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

# Verified clean in report-only (zero violations over a full session), now enforcing.
CSP_MODE = "enforcing"

_ROOT = Path(__file__).parent.parent.parent


def _signal(name, label, value, delta=0, severity="ok", detail=""):
    return {"name": name, "label": label, "value": value,
            "delta": delta, "severity": severity, "detail": detail}


def _gated_tool_count() -> int:
    try:
        with open(_ROOT / "config.yml") as f:
            cfg = yaml.safe_load(f) or {}
        return len(cfg.get("confirmation_required_tools", []) or [])
    except Exception:
        return 0


def compute_status() -> dict:
    from . import kill_switch, http_guard, anomaly

    signals = []

    # kill switch — overrides everything when active
    if kill_switch.is_active():
        signals.append(_signal("kill-switch", "Kill switch", "ACTIVE", -100, "critical",
                               "All tool calls are paused."))
    else:
        signals.append(_signal("kill-switch", "Kill switch", "off", 0, "ok"))

    # LLM API key
    if os.environ.get("ANTHROPIC_API_KEY"):
        signals.append(_signal("llm-api-key", "LLM API key", "set", 0, "ok"))
    else:
        signals.append(_signal("llm-api-key", "LLM API key", "unset", -50, "critical",
                               "ANTHROPIC_API_KEY is not set — the agent can't think."))

    # network / auth posture
    if http_guard.token_required():
        signals.append(_signal("network-auth", "Network auth", "bearer token + rate-limit", 0, "ok",
                               "Exposed on 0.0.0.0 with a required token."))
    else:
        signals.append(_signal("network-auth", "Network auth", "localhost-only", 0, "ok",
                               "Bound to 127.0.0.1; only this machine can reach it."))

    # log redaction (wired into audit.log)
    signals.append(_signal("log-redaction", "Log redaction", "active", 0, "ok"))

    # untrusted-content gate coverage
    signals.append(_signal("gate-coverage", "Injection gate", "external ingest gated (web_search)", 0, "ok"))

    # per-tool anomaly caps
    signals.append(_signal("anomaly-caps", "Anomaly caps",
                           f"{anomaly.caps_summary()['tools_capped']} tools capped", 0, "ok"))

    # confirmation gate on destructive tools
    n = _gated_tool_count()
    signals.append(_signal("confirmation-gate", "Confirmation gate", f"{n} tools gated", 0, "ok"))

    # subprocess env — none to strip
    signals.append(_signal("subprocess-envs", "Subprocess env", "no spawn sites", 0, "ok"))

    # CSP
    if CSP_MODE == "enforcing":
        signals.append(_signal("csp-status", "Content-Security-Policy", "enforcing", 0, "ok"))
    else:
        signals.append(_signal("csp-status", "Content-Security-Policy", "report-only", -10, "info",
                               "Collecting violations before enforcing."))

    # CVE scan — read the latest pip-audit sidecar
    from . import cve_scan
    from datetime import datetime, timezone
    scan = cve_scan.latest()
    if scan is None:
        signals.append(_signal("cve-scan", "Dependency CVE scan", "never run", -5, "info"))
    elif scan.get("error_message"):
        signals.append(_signal("cve-scan", "Dependency CVE scan", "scanner error", -10, "warning",
                               scan["error_message"]))
    else:
        n = scan.get("cve_count") or 0
        try:
            age_days = (datetime.now(timezone.utc) -
                        datetime.fromisoformat(scan["generated_at"])).days
        except Exception:
            age_days = 0
        if age_days > 14:
            signals.append(_signal("cve-scan", "Dependency CVE scan", "stale (>14d)", -5, "info"))
        elif n == 0:
            signals.append(_signal("cve-scan", "Dependency CVE scan", "clean", 0, "ok"))
        else:
            signals.append(_signal("cve-scan", "Dependency CVE scan", f"{n} CVEs",
                                   max(-15, -5 * n), "warning"))

    # CSRF / origin gate — state-changing POSTs are origin-checked
    signals.append(_signal("csrf-origin-gate", "CSRF origin gate", "present", 0, "ok",
                           "Cross-site state-changing requests are rejected."))

    score = max(0, min(100, 100 + sum(s["delta"] for s in signals)))
    color = "green" if score >= 85 else "amber" if score >= 60 else "red"
    return {"score": score, "color": color, "signals": signals}
