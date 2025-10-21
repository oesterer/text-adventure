"""Diagnostic tool for the OpenAI integration.

It verifies that the API key is discoverable, that the LLMClient deems itself
available, and (optionally) attempts a lightweight request against the
Responses API so you can confirm network access.

Usage:
    python3 scripts/diagnose_llm.py            # run checks, attempt live call
    python3 scripts/diagnose_llm.py --dry-run  # skip the network request
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import GameEngine, LLMClient, load_game
from engine.llm import LLMUnavailableError

GAME_PATH = ROOT / "games" / "pirate_sample.json"
KEY_PATH = Path.home() / ".apikeys" / "openai"


def summarize_checks(llm_client: LLMClient) -> None:
    print("API key path:", KEY_PATH)
    if KEY_PATH.exists():
        print("  ✔ found key file")
    else:
        print("  ✖ key file missing")

    if llm_client.api_key:
        masked = llm_client.api_key[:4] + "…"
        print("Loaded API key (masked):", masked)
    else:
        print("No API key loaded from file or OPENAI_API_KEY.")

    if llm_client.available():
        print("LLMClient.available(): ✔ True")
    else:
        print("LLMClient.available(): ✖ False (check key content or permissions)")


def build_engine(llm_client: LLMClient) -> GameEngine:
    metadata = json.loads(GAME_PATH.read_text(encoding="utf-8"))
    return GameEngine(
        load_game(metadata),
        render_ascii_art=False,
        llm_client=llm_client if llm_client.available() else None,
    )


def attempt_request(game: GameEngine, llm_client: LLMClient) -> None:
    if not llm_client.available():
        print("Skipping network call: LLM client reports unavailable.")
        return

    context = game._serialize_for_llm()  # type: ignore[attr-defined]
    try:
        response_text = llm_client.generate_response(
            "diagnostic check: briefly describe the current location.",
            context,
            [],
        )
    except LLMUnavailableError as exc:
        print("LLM request failed:")
        print(" ", exc)
    except Exception as exc:  # pragma: no cover - debugging aid
        print("Unexpected error when contacting OpenAI:", exc)
    else:
        print("LLM responded successfully:\n", response_text)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Diagnose the OpenAI integration")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="skip the live API request and only report configuration",
    )
    args = parser.parse_args(argv)

    llm_client = LLMClient()
    summarize_checks(llm_client)
    game = build_engine(llm_client)

    if args.dry_run:
        return 0

    attempt_request(game, llm_client)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
