"""Environment helpers for Clanker_clipboard."""

from __future__ import annotations

import os
from pathlib import Path

_ENV_PATH: Path | None = None
_ATTEMPTED = False


def load_project_env() -> Path | None:
    """Load .env from the project root into os.environ if present."""
    global _ENV_PATH, _ATTEMPTED

    if _ATTEMPTED:
        return _ENV_PATH

    _ATTEMPTED = True
    candidate = Path(__file__).resolve().parent.parent / ".env"
    if not candidate.exists():
        return None

    for raw_line in candidate.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]

        os.environ.setdefault(key, value)

    _ENV_PATH = candidate
    return _ENV_PATH