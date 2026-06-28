"""
Trillion — voice entry point (push-to-talk).
Run: python main_voice.py

The brain (agent.py) is identical to the text REPL — voice is purely an adapter
at the edges. If something goes wrong with audio, run main.py to debug the brain.
"""
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from trillion.agent import Agent
from trillion.tools.registry import build_registry
from trillion.voice import tts

BANNER = """
╔══════════════════════════════════════╗
║  Trillion — Voice Mode               ║
║  Hold SPACE to speak, release to send║
║  Ctrl-C to quit                      ║
╚══════════════════════════════════════╝
"""


def main() -> None:
    print(BANNER)

    agent = Agent()
    registry = build_registry()
    agent.attach_tools(registry)
    print(f"[tools] {len(registry)} tool(s) loaded.")

    try:
        from trillion.memory import MemoryStore, register_memory_tools
        memory = MemoryStore()
        agent.attach_memory(memory)
        register_memory_tools(registry, memory)
        print("[memory] Memory loaded.")
    except ImportError:
        pass

    try:
        from trillion.heartbeat import Heartbeat
        heartbeat = Heartbeat()
        heartbeat.start()
        print("[heartbeat] Running in background.")
    except ImportError:
        pass

    print()

    def on_transcript(text: str) -> None:
        print("Trillion > ", end="", flush=True)
        reply_parts: list[str] = []

        for chunk in agent.run_turn(text):
            print(chunk, end="", flush=True)
            reply_parts.append(chunk)

        print("\n")
        full_reply = "".join(reply_parts)
        if full_reply.strip():
            tts.speak(full_reply)

    from trillion.voice.push_to_talk import run_push_to_talk
    run_push_to_talk(on_transcript)


if __name__ == "__main__":
    main()
