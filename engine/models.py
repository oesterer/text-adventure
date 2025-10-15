from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ObjectMetadata:
    id: str
    name: str
    description: str
    details: str = ""
    can_pick_up: bool = False
    can_move: bool = False
    initial_state: Dict[str, str] = field(default_factory=dict)
    contains: List[str] = field(default_factory=list)


@dataclass
class ActorMetadata:
    id: str
    name: str
    description: str
    persona: str = ""
    background: str = ""
    dialogue: Dict[str, str] = field(default_factory=dict)
    inventory: List[str] = field(default_factory=list)


@dataclass
class PathwayMetadata:
    id: str
    name: str
    target: str
    description: str
    locked: bool = False
    hidden: bool = False
    unlocks_with: Optional[str] = None
    reveals_with: Optional[str] = None


@dataclass
class LocationMetadata:
    id: str
    name: str
    image: str
    description: str
    details: str = ""
    objects: List[ObjectMetadata] = field(default_factory=list)
    actors: List[ActorMetadata] = field(default_factory=list)
    pathways: List[PathwayMetadata] = field(default_factory=list)


@dataclass
class PlayerMetadata:
    name: str
    description: str = ""
    starting_inventory: List[str] = field(default_factory=list)


@dataclass
class GameMetadata:
    title: str
    summary: str
    start_location: str
    locations: Dict[str, LocationMetadata]
    player: PlayerMetadata


@dataclass
class ObjectState:
    status: Dict[str, str] = field(default_factory=dict)
    held_by_player: bool = False


@dataclass
class ActorState:
    conversation_flags: Dict[str, bool] = field(default_factory=dict)
    inventory: List[str] = field(default_factory=list)


@dataclass
class PathwayState:
    locked: bool = False
    hidden: bool = False


@dataclass
class LocationState:
    visited: bool = False


@dataclass
class PlayerState:
    location_id: str
    inventory: List[str] = field(default_factory=list)
    attributes: Dict[str, str] = field(default_factory=dict)


@dataclass
class GameState:
    player: PlayerState
    objects: Dict[str, ObjectState]
    actors: Dict[str, ActorState]
    pathways: Dict[str, PathwayState]
    locations: Dict[str, LocationState]


def build_initial_state(game: GameMetadata) -> GameState:
    objects_state: Dict[str, ObjectState] = {}
    actors_state: Dict[str, ActorState] = {}
    pathways_state: Dict[str, PathwayState] = {}
    locations_state: Dict[str, LocationState] = {}

    for location in game.locations.values():
        locations_state[location.id] = LocationState(visited=False)
        for obj in location.objects:
            objects_state[obj.id] = ObjectState(status=dict(obj.initial_state))
        for actor in location.actors:
            actors_state[actor.id] = ActorState()
        for path in location.pathways:
            pathways_state[path.id] = PathwayState(
                locked=path.locked,
                hidden=path.hidden,
            )

    player_state = PlayerState(
        location_id=game.start_location,
        inventory=list(game.player.starting_inventory),
    )

    for obj_id in player_state.inventory:
        if obj_id in objects_state:
            objects_state[obj_id].held_by_player = True

    return GameState(
        player=player_state,
        objects=objects_state,
        actors=actors_state,
        pathways=pathways_state,
        locations=locations_state,
    )
