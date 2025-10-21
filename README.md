# Text Adventure Engine

Lightweight engine for loading text-driven adventure games defined by structured metadata. Locations, objects, actors, and pathways are described in JSON and converted into actionable state the engine can reason about during a play session.

## Running the sample game (browser)

```bash
python3 webapp.py
```

Then open http://127.0.0.1:8000 to explore the adventure in a styled web UI with inline imagery and a command console. Use the restart button to reset the session.

## Enabling LLM narration

Store your OpenAI API key at `~/.apikeys/openai` (plain text, no whitespace). When present, both the CLI and browser server automatically route free-form exploration prompts through the `gpt-4.1-mini` model via the Responses API. Unhandled commands then receive in-world replies driven by the game metadata (locations, objects, actors, and pathways). If the key is missing the engine falls back to deterministic canned text.

## Running the sample game (terminal)

```bash
python3 main.py
```

Location art renders in the terminal before each description using PNG assets stored under `images/`. Images are downsampled to ASCII for terminal display while retaining the original PNG files.

Useful commands once the CLI starts:

- `look` — recap the current location
- `inspect <object>` — learn more about an object in scope
- `talk <actor>` — hear what someone has to say
- `take <object>` — add portable items to your inventory
- `go <path>` — move through a visible pathway
- `inventory` — show what you are carrying
- `help` — list built-in commands (anything else falls back to the narrative AI hook)

The engine still handles structural commands (movement, talking to named actors, opening objects, quitting) locally to maintain deterministic state.

Type `exit` or `quit` to leave the session.

## Game metadata structure

Metadata is stored under `games/` as JSON. The loader consumes a schema with:

- `title`, `summary`, and `start_location`
- `player` definition with `name`, optional `description`, and starting inventory
- `locations` array of location blocks containing `image`, `description`, optional `details`, and nested collections for `objects`, `actors`, and `pathways`

Objects declare whether they can be picked up or moved and track arbitrary state values (such as `open: true/false`). Pathways can be hidden or locked to gate traversal. Actors support persona/background notes and simple keyed dialogue snippets for deterministic responses.

See `games/pirate_sample.json` for a working example featuring two locations aboard a pirate vessel.
