from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib import error, request

from .models import ActorMetadata, LocationMetadata, ObjectMetadata, PathwayMetadata

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_KEY_PATH = Path.home() / ".apikeys" / "openai"


class LLMUnavailableError(RuntimeError):
    """Raised when the LLM cannot be contacted or configured."""


@dataclass
class SerializedGameContext:
    title: str
    summary: str
    current_location: LocationMetadata
    locations: Iterable[LocationMetadata]
    player_name: str
    inventory: List[ObjectMetadata]


class LLMClient:
    def __init__(
        self,
        api_key_path: Optional[Path] = None,
        *,
        model: str = DEFAULT_MODEL,
        max_output_tokens: int = 400,
        temperature: float = 0.7,
    ) -> None:
        self.api_key_path = api_key_path or DEFAULT_KEY_PATH
        self.api_key = self._load_api_key(self.api_key_path)
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature

    def available(self) -> bool:
        return bool(self.api_key)

    def generate_response(
        self,
        command: str,
        context: SerializedGameContext,
        llm_history: List[Dict[str, str]],
    ) -> str:
        if not self.available():
            raise LLMUnavailableError("OpenAI API key not configured.")

        messages = self._build_messages(command, context, llm_history)
        payload = {
            "model": self.model,
            "input": messages,
            "max_output_tokens": self.max_output_tokens,
            "temperature": self.temperature,
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        req = request.Request(
            OPENAI_RESPONSES_URL,
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=30) as resp:
                response_payload = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:  # pragma: no cover - network errors
            detail = exc.read().decode("utf-8", errors="ignore") if exc.fp else ""
            message = detail or exc.reason or "HTTP error"
            raise LLMUnavailableError(f"Failed contacting OpenAI API: {exc.code} {message}") from exc
        except Exception as exc:  # pragma: no cover - network errors
            raise LLMUnavailableError(f"Failed contacting OpenAI API: {exc}") from exc

        return self._extract_text(response_payload)

    # Internal helpers --------------------------------------------------
    def _build_messages(
        self,
        command: str,
        context: SerializedGameContext,
        llm_history: List[Dict[str, str]],
    ) -> List[Dict[str, object]]:
        location_notes = self._render_locations(context.locations, context.current_location)
        inventory_notes = self._render_inventory(context.inventory)
        system_prompt = (
            f"You are the narrative intelligence for the text adventure '{context.title}'. "
            "Answer as the narrator or non-player characters, using only the provided canon." 
            " If the player requests actions you cannot fulfill, describe what is known or suggest valid moves."
        )

        messages: List[Dict[str, object]] = [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "system",
                "content": [
                    {"type": "input_text", "text": f"GAME SUMMARY:\n{context.summary}"},
                    {"type": "input_text", "text": "CURRENT LOCATION:\n" + location_notes[context.current_location.id]},
                ],
            },
        ]

        other_locations = [
            loc_text
            for loc_id, loc_text in location_notes.items()
            if loc_id != context.current_location.id
        ]
        if other_locations:
            messages.append(
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "OTHER LOCATIONS:\n" + "\n\n".join(other_locations),
                        }
                    ],
                }
            )

        if inventory_notes:
            messages.append(
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "PLAYER INVENTORY:\n" + inventory_notes,
                        }
                    ],
                }
            )

        for entry in llm_history[-6:]:
            messages.append(
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": entry["command"]}],
                }
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": entry["response"]}],
                }
            )

        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": command}
                ],
            }
        )
        return messages

    @staticmethod
    def _render_locations(
        locations: Iterable[LocationMetadata],
        current: LocationMetadata,
    ) -> Dict[str, str]:
        notes: Dict[str, str] = {}
        for location in locations:
            buffer: List[str] = [f"Location {location.name} (id: {location.id})"]
            buffer.append(f"Description: {location.description}")
            if location.details:
                buffer.append(f"Details: {location.details}")
            if location.actors:
                actor_lines = [LLMClient._render_actor(actor) for actor in location.actors]
                buffer.append("Actors:\n- " + "\n- ".join(actor_lines))
            if location.objects:
                object_lines = [LLMClient._render_object(obj) for obj in location.objects]
                buffer.append("Objects:\n- " + "\n- ".join(object_lines))
            if location.pathways:
                path_lines = [LLMClient._render_pathway(path) for path in location.pathways]
                buffer.append("Paths:\n- " + "\n- ".join(path_lines))
            notes[location.id] = "\n".join(buffer)
        return notes

    @staticmethod
    def _render_actor(actor: ActorMetadata) -> str:
        parts = [f"{actor.name} ({actor.id})"]
        if actor.persona:
            parts.append(f"Persona: {actor.persona}")
        if actor.background:
            parts.append(f"Background: {actor.background}")
        if actor.description:
            parts.append(f"Description: {actor.description}")
        return "; ".join(parts)

    @staticmethod
    def _render_object(obj: ObjectMetadata) -> str:
        parts = [f"{obj.name} ({obj.id})"]
        if obj.description:
            parts.append(f"Description: {obj.description}")
        if obj.details:
            parts.append(f"Details: {obj.details}")
        state_bits = []
        for key, value in obj.initial_state.items():
            state_bits.append(f"{key}={value}")
        if state_bits:
            parts.append("State: " + ", ".join(state_bits))
        interaction = []
        if obj.can_pick_up:
            interaction.append("pick-up")
        if obj.can_move:
            interaction.append("move")
        if interaction:
            parts.append("Interact: " + ", ".join(interaction))
        return "; ".join(parts)

    @staticmethod
    def _render_pathway(path: PathwayMetadata) -> str:
        flags = []
        if path.locked:
            flags.append("locked")
        if path.hidden:
            flags.append("hidden")
        flag_str = f" ({', '.join(flags)})" if flags else ""
        return f"{path.name} -> {path.target}{flag_str}"

    @staticmethod
    def _render_inventory(inventory: List[ObjectMetadata]) -> str:
        if not inventory:
            return ""
        return "\n".join(f"- {obj.name}: {obj.description}" for obj in inventory)

    @staticmethod
    def _extract_text(response_payload: Dict[str, object]) -> str:
        outputs = response_payload.get("output")
        if not isinstance(outputs, list):
            raise LLMUnavailableError("Unexpected response schema from OpenAI.")
        for message in outputs:
            if not isinstance(message, dict):
                continue
            if message.get("role") != "assistant":
                continue
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if isinstance(item, dict) and item.get("type") in {"output_text", "text"}:
                    text = item.get("text")
                    if isinstance(text, str):
                        return text.strip()
        raise LLMUnavailableError("No assistant output returned by OpenAI.")

    @staticmethod
    def _load_api_key(path: Path) -> Optional[str]:
        try:
            key = path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            key = os.getenv("OPENAI_API_KEY", "").strip()
        except OSError:
            return None
        return key or None
