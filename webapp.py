from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Dict, List
from wsgiref.simple_server import make_server

from engine import GameEngine, load_game

ROOT = Path(__file__).resolve().parent
GAME_PATH = ROOT / "games" / "pirate_sample.json"


def load_engine() -> GameEngine:
    metadata = json.loads(GAME_PATH.read_text(encoding="utf-8"))
    return GameEngine(load_game(metadata), render_ascii_art=False)


def html_response(start_response, body: str, status: str = "200 OK"):
    encoded = body.encode("utf-8")
    start_response(
        status,
        [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(encoded))),
        ],
    )
    return [encoded]


def json_response(start_response, payload: Dict[str, object], status: str = "200 OK"):
    encoded = json.dumps(payload).encode("utf-8")
    start_response(
        status,
        [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(encoded))),
        ],
    )
    return [encoded]


def not_found(start_response):
    start_response("404 Not Found", [("Content-Type", "text/plain"), ("Content-Length", "9")])
    return [b"Not found"]


def method_not_allowed(start_response):
    start_response("405 Method Not Allowed", [("Content-Type", "text/plain"), ("Content-Length", "18")])
    return [b"Method not allowed"]


def unsafe_path(path: Path) -> bool:
    try:
        path.relative_to(ROOT)
    except ValueError:
        return True
    return False


def serve_static(start_response, relative: str):
    asset = (ROOT / relative).resolve()
    if not asset.exists() or unsafe_path(asset):
        return not_found(start_response)
    mime, _ = mimetypes.guess_type(str(asset))
    data = asset.read_bytes()
    start_response(
        "200 OK",
        [
            ("Content-Type", mime or "application/octet-stream"),
            ("Content-Length", str(len(data))),
        ],
    )
    return [data]


