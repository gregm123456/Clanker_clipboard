"""Manual one-shot ePaper reset utility for Clanker_clipboard."""

from __future__ import annotations

import logging
import time

from clipboard.display import ClipboardDisplay
from clipboard.env import load_project_env

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main() -> int:
    env_path = load_project_env()
    if env_path is not None:
        log.info("Loaded environment from %s", env_path)

    display = ClipboardDisplay()
    try:
        if not display.is_available:
            log.error("ePaper display unavailable: %s", display.last_error)
            return 1

        log.info("Clearing ePaper display")
        display.clear()
        # Give IT8951 a moment to complete the clear operation.
        time.sleep(0.5)
        log.info("ePaper reset complete")
        return 0
    finally:
        display.close()


if __name__ == "__main__":
    raise SystemExit(main())
