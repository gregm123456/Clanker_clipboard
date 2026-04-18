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

    @property
    def is_available(self) -> bool:
        return self._display is not None and self._constants is not None

    def clear(self) -> None:
        """Clear the display to white if hardware is available."""
        if self._display is None:
            return
        self._display.clear()

    def show_test_pattern(self, text: str = "CLANKER CLIPBOARD") -> None:
        """Render a simple full-screen test pattern for hardware bring-up."""
        img = Image.new("L", (DISPLAY_WIDTH, DISPLAY_HEIGHT), 255)
        draw = ImageDraw.Draw(img)

        draw.rectangle([12, 12, DISPLAY_WIDTH - 12, DISPLAY_HEIGHT - 12], outline=0, width=6)
        draw.line([80, 220, DISPLAY_WIDTH - 80, 220], fill=0, width=4)
        draw.line([80, DISPLAY_HEIGHT - 220, DISPLAY_WIDTH - 80, DISPLAY_HEIGHT - 220], fill=0, width=4)
        draw.rectangle([120, 300, 420, 600], outline=0, width=5)
        draw.ellipse([DISPLAY_WIDTH - 420, 300, DISPLAY_WIDTH - 120, 600], outline=0, width=5)

        font = self._load_font(72)
        sub_font = self._load_font(42)

        title_box = draw.textbbox((0, 0), text, font=font)
        title_width = title_box[2] - title_box[0]
        draw.text(((DISPLAY_WIDTH - title_width) / 2, 90), text, fill=0, font=font)
        draw.text((160, 680), "IT8951 full refresh test", fill=0, font=sub_font)
        draw.text((160, 760), f"VCOM {VCOM:.2f}", fill=0, font=sub_font)

        self._display.frame_buf.paste(img, [0, 0])
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

    def _load_font(self, size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except Exception:
            return ImageFont.load_default()

    def close(self) -> None:
        log.info("ClipboardDisplay closed")