def landing_page(state_json: str) -> str:
    template = """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Parrot's Clue</title>
  <style>
    :root {
      color-scheme: dark;
      font-family: 'Segoe UI', system-ui, sans-serif;
      background: #0c111f;
      color: #f5f6fb;
    }
    body {
      margin: 0;
      padding: 0;
      display: flex;
      min-height: 100vh;
      justify-content: center;
      background: radial-gradient(circle at top, #1a2740, #05070f 70%);
    }
    .app-shell {
      max-width: 960px;
      width: 100%;
      padding: 2.5rem 2rem 3rem;
      box-sizing: border-box;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 1rem;
      margin-bottom: 1.5rem;
    }
    header h1 {
      font-weight: 600;
      margin: 0;
      font-size: 2rem;
      letter-spacing: 0.04em;
    }
    header button {
      background: #2b3b5f;
      color: inherit;
      border: 1px solid rgba(255, 255, 255, 0.15);
      padding: 0.5rem 1rem;
      border-radius: 999px;
      cursor: pointer;
      transition: background 0.2s ease, transform 0.2s ease;
      font-weight: 500;
    }
    header button:hover {
      background: #3a4d7a;
      transform: translateY(-1px);
    }
    .stage {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 1.5rem;
    }
    .viewport {
      position: relative;
      border-radius: 18px;
      overflow: hidden;
      box-shadow: 0 20px 45px rgba(5, 12, 27, 0.6);
      border: 1px solid rgba(255, 255, 255, 0.08);
      background: rgba(14, 20, 36, 0.9);
    }
    .viewport img {
      display: block;
      width: 100%;
      height: auto;
      aspect-ratio: 16 / 9;
      object-fit: cover;
      background: #101728;
    }
    .pane {
      padding: 1.25rem 1.5rem 1.5rem;
    }
    .pane h2 {
      margin: 0 0 0.75rem;
      font-size: 1.35rem;
      font-weight: 600;
    }
    .pane p {
      margin: 0.25rem 0 0;
      line-height: 1.5;
      color: #d6d9e6;
    }
    .sidebar {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    .card {
      background: rgba(15, 21, 36, 0.85);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 16px;
      padding: 1.25rem 1.4rem;
      box-shadow: 0 18px 35px rgba(5, 12, 27, 0.45);
    }
    .card h3 {
      margin: 0 0 0.6rem;
      font-size: 1.1rem;
      font-weight: 600;
      letter-spacing: 0.03em;
    }
    ul.clean {
      list-style: none;
      margin: 0;
      padding: 0;
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
    }
    ul.clean li {
      padding: 0.35rem 0.5rem;
      background: rgba(255, 255, 255, 0.05);
      border-radius: 8px;
      border: 1px solid rgba(255, 255, 255, 0.06);
    }
    .log {
      margin-top: 2rem;
      background: rgba(9, 13, 24, 0.9);
      border-radius: 18px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      padding: 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 1rem;
      box-shadow: 0 18px 38px rgba(5, 12, 27, 0.45);
      max-height: 320px;
      overflow-y: auto;
    }
    .entry {
      display: grid;
      gap: 0.35rem;
    }
    .entry .label {
      text-transform: uppercase;
      font-size: 0.7rem;
      letter-spacing: 0.22em;
      color: rgba(255, 255, 255, 0.5);
    }
    .entry.user {
      align-self: flex-end;
      text-align: right;
    }
    .entry.user .bubble {
      background: #1e365b;
    }
    .entry.game .bubble {
      background: #1b253d;
    }
    .bubble {
      padding: 0.65rem 0.9rem;
      border-radius: 14px;
      border: 1px solid rgba(255, 255, 255, 0.1);
      line-height: 1.55;
      white-space: pre-wrap;
      color: #f0f2ff;
    }
    form {
      margin-top: 1.8rem;
      display: flex;
      gap: 0.75rem;
    }
    input[type="text"] {
      flex: 1;
      padding: 0.85rem 1rem;
      border-radius: 999px;
      border: 1px solid rgba(255, 255, 255, 0.12);
      background: rgba(10, 15, 28, 0.85);
      color: inherit;
      font-size: 1rem;
      outline: none;
    }
    input[type="text"]:focus {
      border-color: rgba(101, 160, 255, 0.7);
      box-shadow: 0 0 0 2px rgba(101, 160, 255, 0.2);
    }
    button.primary {
      padding: 0.85rem 1.8rem;
      border-radius: 999px;
      border: none;
      background: linear-gradient(135deg, #4f8bff, #a26bff);
      color: white;
      font-weight: 600;
      letter-spacing: 0.05em;
      cursor: pointer;
      transition: transform 0.15s ease;
    }
    button.primary:hover {
      transform: translateY(-1px);
    }
    @media (max-width: 900px) {
      .stage {
        grid-template-columns: 1fr;
      }
      .log {
        max-height: none;
      }
    }
  </style>
</head>
<body>
  <div class=\"app-shell\">
    <header>
      <h1>Parrot's Clue</h1>
      <button id=\"reset-btn\" type=\"button\">Restart Adventure</button>
    </header>
    <div class=\"stage\">
      <div class=\"viewport\">
        <img id=\"location-art\" alt=\"Current location art\" src=\"\" />
        <div class=\"pane\">
          <h2 id=\"location-name\"></h2>
          <p id=\"location-description\"></p>
        </div>
      </div>
      <aside class=\"sidebar\">
        <div class=\"card\">
          <h3>Nearby</h3>
          <ul id=\"objects-list\" class=\"clean\"></ul>
        </div>
        <div class=\"card\">
          <h3>Characters</h3>
          <ul id=\"actors-list\" class=\"clean\"></ul>
        </div>
        <div class=\"card\">
          <h3>Inventory</h3>
          <ul id=\"inventory-list\" class=\"clean\"></ul>
        </div>
      </aside>
    </div>
    <section class=\"log\" id=\"history\"></section>
    <form id=\"command-form\">
      <input id=\"command-input\" type=\"text\" placeholder=\"Try 'inspect cabin door'\" autocomplete=\"off\" />
      <button class=\"primary\" type=\"submit\">Send</button>
    </form>
  </div>
  <script id=\"bootstrap-data\" type=\"application/json\">__STATE__</script>
  <script>
    const historyEl = document.getElementById('history');
    const locationName = document.getElementById('location-name');
    const locationDescription = document.getElementById('location-description');
    const locationArt = document.getElementById('location-art');
    const objectsList = document.getElementById('objects-list');
    const actorsList = document.getElementById('actors-list');
    const inventoryList = document.getElementById('inventory-list');
    const form = document.getElementById('command-form');
    const input = document.getElementById('command-input');
    const resetBtn = document.getElementById('reset-btn');

    function escapeHtml(text) {
      const mapping = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
      return text.replace(/[&<>\"']/g, (c) => mapping[c]);
    }

    function renderList(target, items, emptyText) {
      target.innerHTML = '';
      if (!items || items.length === 0) {
        const li = document.createElement('li');
        li.textContent = emptyText;
        li.style.opacity = '0.6';
        target.appendChild(li);
        return;
      }
      for (const item of items) {
        const li = document.createElement('li');
        li.innerHTML = `<strong>${escapeHtml(item.name)}</strong>` + (item.description ? `<br/><span style="opacity:0.75">${escapeHtml(item.description)}</span>` : '');
        target.appendChild(li);
      }
    }

    function renderHistory(history) {
      historyEl.innerHTML = '';
      for (const entry of history) {
        const wrapper = document.createElement('div');
        wrapper.className = `entry ${entry.speaker}`;
        const label = document.createElement('span');
        label.className = 'label';
        label.textContent = entry.speaker === 'user' ? 'You' : 'Game';
        const bubble = document.createElement('div');
        bubble.className = 'bubble';
        bubble.innerHTML = escapeHtml(entry.text);
        wrapper.appendChild(label);
        wrapper.appendChild(bubble);
        historyEl.appendChild(wrapper);
      }
      historyEl.scrollTop = historyEl.scrollHeight;
    }

    function updateView(data) {
      const { location } = data.view;
      locationName.textContent = location.name;
      locationDescription.textContent = location.description;
      locationArt.src = `/assets/${location.image}`;
      locationArt.alt = `${location.name} artwork`;
      renderList(objectsList, location.objects, 'Nothing of note.');
      renderList(actorsList, location.actors, 'No one nearby.');
      renderList(inventoryList, data.view.inventory, 'Empty hands.');
      renderHistory(data.history);
    }

    async function fetchState() {
      try {
        const response = await fetch('/api/state');
        if (!response.ok) {
          throw new Error('Failed to load state');
        }
        const data = await response.json();
        updateView(data);
      } catch (error) {
        console.error(error);
      }
    }

    async function sendCommand(command) {
      try {
        const response = await fetch('/api/command', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ command })
        });
        if (!response.ok) {
          throw new Error('Command failed');
        }
        const data = await response.json();
        updateView(data);
        return data;
      } catch (error) {
        console.error(error);
        return null;
      }
    }

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const command = input.value.trim();
      if (!command) {
        input.focus();
        return;
      }
      input.value = '';
      await sendCommand(command);
      input.focus();
    });

    resetBtn.addEventListener('click', async () => {
      await sendCommand('reset');
    });

    let initialState = null;
    const bootstrap = document.getElementById('bootstrap-data');
    if (bootstrap) {
      try {
        initialState = JSON.parse(bootstrap.textContent);
      } catch (error) {
        console.error('Failed to parse bootstrap state', error);
      }
    }

    if (initialState) {
      updateView(initialState);
    }
    fetchState();
  </script>
</body>
</html>"""

    return template.replace("__STATE__", state_json)


