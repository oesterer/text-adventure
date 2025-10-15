"""Lightweight text adventure engine primitives."""

from .engine import CommandResponse, GameEngine
from .loader import load_game
from .models import (
    ActorMetadata,
    GameMetadata,
    GameState,
    LocationMetadata,
    ObjectMetadata,
    PathwayMetadata,
    PlayerMetadata,
    build_initial_state,
)

__all__ = [
    "CommandResponse",
    "GameEngine",
    "load_game",
    "ActorMetadata",
    "GameMetadata",
    "GameState",
    "LocationMetadata",
    "ObjectMetadata",
    "PathwayMetadata",
    "PlayerMetadata",
    "build_initial_state",
]
