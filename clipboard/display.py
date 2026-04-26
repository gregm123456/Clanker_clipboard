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

log = logging.getLogger(__name__)

# Display resolution for the 6-inch IT8951 panel (adjust to match your panel)
DISPLAY_WIDTH = 1448
DISPLAY_HEIGHT = 1072

DEFAULT_VCOM = -2.06
DEFAULT_SPI_BUS = 0
DEFAULT_SPI_DEVICE = 0
DEFAULT_SPI_HZ = 24_000_000
DEFAULT_READY_PIN = 24
DEFAULT_RESET_PIN = 17


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
        self._spi_bus = int(os.getenv("EPAPER_SPI_BUS", str(DEFAULT_SPI_BUS)))
        self._spi_device = int(os.getenv("EPAPER_SPI_DEVICE", str(DEFAULT_SPI_DEVICE)))
        self._spi_hz = int(os.getenv("EPAPER_SPI_HZ", str(DEFAULT_SPI_HZ)))
        self._ready_pin = int(os.getenv("EPAPER_READY_PIN", str(DEFAULT_READY_PIN)))
        self._reset_pin = int(os.getenv("EPAPER_RESET_PIN", str(DEFAULT_RESET_PIN)))
        self._last_error: str | None = None

        # Import here so the module can be imported on non-Pi systems without crashing.
        # Use AutoEPDDisplay directly — the same class picker uses — rather than wrapping
        # the abstract AutoDisplay base class, which has no hardware update implementation.
        try:
            from IT8951.display import AutoEPDDisplay
            from IT8951 import constants

            constants.Pins.HRDY = self._ready_pin
            constants.Pins.RESET = self._reset_pin

            self._display = AutoEPDDisplay(
                vcom=self._vcom,
                bus=self._spi_bus,
                device=self._spi_device,
                spi_hz=self._spi_hz,
            )
            self._constants = constants
            log.info(
                "ClipboardDisplay initialized — SPI %d.%d data=%d Hz, VCOM %.2f, pins reset=%d ready=%d",
                self._spi_bus,
                self._spi_device,
                self._spi_hz,
                self._vcom,
                self._reset_pin,
                self._ready_pin,
            )
        except Exception as exc:
            self._last_error = str(exc)
            log.warning("ePaper display unavailable: %s — running in headless mode", exc)
            self._display = None
            self._constants = None

    def update(self, state: dict) -> None:
        """Render current knob/button state to the ePaper display."""
        image = self._render(state)
        if self._display is not None:
            self._blit(image)

    @property
    def is_available(self) -> bool:
        return self._display is not None and self._constants is not None

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def vcom(self) -> float:
        return self._vcom

    @property
    def spi_bus(self) -> int:
        return self._spi_bus

    @property
    def spi_device(self) -> int:
        return self._spi_device

    @property
    def spi_hz(self) -> int:
        return self._spi_hz

    @property
    def ready_pin(self) -> int:
        return self._ready_pin

    @property
    def reset_pin(self) -> int:
        return self._reset_pin

    def device_summary(self) -> dict[str, str | int | float | None]:
        if self._display is None:
            return {
                "width": None,
                "height": None,
                "firmware_version": None,
                "lut_version": None,
                "vcom": self._vcom,
                "spi_bus": self._spi_bus,
                "spi_device": self._spi_device,
                "spi_hz": self._spi_hz,
                "ready_pin": self._ready_pin,
                "reset_pin": self._reset_pin,
            }

        epd = self._display.epd
        return {
            "width": epd.width,
            "height": epd.height,
            "firmware_version": getattr(epd, "firmware_version", None),
            "lut_version": getattr(epd, "lut_version", None),
            "vcom": self._vcom,
            "spi_bus": self._spi_bus,
            "spi_device": self._spi_device,
            "spi_hz": self._spi_hz,
            "ready_pin": self._ready_pin,
            "reset_pin": self._reset_pin,
        }

    def clear(self) -> None:
        """Clear the display to white if hardware is available."""
        if self._display is None:
            return
        self._display.clear()

    def _blit(self, img: Image.Image) -> None:
        """Paste img into the display frame buffer and trigger a GC16 full refresh.

        This is the same pattern picker uses: paste prepared L-mode image into
        AutoEPDDisplay.frame_buf then call draw_full(GC16).
        """
        prepared = img if img.mode == "L" else img.convert("L")
        self._display.frame_buf.paste(prepared, [0, 0])
        self._display.draw_full(self._constants.DisplayModes.GC16)

    def show_test_pattern(self, text: str = "CLANKER CLIPBOARD") -> None:
        """Render a simple full-screen test pattern for hardware bring-up."""
        if self._display is None:
            return
        img = self._build_test_image(text)
        self._blit(img)

    def show_test_pattern_with_strategy(self, text: str, strategy: str = "text") -> None:
        """Render test pattern — strategy parameter retained for CLI compatibility.

        All strategies now use the same picker-proven GC16 path via _blit().
        The strategy label is rendered in the image for visual confirmation.
        """
        if self._display is None:
            return
        img = self._build_test_image(text, label=f"strategy arg: {strategy} (GC16)")
        self._blit(img)

    def _build_test_image(self, text: str, label: str = "IT8951 GC16 full refresh") -> Image.Image:
        """Build the test pattern PIL image."""
        # Use actual panel dimensions so the image exactly fills the frame buffer.
        w = self._display.width
        h = self._display.height
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

        return img

    def _render(self, state: dict) -> Image.Image:  # noqa: E303
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
