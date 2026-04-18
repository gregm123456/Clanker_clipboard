"""One-shot hardware diagnostics for Clanker_clipboard bring-up on Raspberry Pi Zero 2W."""

from __future__ import annotations

import argparse
import logging
import os
import time
from pathlib import Path

from clipboard.env import load_project_env
from clipboard.display import ClipboardDisplay
from clipboard.hw import ClipboardHardware

LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"

log = logging.getLogger(__name__)


def _device_status(path: str) -> str:
    return "present" if Path(path).exists() else "missing"


def check_spi_devices() -> int:
    """Check whether SPI device nodes exist and can be opened."""
    env_path = load_project_env()
    if env_path is not None:
        print(f"Loaded environment from {env_path}")

    print("SPI device nodes:")
    for path in ("/dev/spidev0.0", "/dev/spidev0.1"):
        print(f"  {path}: {_device_status(path)}")

    try:
        import spidev
    except Exception as exc:
        print(f"spidev import failed: {exc}")
        return 1

    failures = 0
    for device in (0, 1):
        spi = spidev.SpiDev()
        try:
            spi.open(0, device)
            spi.max_speed_hz = 1_000_000
            print(f"  open test ok: spidev0.{device}")
        except Exception as exc:
            print(f"  open test failed: spidev0.{device}: {exc}")
            failures += 1
        finally:
            try:
                spi.close()
            except Exception:
                pass

    return 1 if failures else 0


def probe_adc(samples: int, interval: float) -> int:
    """Read MCP3008 channels repeatedly and print raw and voltage values."""
    env_path = load_project_env()
    if env_path is not None:
        print(f"Loaded environment from {env_path}")

    print(
        "ADC probe: MCP3008 does not expose an identity register; success means SPI opens and readings are plausible and change when the wiring or inputs move."
    )

    hw = ClipboardHardware()
    try:
        print(
            f"Using SPI {os.getenv('MCP3008_SPI_BUS', '0')}.{os.getenv('MCP3008_SPI_DEVICE', '1')} for MCP3008"
        )
        for sample_index in range(samples):
            readings = hw.read_all_adc()
            columns = [
                f"ch{item['channel']}: raw={item['raw']:>4} v={item['voltage']:.3f}"
                for item in readings
            ]
            print(f"sample {sample_index + 1:>2}: " + " | ".join(columns))
            if sample_index + 1 < samples:
                time.sleep(interval)
    finally:
        hw.close()

    return 0


def test_epaper(text: str, clear_after: bool) -> int:
    """Attempt a simple full-screen ePaper draw."""
    env_path = load_project_env()
    if env_path is not None:
        print(f"Loaded environment from {env_path}")

    display = ClipboardDisplay()
    try:
        if not display.is_available:
            print(
                "ePaper unavailable. "
                f"SPI {display.spi_bus}.{display.spi_device} @ {display.spi_hz} Hz, "
                f"VCOM {display.vcom:.2f}."
            )
            if display.last_error:
                print(f"Driver error: {display.last_error}")
            print("Check IT8951 install, CE0 wiring, HRDY/RESET GPIO wiring, VCOM, and SPI enablement.")
            return 1

        summary = display.device_summary()
        print(
            "ePaper detected: "
            f"{summary['width']}x{summary['height']}, "
            f"firmware={summary['firmware_version']}, "
            f"lut={summary['lut_version']}, "
            f"SPI {summary['spi_bus']}.{summary['spi_device']} @ {summary['spi_hz']} Hz, "
            f"VCOM {summary['vcom']:.2f}"
        )

        print("Clearing ePaper display")
        display.clear()
        print(f"Drawing test pattern: {text}")
        display.show_test_pattern(text)
        if clear_after:
            print("Clearing ePaper display after test")
            display.clear()
        return 0
    finally:
        display.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Clanker_clipboard hardware diagnostics")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("check-spi", help="Verify SPI device nodes and open tests")

    adc_parser = subparsers.add_parser("probe-adc", help="Read all MCP3008 channels repeatedly")
    adc_parser.add_argument("--samples", type=int, default=20, help="Number of samples to print")
    adc_parser.add_argument("--interval", type=float, default=0.25, help="Seconds between samples")

    epaper_parser = subparsers.add_parser("test-epaper", help="Draw a simple full-screen test pattern")
    epaper_parser.add_argument("--text", default="CLANKER CLIPBOARD", help="Text to render")
    epaper_parser.add_argument("--clear-after", action="store_true", help="Clear the display after drawing")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    if args.command == "check-spi":
        return check_spi_devices()
    if args.command == "probe-adc":
        return probe_adc(samples=args.samples, interval=args.interval)
    if args.command == "test-epaper":
        return test_epaper(text=args.text, clear_after=args.clear_after)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())