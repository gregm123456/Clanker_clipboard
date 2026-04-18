"""
Clanker_clipboard — Raspberry Pi Zero 2W service

Entry point. Initializes hardware (MCP3008 ADC, GPIO buttons, IT8951 ePaper),
polls input state, updates the ePaper display, and serves live state to other
Clanker system components over the local network.

Node target: Raspberry Pi Zero 2W
"""

import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main() -> None:
    log.info("Clanker_clipboard starting")

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
    while True:
        # TODO: read knobs and buttons
        # state = hw.read_state()
        # display.update(state)
        time.sleep(0.1)


if __name__ == "__main__":
    main()
