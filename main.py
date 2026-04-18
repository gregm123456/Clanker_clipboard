"""
Clanker_clipboard — Raspberry Pi Zero 2W service

Entry point. Initializes hardware (MCP3008 ADC, GPIO buttons, IT8951 ePaper),
polls input state, updates the ePaper display, and serves live state to other
Clanker system components over the local network.

Node target: Raspberry Pi Zero 2W
"""

import time
import logging
import signal
import atexit

from clipboard.env import load_project_env
from clipboard.display import ClipboardDisplay

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    env_path = load_project_env()
    if env_path is not None:
        log.info("Loaded environment from %s", env_path)

    log.info("Clanker_clipboard starting")

    display = ClipboardDisplay()
    if display.is_available:
        log.info("ePaper display ready")
    else:
        log.warning("ePaper display unavailable: %s", display.last_error)

    shutdown_requested = False
    cleanup_done = False

    def _cleanup() -> None:
        nonlocal cleanup_done
        if cleanup_done:
            return
        cleanup_done = True

        log.info("Resetting ePaper before shutdown")
        try:
            display.clear()
            # Give IT8951 a moment to complete the clear operation.
            time.sleep(0.5)
        except Exception as exc:
            log.debug("Display reset during shutdown failed: %s", exc)
        finally:
            try:
                display.close()
            except Exception as exc:
                log.debug("Display close during shutdown failed: %s", exc)

    def _handle_shutdown_signal(signum, _frame) -> None:
        nonlocal shutdown_requested
        signal_name = signal.Signals(signum).name
        log.info("Received %s, shutting down", signal_name)
        shutdown_requested = True

    atexit.register(_cleanup)
    signal.signal(signal.SIGINT, _handle_shutdown_signal)
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)

    # TODO: initialize hardware
    # from clipboard.hw import ClipboardHardware
    # hw = ClipboardHardware()

    # TODO: initialize ePaper display
    # from clipboard.display import ClipboardDisplay
    # display = ClipboardDisplay()

    # TODO: start state HTTP server in background thread
    # from clipboard.server import start_server
    # start_server()

    log.info("Entering main loop")
    try:
        while not shutdown_requested:
            # TODO: read knobs and buttons
            # state = hw.read_state()
            # display.update(state)
            time.sleep(0.1)
    except KeyboardInterrupt:
        log.info("Keyboard interrupt received, shutting down")
    finally:
        _cleanup()


if __name__ == "__main__":
    main()
