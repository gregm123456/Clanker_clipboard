"""
display.py — ePaper display driver wrapper for Clanker_clipboard

Wraps the IT8951 controller driver for the 6-inch grayscale ePaper panel.
Provides simple methods for clearing the screen and rendering text/status.

Node target: Raspberry Pi Zero 2W
"""

import os
import logging
from PIL import Image, ImageDraw, ImageFont

from clipboard.env import load_project_env
from clipboard.epaper_enhanced import create_display

log = logging.getLogger(__name__)

# Display resolution for the 6-inch IT8951 panel (adjust to match your panel)
DISPLAY_WIDTH = 1448
DISPLAY_HEIGHT = 1072

DEFAULT_VCOM = -2.06
DEFAULT_SPI_DEVICE = 0


class ClipboardDisplay:
    """
    Manages the IT8951 ePaper display.

    Usage::

        display = ClipboardDisplay()
        display.update({"knobs": [0, 3, 7, 2], "buttons": {}})
        display.close()
    """

    def __init__(self) -> None:
        load_project_env()
        self._vcom = float(os.getenv("EPAPER_VCOM", str(DEFAULT_VCOM)))
        self._spi_device = int(os.getenv("EPAPER_SPI_DEVICE", str(DEFAULT_SPI_DEVICE)))
        self._last_error: str | None = None

        try:
            # Use picker's proven display driver factory
            self._display = create_display(
                spi_device=self._spi_device,
                vcom=self._vcom,
                width=DISPLAY_WIDTH,
                height=DISPLAY_HEIGHT,
                force_simulation=False,
                prefer_enhanced=True,
            )
            log.info(
                "ClipboardDisplay initialized — display %dx%d, VCOM %.2f, SPI device %d",
                DISPLAY_WIDTH,
                DISPLAY_HEIGHT,
                self._vcom,
                self._spi_device,
            )
        except Exception as exc:
            self._last_error = str(exc)
            log.warning("ePaper display unavailable: %s — running in headless mode", exc)
            self._display = None

    def update(self, state: dict, mode: str = "image") -> None:
        """Render current knob/button state to the ePaper display.
        
        Args:
            state: Dictionary with 'knobs' and 'buttons' data.
            mode: Display refresh mode - 'text' (DU partial), 'image' (GC16 full), 'fast' (DU partial).
        """
        image = self._render(state)
        if self._display is not None:
            self._blit(image, mode=mode)

    @property
    def is_available(self) -> bool:
        return self._display is not None

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def vcom(self) -> float:
        return self._vcom

    @property
    def spi_device(self) -> int:
        return self._spi_device

    def device_summary(self) -> dict[str, str | int | float | None]:
        if self._display is None:
            return {
                "width": None,
                "height": None,
                "vcom": self._vcom,
                "spi_device": self._spi_device,
            }

        return {
            "width": getattr(self._display, "width", DISPLAY_WIDTH),
            "height": getattr(self._display, "height", DISPLAY_HEIGHT),
            "vcom": self._vcom,
            "spi_device": self._spi_device,
        }

    def clear(self) -> None:
        """Clear the display to white if hardware is available."""
        if self._display is None:
            return
        self._display.clear()

    def _blit(self, img: Image.Image, mode: str = "image") -> None:
        """Display the image using the configured refresh mode.
        
        Args:
            img: PIL Image in any mode.
            mode: Refresh mode - 'text' or 'fast' for DU, 'image' for GC16.
        """
        # Map Clanker modes to epaper_enhanced modes
        if mode in ("text", "fast"):
            display_mode = "FAST"  # DU partial for responsiveness
        else:
            display_mode = "full"  # GC16 for image quality

        try:
            self._display.display_image(img, mode=display_mode)
            log.debug(f"Display updated (mode={display_mode})")
        except Exception as exc:
            log.error(f"Display update failed: {exc}")
            raise

    def show_test_pattern(self, text: str = "CLANKER CLIPBOARD") -> None:
        """Render a simple full-screen test pattern for hardware bring-up."""
        if self._display is None:
            return
        img = self._build_test_image(text)
        self._blit(img)

    def show_test_pattern_with_strategy(self, text: str, strategy: str = "text") -> None:
        """Render test pattern with specified refresh strategy.

        The strategy parameter controls refresh mode: 'text'/'fast' use DU partial (fast),
        'image' uses GC16 full (quality).
        """
        if self._display is None:
            return
        img = self._build_test_image(text, label=f"strategy: {strategy}")
        self._blit(img, mode=strategy)

    def _build_test_image(self, text: str, label: str = "IT8951 test pattern") -> Image.Image:
        """Build the test pattern PIL image."""
        w = DISPLAY_WIDTH
        h = DISPLAY_HEIGHT
        img = Image.new("L", (w, h), 255)
        draw = ImageDraw.Draw(img)

        draw.rectangle([12, 12, w - 12, h - 12], outline=0, width=6)
        draw.line([80, 220, w - 80, 220], fill=0, width=4)
        draw.line([80, h - 220, w - 80, h - 220], fill=0, width=4)
        draw.rectangle([120, 300, 420, 600], outline=0, width=5)
        draw.ellipse([w - 420, 300, w - 120, 600], outline=0, width=5)

        font = self._load_font(72)
        sub_font = self._load_font(42)

        title_box = draw.textbbox((0, 0), text, font=font)
        title_width = title_box[2] - title_box[0]
        draw.text(((w - title_width) / 2, 90), text, fill=0, font=font)
        draw.text((160, 680), label, fill=0, font=sub_font)
        draw.text((160, 760), f"VCOM {self._vcom:.2f}  {w}x{h}", fill=0, font=sub_font)

        img.save("/tmp/clipboard_test_image.png")
        log.info(f"Test image saved to /tmp/clipboard_test_image.png (size={img.size})")

        return img

    def _render(self, state: dict) -> Image.Image:  # noqa: E303
        """Build a PIL image representing the current state with properly sized fonts.
        
        Uses dynamic font sizing like picker to ensure text is legible on e-paper.
        """
        img = Image.new("L", (DISPLAY_WIDTH, DISPLAY_HEIGHT), 255)
        draw = ImageDraw.Draw(img)

        knobs = state.get("knobs", [])
        buttons = state.get("buttons", {})

        # Compute font sizes relative to display height (picker pattern)
        short_dim = min(DISPLAY_WIDTH, DISPLAY_HEIGHT)
        base_font_size = max(12, int(short_dim * 0.06))  # ~6% of display
        title_font_size = int(base_font_size * 1.2)
        item_font_size = base_font_size
        
        title_font = self._load_font(title_font_size)
        item_font = self._load_font(item_font_size)

        # Title
        draw.text((40, 40), "Clanker Clipboard", fill=0, font=title_font)

        # Knobs with item font
        for i, pos in enumerate(knobs):
            y = 120 + i * 80
            draw.text((40, y), f"Knob {i + 1}: {pos}", fill=0, font=item_font)

        # Buttons with item font
        y = 120 + len(knobs) * 80 + 20
        for name, pressed in buttons.items():
            label = f"{name}: {'PRESSED' if pressed else 'open'}"
            draw.text((40, y), label, fill=0, font=item_font)
            y += 60

        return img

    def _load_font(self, size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except Exception:
            return ImageFont.load_default()

    def close(self) -> None:
        if self._display is not None:
            try:
                self._display.close()
            except Exception as exc:
                log.debug("Display close failed: %s", exc)
        log.info("ClipboardDisplay closed")
