"""
hw.py — Hardware abstraction for Clanker_clipboard (Raspberry Pi Zero 2W)

Reads four 8-position rotary knobs via MCP3008 ADC (resistor ladder on SPI)
and several push buttons via GPIO.

Node target: Raspberry Pi Zero 2W
"""

import logging
import os

from clipboard.env import load_project_env

log = logging.getLogger(__name__)

# Number of knobs; each has 8 positions (0–7) via resistor ladder
KNOB_COUNT = 4

# MCP3008 ADC channel assignments for each knob (0-indexed)
KNOB_CHANNELS = [0, 1, 2, 3]

# GPIO BCM pin numbers for buttons (extend as needed)
BUTTON_PINS: list[int] = []  # TODO: fill in actual GPIO pins

# ADC and ePaper follow the picker wiring: display on CE0, MCP3008 on CE1.
DEFAULT_SPI_BUS = 0
DEFAULT_SPI_DEVICE = 1


def _voltage_to_position(voltage: float, v_ref: float = 3.3, positions: int = 8) -> int:
    """Map a voltage reading to a discrete position index (0-based)."""
    step = v_ref / positions
    pos = int(voltage / step)
    return max(0, min(positions - 1, pos))


class ClipboardHardware:
    """
    Manages MCP3008 ADC (SPI) for rotary knobs and GPIO for push buttons.

    Usage::

        hw = ClipboardHardware()
        state = hw.read_state()
        # state = {"knobs": [0, 3, 7, 2], "buttons": {"gpio17": False, ...}}
        hw.close()
    """

    def __init__(
        self,
        spi_bus: int | None = None,
        spi_device: int | None = None,
        v_ref: float = 3.3,
    ) -> None:
        load_project_env()
        import spidev
        import RPi.GPIO as GPIO

        self._spi_bus = spi_bus if spi_bus is not None else int(os.getenv("MCP3008_SPI_BUS", str(DEFAULT_SPI_BUS)))
        self._spi_device = spi_device if spi_device is not None else int(os.getenv("MCP3008_SPI_DEVICE", str(DEFAULT_SPI_DEVICE)))
        self._v_ref = v_ref

        self._spi = spidev.SpiDev()
        self._spi.open(self._spi_bus, self._spi_device)
        self._spi.max_speed_hz = 1_000_000

        self._GPIO = GPIO
        GPIO.setmode(GPIO.BCM)
        for pin in BUTTON_PINS:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        log.info(
            "ClipboardHardware initialized — SPI %d.%d, %d knobs, %d buttons",
            self._spi_bus,
            self._spi_device,
            KNOB_COUNT,
            len(BUTTON_PINS),
        )

    def _read_adc(self, channel: int) -> float:
        """Read raw 10-bit value from MCP3008 channel and convert to voltage."""
        raw = self.read_raw_adc(channel)
        return (raw / 1023.0) * self._v_ref

    def read_raw_adc(self, channel: int) -> int:
        """Read raw 10-bit value from an MCP3008 channel."""
        if channel < 0 or channel > 7:
            raise ValueError(f"MCP3008 channel must be 0–7, got {channel}")
        cmd = [1, (8 + channel) << 4, 0]
        reply = self._spi.xfer2(cmd)
        return ((reply[1] & 3) << 8) | reply[2]

    def read_all_adc(self) -> list[dict[str, float | int]]:
        """Return raw and voltage readings for all MCP3008 channels."""
        readings: list[dict[str, float | int]] = []
        for channel in range(8):
            raw = self.read_raw_adc(channel)
            voltage = (raw / 1023.0) * self._v_ref
            readings.append({"channel": channel, "raw": raw, "voltage": voltage})
        return readings

    def read_state(self) -> dict:
        """Return current knob positions and button states."""
        knobs = [
            _voltage_to_position(self._read_adc(ch), self._v_ref)
            for ch in KNOB_CHANNELS
        ]
        buttons = {
            f"gpio{pin}": not self._GPIO.input(pin)  # active-low with pull-up
            for pin in BUTTON_PINS
        }
        return {"knobs": knobs, "buttons": buttons}

    def close(self) -> None:
        self._spi.close()
        self._GPIO.cleanup()
        log.info("ClipboardHardware closed")
