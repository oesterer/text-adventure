from __future__ import annotations

from typing import Any, Dict, List

from .models import (
    ActorMetadata,
    GameMetadata,
    LocationMetadata,
    ObjectMetadata,
    PathwayMetadata,
    PlayerMetadata,
)


def load_game(metadata: Dict[str, Any]) -> GameMetadata:
    player_cfg = metadata["player"]
    player = PlayerMetadata(
        name=player_cfg.get("name", "Player"),
        description=player_cfg.get("description", ""),
        starting_inventory=list(player_cfg.get("starting_inventory", [])),
    )

    locations: Dict[str, LocationMetadata] = {}
    for location_cfg in metadata.get("locations", []):
        objects = [
            ObjectMetadata(
                id=obj_cfg["id"],
                name=obj_cfg.get("name", obj_cfg["id"]),
                description=obj_cfg.get("description", ""),
                details=obj_cfg.get("details", ""),
                can_pick_up=obj_cfg.get("can_pick_up", False),
                can_move=obj_cfg.get("can_move", False),
                initial_state=dict(obj_cfg.get("initial_state", {})),
                contains=list(obj_cfg.get("contains", [])),
            )
            for obj_cfg in location_cfg.get("objects", [])
        ]
        actors = [
            ActorMetadata(
                id=actor_cfg["id"],
                name=actor_cfg.get("name", actor_cfg["id"]),
                description=actor_cfg.get("description", ""),
                persona=actor_cfg.get("persona", ""),
                background=actor_cfg.get("background", ""),
                dialogue=dict(actor_cfg.get("dialogue", {})),
                inventory=list(actor_cfg.get("inventory", [])),
            )
            for actor_cfg in location_cfg.get("actors", [])
        ]
        pathways = [
            PathwayMetadata(
                id=path_cfg["id"],
                name=path_cfg.get("name", path_cfg["id"]),
                target=path_cfg["target"],
                description=path_cfg.get("description", ""),
                locked=path_cfg.get("locked", False),
                hidden=path_cfg.get("hidden", False),
                unlocks_with=path_cfg.get("unlocks_with"),
                reveals_with=path_cfg.get("reveals_with"),
            )
            for path_cfg in location_cfg.get("pathways", [])
        ]

        location = LocationMetadata(
            id=location_cfg["id"],
            name=location_cfg.get("name", location_cfg["id"]),
            image=location_cfg.get("image", ""),
            description=location_cfg.get("description", ""),
            details=location_cfg.get("details", ""),
            objects=objects,
            actors=actors,
            pathways=pathways,
        )
        locations[location.id] = location

    return GameMetadata(
        title=metadata.get("title", "Untitled"),
        summary=metadata.get("summary", ""),
        start_location=metadata["start_location"],
        locations=locations,
        player=player,
    )
