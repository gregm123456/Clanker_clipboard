"""
display.py — ePaper display driver wrapper for Clanker_clipboard

Wraps the IT8951 controller driver for the 6-inch grayscale ePaper panel.
Provides simple methods for clearing the screen and rendering text/status.

Node target: Raspberry Pi Zero 2W
"""

import os
import logging
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

# Display resolution for the 6-inch IT8951 panel (adjust to match your panel)
DISPLAY_WIDTH = 1448
DISPLAY_HEIGHT = 1072

VCOM = float(os.getenv("EPAPER_VCOM", "-1.45"))


class ClipboardDisplay:
    """
    Manages the IT8951 ePaper display.

    Usage::

        display = ClipboardDisplay()
        display.update({"knobs": [0, 3, 7, 2], "buttons": {}})
        display.close()
    """

    def __init__(self) -> None:
        # Import here so the module can be imported on non-Pi systems without crashing
        try:
            from IT8951.display import AutoEPDDisplay
            from IT8951 import constants

            self._display = AutoEPDDisplay(vcom=VCOM, rotate=None, mirror=False)
            self._constants = constants
            log.info("ClipboardDisplay initialized — VCOM %.2f", VCOM)
        except Exception as exc:
            log.warning("ePaper display unavailable: %s — running in headless mode", exc)
            self._display = None
            self._constants = None

    def update(self, state: dict) -> None:
        """Render current knob/button state to the ePaper display."""
        image = self._render(state)
        if self._display is not None:
            self._display.frame_buf.paste(image, [0, 0])
            self._display.draw_full(self._constants.DisplayModes.GL16)

    def _render(self, state: dict) -> Image.Image:
        """Build a PIL image representing the current state."""
        img = Image.new("L", (DISPLAY_WIDTH, DISPLAY_HEIGHT), 255)
        draw = ImageDraw.Draw(img)

        knobs = state.get("knobs", [])
        buttons = state.get("buttons", {})

        draw.text((40, 40), "Clanker Clipboard", fill=0)

        for i, pos in enumerate(knobs):
            y = 120 + i * 80
            draw.text((40, y), f"Knob {i + 1}: {pos}", fill=0)

        y = 120 + len(knobs) * 80 + 20
        for name, pressed in buttons.items():
            label = f"{name}: {'PRESSED' if pressed else 'open'}"
            draw.text((40, y), label, fill=0)
            y += 60

        return img

    def close(self) -> None:
        log.info("ClipboardDisplay closed")
