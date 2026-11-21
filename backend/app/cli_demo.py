# backend/app/cli_demo.py
# P5 — Text-based CLI demo of the dialogue brain.
#
# WHY this file exists: Tests prove correctness; this proves it FEELS right.
# Type speech, see what the agent would say + what actions it emits.
# No audio. No Gnani. No network. Run anywhere.
#
# Usage:
#   python -m app.cli_demo --lang en-IN
#   python -m app.cli_demo --lang hi-IN
#   python -m app.cli_demo --lang kn-IN
#
# Type your "speech" at the prompt. Special commands:
#   /quit or /exit  — end session
#   /session        — print full session dict (debug)
#   /reset          — start a new session

import argparse
import json
import sys

from app.brain.dialogue import new_session, handle
from app.repo import memory_repo


def _print_actions(actions: list[dict]) -> None:
    """Print each action in a human-readable way."""
    for action in actions:
        atype = action.get("type")

        if atype == "say":
            # _text is pre-rendered by _say() in dialogue.py
            text = action.get("_text") or action.get("key", "")
            print(f"\n  🔊 AGENT: {text}")

        elif atype == "alert":
            signs = action.get("signs", [])
            print(f"\n  🚨 DANGER ALERT: {', '.join(signs)}")

        elif atype == "card":
            draft = action.get("draft", {})
            uncertain = action.get("uncertain", [])
            print(f"\n  📋 CARD UPDATE:")
            # Print only non-null fields
            for k, v in draft.items():
                if v is not None and not k.startswith("_"):
                    marker = " ⚠️" if k in uncertain else ""
                    print(f"       {k}: {v}{marker}")
            if uncertain:
                print(f"       Still missing: {', '.join(uncertain)}")

        elif atype == "saved":
            visit_id = action.get("visit_id", "")
            print(f"\n  ✅ SAVED: visit_id={visit_id}")

        else:
            print(f"\n  [{atype}] {json.dumps(action, ensure_ascii=False)}")


def run_demo(lang: str) -> None:
    """Run an interactive CLI session."""
    print(f"\n{'='*60}")
    print(f"  ASHA Mitra — CLI Demo  |  language: {lang}")
    print(f"{'='*60}")
    print("  Type your spoken notes. Commands: /quit /session /reset")
    print()

    # Fresh memory repo for clean demo
    memory_repo.reset_for_testing()

    session = new_session(lang)

    # Fire "start" event to get disclosure
    start_actions = handle(session, {"type": "start", "lang": lang})
    _print_actions(start_actions)

    while True:
        print()
        try:
            user_input = input("  YOU: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  (session ended)")
            break

        if not user_input:
            continue

        # Handle special CLI commands
        if user_input.lower() in ("/quit", "/exit"):
            print("  Goodbye.")
            break

        if user_input.lower() == "/session":
            print(f"\n  SESSION: {json.dumps(session, default=str, ensure_ascii=False, indent=4)}")
            continue

        if user_input.lower() == "/reset":
            memory_repo.reset_for_testing()
            session = new_session(lang)
            print("  (session reset)")
            start_actions = handle(session, {"type": "start", "lang": lang})
            _print_actions(start_actions)
            continue

        # Normal "user_text" event
        actions = handle(session, {"type": "user_text", "text": user_input})
        _print_actions(actions)

        if session.get("state") == "DONE":
            print("\n  (visit saved — type /reset to start a new session)")


def main() -> None:
    parser = argparse.ArgumentParser(description="ASHA Mitra CLI Demo")
    parser.add_argument(
        "--lang",
        default="en-IN",
        choices=["en-IN", "hi-IN", "kn-IN"],
        help="Session language (default: en-IN)",
    )
    args = parser.parse_args()
    run_demo(args.lang)


if __name__ == "__main__":
    main()
