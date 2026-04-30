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


def _load_epaper_config() -> dict[str, int | float]:
    return {
        "spi_bus": int(os.getenv("EPAPER_SPI_BUS", "0")),
        "spi_device": int(os.getenv("EPAPER_SPI_DEVICE", "0")),
        "spi_hz": int(os.getenv("EPAPER_SPI_HZ", "24000000")),
        "cmd_hz": int(os.getenv("EPAPER_CMD_HZ", "1000000")),
        "timeout_secs": float(os.getenv("EPAPER_TIMEOUT_SECS", "10.0")),
        "ready_pin": int(os.getenv("EPAPER_READY_PIN", "24")),
        "reset_pin": int(os.getenv("EPAPER_RESET_PIN", "17")),
        "vcom": float(os.getenv("EPAPER_VCOM", "-2.06")),
    }


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


def test_epaper(text: str, clear_after: bool, render_strategy: str) -> int:
    """Attempt a simple full-screen ePaper draw."""
    env_path = load_project_env()
    if env_path is not None:
        print(f"Loaded environment from {env_path}")

    # Show exactly which local files Python imported to avoid package shadowing confusion.
    print(f"clipboard.diagnostics path: {__file__}")
    print(f"ClipboardDisplay path: {ClipboardDisplay.__module__} -> {__import__(ClipboardDisplay.__module__, fromlist=['_']).__file__}")
    try:
        import sys
        from PIL import __version__ as pillow_version
        import IT8951
        print(f"Runtime: python={sys.version.split()[0]}, pillow={pillow_version}, IT8951={getattr(IT8951, '__version__', 'unknown')}")
    except Exception as exc:
        print(f"Runtime version probe failed: {exc}")

    display = ClipboardDisplay()
    try:
        if not display.is_available:
            print(
                "ePaper unavailable. "
                f"SPI {display.spi_bus}.{display.spi_device}, "
                f"data={display.spi_hz} Hz, VCOM {display.vcom:.2f}, "
                f"reset={display.reset_pin}, ready={display.ready_pin}."
            )
            if display.last_error:
                print(f"Driver error: {display.last_error}")
            print("Check IT8951 install, CE0 wiring, HRDY/RESET GPIO wiring, VCOM, and SPI enablement.")
            return 1

        summary = display.device_summary()
        print(
            "ePaper detected: "
            f"{summary['width']}x{summary['height']}, "
            f"VCOM {summary['vcom']:.2f}, "
            f"SPI device {summary['spi_device']}"
        )

        print("Clearing ePaper display")
        display.clear()
        print(f"Drawing test pattern: {text}")
        print(f"Render strategy: {render_strategy}")
        display.show_test_pattern_with_strategy(text=text, strategy=render_strategy)
        if clear_after:
            print("Clearing ePaper display after test")
            display.clear()
        return 0
    finally:
        display.close()


def probe_epaper_ready(duration: float, interval: float, pulse_reset: bool) -> int:
    """Read the IT8951 ready pin and optionally pulse reset before sampling."""
    env_path = load_project_env()
    if env_path is not None:
        print(f"Loaded environment from {env_path}")

    config = _load_epaper_config()

    try:
        import RPi.GPIO as GPIO
    except Exception as exc:
        print(f"RPi.GPIO import failed: {exc}")
        return 1

    ready_pin = int(config["ready_pin"])
    reset_pin = int(config["reset_pin"])

    print(
        "ePaper pin probe: "
        f"reset={reset_pin}, ready={ready_pin}, sample_window={duration:.1f}s, interval={interval:.3f}s"
    )

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(ready_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(reset_pin, GPIO.OUT, initial=GPIO.HIGH)

    try:
        initial_state = GPIO.input(ready_pin)
        print(f"Initial HRDY level: {initial_state}")

        if pulse_reset:
            print("Pulsing RESET low for 100 ms")
            GPIO.output(reset_pin, GPIO.LOW)
            time.sleep(0.1)
            GPIO.output(reset_pin, GPIO.HIGH)

        high_seen = False
        start = time.monotonic()
        while True:
            elapsed = time.monotonic() - start
            state = GPIO.input(ready_pin)
            print(f"t={elapsed:>4.1f}s HRDY={state}")
            if state:
                high_seen = True
                break
            if elapsed >= duration:
                break
            time.sleep(interval)

        if high_seen:
            print("HRDY went high. The panel is signaling ready.")
            return 0

        print("HRDY stayed low for the entire sample window.")
        return 1
    finally:
        GPIO.cleanup([ready_pin, reset_pin])


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
    epaper_parser.add_argument(
        "--render-strategy",
        choices=("text", "image", "fast"),
        default="text",
        help="Panel update strategy: text=DU partial (responsive), image=GC16 full (quality), fast=DU partial (lightning)",
    )

    ready_parser = subparsers.add_parser("probe-epaper-ready", help="Sample the IT8951 HRDY pin and optionally pulse reset")
    ready_parser.add_argument("--duration", type=float, default=12.0, help="Seconds to sample HRDY after reset")
    ready_parser.add_argument("--interval", type=float, default=0.25, help="Seconds between HRDY samples")
    ready_parser.add_argument("--no-reset-pulse", action="store_true", help="Do not pulse RESET before sampling")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    if args.command == "check-spi":
        return check_spi_devices()
    if args.command == "probe-adc":
        return probe_adc(samples=args.samples, interval=args.interval)
    if args.command == "test-epaper":
        return test_epaper(
            text=args.text,
            clear_after=args.clear_after,
            render_strategy=args.render_strategy,
        )
    if args.command == "probe-epaper-ready":
        return probe_epaper_ready(
            duration=args.duration,
            interval=args.interval,
            pulse_reset=not args.no_reset_pulse,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())