"""
Trillion — text REPL entry point.
Run: python main.py
"""
import os
import sys
from pathlib import Path

# Load .env before importing anything that needs keys
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from trillion.agent import Agent

BANNER = """
╔══════════════════════════════════╗
║  Trillion — your AI assistant    ║
║  Type 'exit' or Ctrl-C to quit  ║
╚══════════════════════════════════╝
"""

COMMANDS = {"/reset", "/exit", "/quit"}


def main() -> None:
    print(BANNER)

    agent = Agent()

    # Tier 2: attach tool registry when available
    try:
        from trillion.tools.registry import build_registry
        registry = build_registry()
        agent.attach_tools(registry)
        print(f"[tools] {len(registry)} tool(s) loaded.\n")
    except ImportError:
        pass

    # Tier 4: attach memory when available
    try:
        from trillion.memory import MemoryStore, register_memory_tools
        memory = MemoryStore()
        agent.attach_memory(memory)
        if registry:
            register_memory_tools(registry, memory)
    except ImportError:
        pass

    # Tier 5: start heartbeat when available
    try:
        from trillion.heartbeat import Heartbeat
        heartbeat = Heartbeat()
        heartbeat.start()
    except ImportError:
        heartbeat = None

    print("Trillion is ready. Say hello.\n")

    while True:
        try:
            user_input = input("You > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break

        if not user_input:
            continue

        # Built-in REPL commands
        if user_input.lower() in ("exit", "quit", "/exit", "/quit"):
            try:
                from trillion.audit import session_cost_summary
                print(f"[{session_cost_summary()}]")
            except Exception:
                pass
            print("Goodbye.")
            break

        if user_input.lower() == "/reset":
            agent.reset()
            print("[Trillion] Conversation cleared.\n")
            continue

        # Tier 5 commands
        if heartbeat:
            if user_input.lower() == "/notices":
                _show_notices()
                continue
            if user_input.lower() == "/heartbeat stop":
                heartbeat.stop()
                print("[Trillion] Heartbeat paused. I'll only respond when you talk to me.")
                continue
            if user_input.lower() == "/heartbeat start":
                heartbeat.start()
                print("[Trillion] Heartbeat resumed.")
                continue

        print("Trillion > ", end="", flush=True)
        try:
            for chunk in agent.run_turn(user_input):
                print(chunk, end="", flush=True)
        except Exception as e:
            print(f"\n[Trillion] Something went wrong: {e}")
        print("\n")


def _show_notices() -> None:
    notices_path = Path(__file__).parent / "data" / "notices.json"
    if not notices_path.exists():
        print("[Trillion] No pending notices.\n")
        return
    import json
    notices = json.loads(notices_path.read_text())
    pending = [n for n in notices if not n.get("dismissed")]
    if not pending:
        print("[Trillion] No pending notices.\n")
        return
    print(f"\n[Trillion] {len(pending)} notice(s):\n")
    for i, n in enumerate(pending, 1):
        print(f"  {i}. [{n.get('priority','low').upper()}] {n['message']}")
    print()
    resp = input("Dismiss all? (y/n) > ").strip().lower()
    if resp == "y":
        for n in notices:
            n["dismissed"] = True
        notices_path.write_text(json.dumps(notices, indent=2))
        print("[Trillion] Notices cleared.\n")


if __name__ == "__main__":
    main()
