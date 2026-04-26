"""
display.py — ePaper display driver wrapper for Clanker_clipboard

Wraps the IT8951 controller driver for the 6-inch grayscale ePaper panel.
Provides simple methods for clearing the screen and rendering text/status.

Node target: Raspberry Pi Zero 2W
"""

import os
import logging
from PIL import Image, ImageDraw, ImageFont, ImageChops

from clipboard.env import load_project_env

log = logging.getLogger(__name__)

# Display resolution for the 6-inch IT8951 panel (adjust to match your panel)
DISPLAY_WIDTH = 1448
DISPLAY_HEIGHT = 1072

DEFAULT_VCOM = -2.06
DEFAULT_SPI_BUS = 0
DEFAULT_SPI_DEVICE = 0
DEFAULT_SPI_HZ = 24_000_000
DEFAULT_CMD_HZ = 1_000_000
DEFAULT_TIMEOUT_SECS = 10.0
DEFAULT_READY_PIN = 24
DEFAULT_RESET_PIN = 17
DEFAULT_TEXT_THRESHOLD = 192


class _ConfiguredEPDDisplay:
    """Small wrapper around IT8951 EPD with the AutoDisplay update logic."""

    def __init__(self, epd, auto_display_cls, constants, rotate=None, mirror=False) -> None:
        self.epd = epd
        self._constants = constants
        self._auto_display = auto_display_cls(epd.width, epd.height, rotate=rotate, mirror=mirror)

    @property
    def frame_buf(self):
        return self._auto_display.frame_buf

    @property
    def width(self) -> int:
        return self._auto_display.width

    @property
    def height(self) -> int:
        return self._auto_display.height

    def draw_full(self, mode) -> None:
        frame = self._auto_display._get_frame_buf()
        self._update(frame.tobytes(), (0, 0), self._auto_display.display_dims, mode)
        self._auto_display.prev_frame = frame

    def draw_partial(self, mode) -> None:
        """Update only the changed region between previous and current frame buffers."""
        if self._auto_display.prev_frame is None:
            self.draw_full(mode)
            return

        frame = self._auto_display._get_frame_buf()
        diff_box = ImageChops.difference(self._auto_display.prev_frame, frame).getbbox()
        if diff_box is None:
            self._auto_display.prev_frame = frame
            return

        # DU-family modes require 8-pixel alignment for controller packing.
        low_bpp_modes = {
            self._constants.DisplayModes.INIT,
            self._constants.DisplayModes.DU,
            self._constants.DisplayModes.DU4,
            self._constants.DisplayModes.A2,
        }
        round_to = 8 if mode in low_bpp_modes else 4
        minx, miny, maxx, maxy = diff_box
        minx -= minx % round_to
        maxx += round_to - 1 - (maxx - 1) % round_to
        miny -= miny % round_to
        maxy += round_to - 1 - (maxy - 1) % round_to
        diff_box = (minx, miny, maxx, maxy)

        buf = frame.crop(diff_box)
        xy = (diff_box[0], diff_box[1])
        dims = (diff_box[2] - diff_box[0], diff_box[3] - diff_box[1])
        self._update(buf.tobytes(), xy, dims, mode)
        self._auto_display.prev_frame = frame

    def clear(self) -> None:
        self.frame_buf.paste(0xFF, box=(0, 0, self.width, self.height))
        self.draw_full(self._constants.DisplayModes.INIT)

    def _update(self, data, xy, dims, mode, pixel_format=None) -> None:
        if pixel_format is None:
            pixel_format = self._constants.PixelModes.M_4BPP

        self.epd.wait_display_ready()
        self.epd.load_img_area(data, xy=xy, dims=dims, pixel_format=pixel_format)
        self.epd.display_area(xy, dims, mode)


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
        self._cmd_hz = int(os.getenv("EPAPER_CMD_HZ", str(DEFAULT_CMD_HZ)))
        self._timeout_secs = float(os.getenv("EPAPER_TIMEOUT_SECS", str(DEFAULT_TIMEOUT_SECS)))
        self._ready_pin = int(os.getenv("EPAPER_READY_PIN", str(DEFAULT_READY_PIN)))
        self._reset_pin = int(os.getenv("EPAPER_RESET_PIN", str(DEFAULT_RESET_PIN)))
        self._text_threshold = int(os.getenv("EPAPER_TEXT_THRESHOLD", str(DEFAULT_TEXT_THRESHOLD)))
        self._last_error: str | None = None

        # Import here so the module can be imported on non-Pi systems without crashing
        try:
            from IT8951.display import AutoDisplay
            from IT8951.interface import EPD
            from IT8951 import constants

            constants.Pins.HRDY = self._ready_pin
            constants.Pins.RESET = self._reset_pin

            epd = EPD(
                vcom=self._vcom,
                bus=self._spi_bus,
                device=self._spi_device,
                cmd_hz=self._cmd_hz,
                data_hz=self._spi_hz,
                timeout_secs=self._timeout_secs,
            )
            self._display = _ConfiguredEPDDisplay(epd, AutoDisplay, constants, rotate=None, mirror=False)
            self._constants = constants
            log.info(
                "ClipboardDisplay initialized — SPI %d.%d cmd=%d data=%d Hz, VCOM %.2f, timeout %.1fs, pins reset=%d ready=%d",
                self._spi_bus,
                self._spi_device,
                self._cmd_hz,
                self._spi_hz,
                self._vcom,
                self._timeout_secs,
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
            self._display_image_full(image, strategy="text")

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
    def cmd_hz(self) -> int:
        return self._cmd_hz

    @property
    def timeout_secs(self) -> float:
        return self._timeout_secs

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
                "cmd_hz": self._cmd_hz,
                "timeout_secs": self._timeout_secs,
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
            "cmd_hz": self._cmd_hz,
            "timeout_secs": self._timeout_secs,
            "ready_pin": self._ready_pin,
            "reset_pin": self._reset_pin,
        }

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
        draw.text((160, 760), f"VCOM {self._vcom:.2f}", fill=0, font=sub_font)

        if self._display is not None:
            self._display_image_full(img, strategy="text")

    def show_test_pattern_with_strategy(self, text: str, strategy: str = "text") -> None:
        """Render test pattern using a specific panel update strategy."""
        img = Image.new("L", (DISPLAY_WIDTH, DISPLAY_HEIGHT), 255)
        draw = ImageDraw.Draw(img)

        draw.rectangle([12, 12, DISPLAY_WIDTH - 12, DISPLAY_HEIGHT - 12], outline=0, width=6)
        draw.line([80, 220, DISPLAY_WIDTH - 80, 220], fill=0, width=4)
        draw.line([80, DISPLAY_HEIGHT - 220, DISPLAY_WIDTH - 80, DISPLAY_HEIGHT - 220], fill=0, width=4)

        font = self._load_font(72)
        sub_font = self._load_font(42)

        title_box = draw.textbbox((0, 0), text, font=font)
        title_width = title_box[2] - title_box[0]
        draw.text(((DISPLAY_WIDTH - title_width) / 2, 90), text, fill=0, font=font)
        draw.text((160, 680), f"Strategy: {strategy}", fill=0, font=sub_font)
        draw.text((160, 760), f"VCOM {self._vcom:.2f} threshold {self._text_threshold}", fill=0, font=sub_font)

        if self._display is not None:
            self._display_image_full(img, strategy=strategy)

    def _display_image_full(self, img: Image.Image, strategy: str = "text") -> None:
        """Prepare and send a full-frame image with strategy-specific waveform control."""
        if strategy == "image":
            prepared = self._prepare_image_grayscale(img)
        else:
            prepared = self._prepare_image_text(img)

        self._display.frame_buf.paste(prepared, [0, 0])

        if strategy == "fast":
            du_mode = getattr(self._constants.DisplayModes, "DU", None)
            if du_mode is None:
                du_mode = getattr(self._constants.DisplayModes, "GL16")
                self._display.draw_full(du_mode)
            else:
                self._display.draw_partial(du_mode)
            return

        if strategy == "image":
            gc16_mode = getattr(self._constants.DisplayModes, "GC16", None)
            if gc16_mode is None:
                gc16_mode = getattr(self._constants.DisplayModes, "GL16")
            self._display.draw_full(gc16_mode)
            return

        # Text/menu strategy modeled after picker behavior: DU partial updates.
        du_mode = getattr(self._constants.DisplayModes, "DU", None)
        if du_mode is None:
            gl16_mode = getattr(self._constants.DisplayModes, "GL16", None)
            if gl16_mode is None:
                gl16_mode = getattr(self._constants.DisplayModes, "GC16")
            self._display.draw_full(gl16_mode)
            return

        self._display.draw_partial(du_mode)

    def _prepare_image_text(self, img: Image.Image) -> Image.Image:
        """Prepare crisp black text over white for menu-like content."""
        if img.mode != "L":
            img = img.convert("L")

        resized = img.copy()
        resized.thumbnail((DISPLAY_WIDTH, DISPLAY_HEIGHT), Image.LANCZOS)

        prepared = Image.new("L", (DISPLAY_WIDTH, DISPLAY_HEIGHT), 0xFF)
        x = (DISPLAY_WIDTH - resized.width) // 2
        y = (DISPLAY_HEIGHT - resized.height) // 2
        prepared.paste(resized, (x, y))

        # Binarize for solid black text on a clean white background.
        threshold = max(0, min(255, int(self._text_threshold)))
        return prepared.point(lambda px: 0 if px < threshold else 255, mode="L")

    def _prepare_image_grayscale(self, img: Image.Image) -> Image.Image:
        """Prepare grayscale content for GC16-style full updates."""
        if img.mode != "L":
            img = img.convert("L")

        resized = img.copy()
        resized.thumbnail((DISPLAY_WIDTH, DISPLAY_HEIGHT), Image.LANCZOS)

        prepared = Image.new("L", (DISPLAY_WIDTH, DISPLAY_HEIGHT), 0xFF)
        x = (DISPLAY_WIDTH - resized.width) // 2
        y = (DISPLAY_HEIGHT - resized.height) // 2
        prepared.paste(resized, (x, y))
        return prepared

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