engine = load_engine()
history: List[Dict[str, str]] = []


def bootstrap_history() -> None:
    history.clear()
    intro = engine.describe_current_location()
    history.append({"speaker": "game", "text": intro})


def rebuild_engine() -> None:
    global engine
    engine = load_engine()
    bootstrap_history()


bootstrap_history()


def collect_state() -> Dict[str, object]:
    return {
        "history": history,
        "view": engine.view_state(),
    }


def handle_command(command_text: str) -> Dict[str, object]:
    lower = command_text.strip().lower()
    if lower in {"reset", "restart", "start over"}:
        rebuild_engine()
        return collect_state()

    if command_text.strip():
        history.append({"speaker": "user", "text": command_text})
        response = engine.handle_command(command_text)
        history.append({"speaker": "game", "text": response.output})
    else:
        description = engine.describe_current_location()
        history.append({"speaker": "game", "text": description})
    return collect_state()


def safe_state_payload(state: Dict[str, object]) -> str:
    payload = json.dumps(state)
    return payload.replace("</", "<\\/")


HTML = landing_page(safe_state_payload(collect_state()))


def app(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET").upper()

    if path == "/":
        if method != "GET":
            return method_not_allowed(start_response)
        return html_response(start_response, HTML)

    if path.startswith("/assets/"):
        relative = path[len("/assets/"):]
        return serve_static(start_response, relative)

    if path == "/api/state":
        if method != "GET":
            return method_not_allowed(start_response)
        return json_response(start_response, collect_state())

    if path == "/api/command":
        if method != "POST":
            return method_not_allowed(start_response)
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = 0
        raw = environ["wsgi.input"].read(length) if length > 0 else b""
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {}
        command_text = str(payload.get("command", ""))
        state = handle_command(command_text)
        return json_response(start_response, state)

    return not_found(start_response)


if __name__ == "__main__":
    with make_server("127.0.0.1", 8000, app) as server:
        print("Serving Parrot's Clue on http://127.0.0.1:8000")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
