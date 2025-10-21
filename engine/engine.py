from __future__ import annotations

import zlib

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .models import (
    ActorMetadata,
    GameMetadata,
    GameState,
    LocationMetadata,
    ObjectMetadata,
    PathwayMetadata,
    build_initial_state,
)
from .llm import LLMClient, LLMUnavailableError, SerializedGameContext


@dataclass
class CommandResponse:
    output: str
    handled: bool = True


class GameEngine:
    def __init__(
        self,
        metadata: GameMetadata,
        *,
        render_ascii_art: bool = True,
        llm_client: Optional[LLMClient] = None,
    ) -> None:
        self.metadata = metadata
        self.state: GameState = build_initial_state(metadata)
        self.state.locations[self.state.player.location_id].visited = True
        self._image_cache: Dict[str, str] = {}
        self.render_ascii_art = render_ascii_art
        self.llm_client = llm_client
        self._llm_history: List[Dict[str, str]] = []

    # Public API -----------------------------------------------------------
    def handle_command(self, raw_input: str) -> CommandResponse:
        command = raw_input.strip()
        if not command:
            return CommandResponse(self.describe_current_location())

        lowered = command.lower()

        if lowered in {"look", "look around", "l"}:
            return CommandResponse(self.describe_current_location())
        if lowered in {"details", "examine location"}:
            return CommandResponse(self.describe_location_details())
        if lowered in {"inventory", "i"}:
            return CommandResponse(self.describe_inventory())
        if lowered == "help":
            return CommandResponse(self.describe_help())

        if lowered in {"map", "view map", "study map", "look at map"}:
            return CommandResponse(self.show_map())

        if lowered.startswith("inspect ") or lowered.startswith("examine "):
            target = self._extract_target(lowered)
            return CommandResponse(self.inspect_object(target))

        if lowered.startswith("take ") or lowered.startswith("pick up "):
            target = self._extract_target(lowered)
            return CommandResponse(self.take_object(target))

        if lowered.startswith("open "):
            target = self._extract_target(lowered)
            return CommandResponse(self.open_object(target))

        if lowered.startswith("talk ") or lowered.startswith("speak "):
            target = self._extract_target(lowered)
            return CommandResponse(self.talk_to_actor(target))

        if lowered.startswith("go ") or lowered.startswith("move "):
            target = self._extract_target(lowered)
            if target == "map":
                return CommandResponse(self.show_map())
            return CommandResponse(self.move_to_location(target))

        # Placeholder for LLM-backed responses.
        lore = self.describe_location_details()
        llm_text, via_llm = self._llm_response(command, lore)
        return CommandResponse(llm_text, handled=via_llm)

    def describe_current_location(self) -> str:
        location = self.current_location
        parts: List[str] = []
        artwork = None
        if self.render_ascii_art:
            artwork = self._render_location_image(location)
        if artwork:
            parts.append(artwork)
        parts.extend(
            [
                f"Location: {location.name}",
                location.description,
            ]
        )
        actors = list(self._actors_in_location())
        objects = list(self._objects_in_location(location))

        if actors:
            actor_names = ", ".join(actor.name for actor in actors)
            parts.append(f"You can see: {actor_names}.")
        if objects:
            object_names = ", ".join(obj.name for obj in objects if not self.state.objects[obj.id].held_by_player)
            if object_names:
                parts.append(f"Nearby objects: {object_names}.")
        pathways = list(self._visible_pathways())
        if pathways:
            path_names = ", ".join(path.name for path in pathways)
            parts.append(f"Exits: {path_names}.")
        return "\n".join(parts)

    def describe_location_details(self) -> str:
        details = self.current_location.details.strip()
        return details or "Nothing notable beyond the obvious." 

    def describe_inventory(self) -> str:
        inventory = self.state.player.inventory
        if not inventory:
            return "Your inventory is empty."
        rendered: List[str] = []
        for obj_id in inventory:
            meta = self._object_by_id(obj_id)
            if meta:
                rendered.append(meta.name)
        return "You carry: " + ", ".join(rendered)

    def describe_help(self) -> str:
        return (
            "Commands: look, details, inventory, map, inspect <object>, take <object>, open <object>, "
            "talk <actor>, go <path>."
        )

    # Object commands -----------------------------------------------------
    def inspect_object(self, target: Optional[str]) -> str:
        if not target:
            return "Inspect what?"

        obj = self._match_object_in_scope(target)
        if not obj:
            return f"There is no '{target}' to inspect."
        state = self.state.objects.get(obj.id)
        description = obj.description
        if obj.details:
            description = f"{description}\n{obj.details}"
        if state and state.status:
            state_bits = ", ".join(f"{key}={value}" for key, value in state.status.items())
            description = f"{description}\nCurrent state: {state_bits}."
        return description

    def take_object(self, target: Optional[str]) -> str:
        if not target:
            return "Take what?"
        obj = self._match_object_in_scope(target, include_inventory=False)
        if not obj:
            return f"You cannot find '{target}'."
        state = self.state.objects[obj.id]
        if state.held_by_player:
            return "You already have it."
        if not obj.can_pick_up:
            return "That cannot be picked up."
        state.held_by_player = True
        self.state.player.inventory.append(obj.id)
        return f"You pick up the {obj.name}."

    def open_object(self, target: Optional[str]) -> str:
        if not target:
            return "Open what?"
        obj = self._match_object_in_scope(target)
        if not obj:
            return f"There is no '{target}' here."
        state = self.state.objects[obj.id]
        if state.status.get("open") == "true":
            return "It is already open."
        state.status["open"] = "true"
        return f"You open the {obj.name}."

    # Actor commands ------------------------------------------------------
    def talk_to_actor(self, target: Optional[str]) -> str:
        if not target:
            return "Talk to whom?"
        actor = self._match_actor_in_scope(target)
        if not actor:
            return f"No one named '{target}' is here."
        dialogue = actor.dialogue.get("default") or actor.description
        return dialogue

    # Movement -------------------------------------------------------------
    def move_to_location(self, target: Optional[str]) -> str:
        if not target:
            return "Go where?"
        pathway = self._match_pathway_in_scope(target)
        if not pathway:
            return f"There is no path called '{target}'."
        state = self.state.pathways[pathway.id]
        if state.hidden:
            return "You do not know how to go that way."
        if state.locked:
            return "That way is locked."
        self.state.player.location_id = pathway.target
        self.state.locations[pathway.target].visited = True
        return self.describe_current_location()

    # Helpers --------------------------------------------------------------
    @property
    def current_location(self) -> LocationMetadata:
        return self.metadata.locations[self.state.player.location_id]

    def _objects_in_location(self, location: LocationMetadata) -> Iterable[ObjectMetadata]:
        return (obj for obj in location.objects)

    def _actors_in_location(self) -> Iterable[ActorMetadata]:
        return self.current_location.actors

    def _pathways_in_location(self) -> Iterable[PathwayMetadata]:
        return self.current_location.pathways

    def _visible_pathways(self) -> Iterable[PathwayMetadata]:
        for path in self._pathways_in_location():
            if self.state.pathways[path.id].hidden:
                continue
            yield path

    def _objects_in_location_scope(self) -> List[ObjectMetadata]:
        objects: List[ObjectMetadata] = []
        for obj in self._objects_in_location(self.current_location):
            if not self.state.objects[obj.id].held_by_player:
                objects.append(obj)
        for obj_id in self.state.player.inventory:
            obj_meta = self._object_by_id(obj_id)
            if obj_meta:
                objects.append(obj_meta)
        return objects

    def _match_object_in_scope(
        self,
        target: str,
        include_inventory: bool = True,
    ) -> Optional[ObjectMetadata]:
        target_lower = target.lower()
        candidates = []
        for obj in self._objects_in_location(self.current_location):
            if obj.name.lower() == target_lower or obj.id.lower() == target_lower:
                if not self.state.objects[obj.id].held_by_player:
                    return obj
                candidates.append(obj)
        if include_inventory:
            for obj_id in self.state.player.inventory:
                obj = self._object_by_id(obj_id)
                if obj and (obj.name.lower() == target_lower or obj.id.lower() == target_lower):
                    return obj
        if candidates:
            return candidates[0]
        return None

    def _match_actor_in_scope(self, target: str) -> Optional[ActorMetadata]:
        target_lower = target.lower()
        for actor in self._actors_in_location():
            if actor.name.lower() == target_lower or actor.id.lower() == target_lower:
                return actor
        return None

    def _match_pathway_in_scope(self, target: str) -> Optional[PathwayMetadata]:
        target_lower = target.lower()
        for path in self._pathways_in_location():
            if path.name.lower() == target_lower or path.id.lower() == target_lower:
                return path
        return None

    def _object_by_id(self, obj_id: str) -> Optional[ObjectMetadata]:
        for location in self.metadata.locations.values():
            for obj in location.objects:
                if obj.id == obj_id:
                    return obj
        return None

    @staticmethod
    def _extract_target(command: str) -> Optional[str]:
        parts = command.split(" ", 1)
        if len(parts) == 1:
            return None
        target = parts[1].strip()
        cleanup_prefixes = ("to ", "the ", "at ", "toward ", "towards ")
        changed = True
        while changed and target:
            changed = False
            for prefix in cleanup_prefixes:
                if target.startswith(prefix):
                    target = target[len(prefix) :].strip()
                    changed = True
        return target or None

    def _render_location_image(self, location: LocationMetadata) -> Optional[str]:
        return self._render_image_asset(location.image)

    def view_state(self) -> Dict[str, object]:
        location = self.current_location
        actors = [
            {
                "id": actor.id,
                "name": actor.name,
                "description": actor.description,
            }
            for actor in location.actors
        ]
        objects = []
        for obj in location.objects:
            if self.state.objects[obj.id].held_by_player:
                continue
            objects.append(
                {
                    "id": obj.id,
                    "name": obj.name,
                    "description": obj.description,
                    "details": obj.details,
                }
            )
        exits = [
            {
                "id": path.id,
                "name": path.name,
                "description": path.description,
                "target": path.target,
                "locked": self.state.pathways[path.id].locked,
            }
            for path in location.pathways
            if not self.state.pathways[path.id].hidden
        ]
        inventory = []
        for obj_id in self.state.player.inventory:
            meta = self._object_by_id(obj_id)
            if meta:
                inventory.append({"id": obj_id, "name": meta.name})
        return {
            "location": {
                "id": location.id,
                "name": location.name,
                "description": location.description,
                "details": location.details,
                "image": location.image,
                "actors": actors,
                "objects": objects,
                "exits": exits,
            },
            "inventory": inventory,
        }

    def show_map(self) -> str:
        if self.current_location.id != "captains_cabin":
            return "There is no map to study here."
        art = None
        if self.render_ascii_art:
            art = self._render_image_asset("images/PirateMap.png")
        map_object = next((obj for obj in self.current_location.objects if obj.id == "treasure_map"), None)
        description = map_object.details if map_object and map_object.details else "The weathered parchment hints at a hidden cove marked with a bold red X."
        if art:
            return f"{art}\n{description}"
        return description + "\nMap available at /assets/images/PirateMap.png"

    def _serialize_for_llm(self) -> SerializedGameContext:
        locations = list(self.metadata.locations.values())
        inventory_objects: List[ObjectMetadata] = []
        for obj_id in self.state.player.inventory:
            meta = self._object_by_id(obj_id)
            if meta:
                inventory_objects.append(meta)
        return SerializedGameContext(
            title=self.metadata.title,
            summary=self.metadata.summary,
            current_location=self.current_location,
            locations=locations,
            player_name=self.metadata.player.name,
            inventory=inventory_objects,
        )

    def _llm_response(self, command: str, lore: str) -> Tuple[str, bool]:
        fallback = (
            "The narrative engine would answer via an AI, "
            "drawing only from known details. For now, consult the location notes:\n"
            f"{lore}"
        )
        if not self.llm_client:
            return fallback, False

        try:
            context = self._serialize_for_llm()
            response = self.llm_client.generate_response(command, context, self._llm_history)
        except LLMUnavailableError:
            return fallback, False
        except Exception:
            return fallback, False

        self._llm_history.append({"command": command, "response": response})
        if len(self._llm_history) > 10:
            self._llm_history = self._llm_history[-10:]
        return response, True

    def _render_image_asset(self, path_label: str) -> Optional[str]:
        path_label = path_label.strip()
        if not path_label:
            return None
        cached = self._image_cache.get(path_label)
        if cached is not None:
            return cached

        asset_path = Path(path_label)
        if not asset_path.is_absolute():
            asset_path = Path.cwd() / asset_path

        if asset_path.suffix.lower() == ".png":
            try:
                content = self._png_to_ascii(asset_path)
            except Exception:
                content = f"[unable to render image: {path_label}]"
        else:
            try:
                content = asset_path.read_text(encoding="utf-8")
            except OSError:
                content = f"[missing artwork: {path_label}]"

        self._image_cache[path_label] = content
        return content

    def _png_to_ascii(self, path: Path) -> str:
        width, height, pixels = self._decode_png_rgba(path)
        target_cols = min(60, width)
        if target_cols <= 0:
            return ""
        step_x = width / target_cols
        # characters are roughly twice as tall as they are wide
        step_y = max(1.0, step_x * 0.5)
        rows = min(40, max(1, int(height / step_y)))
        ramp = " .:-=+*#%@"
        ascii_lines: List[str] = []
        for row_index in range(rows):
            y = min(height - 1, int(row_index * step_y))
            line_chars: List[str] = []
            for col_index in range(target_cols):
                x = min(width - 1, int(col_index * step_x))
                r, g, b, a = pixels[y][x]
                if a < 40:
                    line_chars.append(" ")
                    continue
                luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
                idx = int(luminance / 255 * (len(ramp) - 1))
                line_chars.append(ramp[idx])
            ascii_lines.append("".join(line_chars))
        return "\n".join(ascii_lines)

    @staticmethod
    def _decode_png_rgba(path: Path) -> Tuple[int, int, List[List[Tuple[int, int, int, int]]]]:
        data = path.read_bytes()
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Not a PNG file")

        offset = 8
        width = height = None
        idat_data = bytearray()
        while offset < len(data):
            length = int.from_bytes(data[offset : offset + 4], "big")
            chunk_type = data[offset + 4 : offset + 8]
            chunk_data = data[offset + 8 : offset + 8 + length]
            offset += 12 + length
            if chunk_type == b"IHDR":
                width = int.from_bytes(chunk_data[0:4], "big")
                height = int.from_bytes(chunk_data[4:8], "big")
                bit_depth = chunk_data[8]
                color_type = chunk_data[9]
                if bit_depth != 8 or color_type != 6:
                    raise ValueError("Unsupported PNG format")
            elif chunk_type == b"IDAT":
                idat_data.extend(chunk_data)
            elif chunk_type == b"IEND":
                break

        if width is None or height is None:
            raise ValueError("PNG missing IHDR")

        decompressed = zlib.decompress(bytes(idat_data))
        stride = width * 4
        pixels: List[List[Tuple[int, int, int, int]]] = []
        idx = 0
        for _ in range(height):
            filter_type = decompressed[idx]
            idx += 1
            if filter_type != 0:
                raise ValueError("Unsupported PNG filter")
            row: List[Tuple[int, int, int, int]] = []
            row_bytes = decompressed[idx : idx + stride]
            idx += stride
            for px in range(0, len(row_bytes), 4):
                r, g, b, a = row_bytes[px : px + 4]
                row.append((r, g, b, a))
            pixels.append(row)
        return width, height, pixels
