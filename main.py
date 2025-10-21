from __future__ import annotations

import json
from pathlib import Path

from engine import GameEngine, LLMClient, load_game


def load_metadata(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def run_cli(game: GameEngine) -> None:
    print("Welcome to", game.metadata.title)
    print(game.describe_current_location())
    while True:
        raw = input("\n> ").strip()
        if raw.lower() in {"quit", "exit"}:
            print("Farewell, adventurer.")
            return
        response = game.handle_command(raw)
        print(response.output)


def build_game(
    sample: bool = True,
    *,
    render_ascii_art: bool = True,
    with_llm: bool = True,
) -> GameEngine:
    root = Path(__file__).parent
    path = root / "games" / "pirate_sample.json"
    metadata_dict = load_metadata(path)
    metadata = load_game(metadata_dict)
    llm_client = None
    if with_llm:
        candidate = LLMClient()
        if candidate.available():
            llm_client = candidate
    return GameEngine(metadata, render_ascii_art=render_ascii_art, llm_client=llm_client)


if __name__ == "__main__":
    run_cli(build_game())
