"""
server.py — Lightweight HTTP state server for Clanker_clipboard

Serves current knob and button state as JSON so other Clanker nodes
can poll it over the local network (Tailscale).

Endpoint: GET /state  → {"knobs": [...], "buttons": {...}}
Endpoint: GET /health → {"status": "ok"}

Node target: Raspberry Pi Zero 2W
"""

import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

log = logging.getLogger(__name__)

_state: dict = {"knobs": [], "buttons": {}}
_state_lock = threading.Lock()

HTTP_PORT = int(os.getenv("CLIPBOARD_HTTP_PORT", "8080"))


def set_state(state: dict) -> None:
    """Update the shared state that the server will serve."""
    with _state_lock:
        _state.update(state)


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002
        # Suppress per-request access logs to keep Zero 2W output clean
        pass

    def do_GET(self):  # noqa: N802
        if self.path == "/state":
            with _state_lock:
                body = json.dumps(_state).encode()
            self._respond(200, body)
        elif self.path == "/health":
            self._respond(200, b'{"status":"ok"}')
        else:
            self._respond(404, b'{"error":"not found"}')

    def _respond(self, code: int, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_server(port: int = HTTP_PORT) -> threading.Thread:
    """Start the HTTP state server in a daemon thread. Returns the thread."""
    server = HTTPServer(("", port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log.info("Clipboard state server listening on :%d", port)
    return thread
