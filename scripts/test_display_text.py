#!/usr/bin/env python3
"""One-shot text render test for Clanker clipboard display.

This script is intentionally simple:
1. Initialize ClipboardDisplay.
2. Render a full-quality text test (image mode).
3. Render a fast text test (text mode).
4. Optionally clear the panel.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Ensure project root is on sys.path so 'clipboard' package is importable
# when running this script directly: python scripts/test_display_text.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clipboard.display import ClipboardDisplay

LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a text test pattern on clipboard ePaper")
    parser.add_argument("--text", default="CLANKER TEST", help="Main text to render")
    parser.add_argument("--image-delay", type=float, default=1.0, help="Seconds to wait after image-mode render")
    parser.add_argument("--text-delay", type=float, default=0.5, help="Seconds to wait after text-mode render")
    parser.add_argument("--skip-fast", action="store_true", default=True, help="Skip DU fast pass (default on — DU corrupts without prior state)")
    parser.add_argument("--with-fast", dest="skip_fast", action="store_false", help="Enable the DU fast second pass")
    parser.add_argument("--clear-after", action="store_true", help="Clear display after test")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    display = ClipboardDisplay()
    if not display.is_available:
        print(f"Display unavailable: {display.last_error}")
        return 1

    print("Display initialized")
    print(f"Rendering full-refresh test: {args.text}")
    display.show_test_pattern_with_strategy(text=args.text, strategy="image")
    time.sleep(max(0.0, args.image_delay))

    if not args.skip_fast:
        print(f"Rendering text-mode fast test: {args.text}")
        display.show_test_pattern_with_strategy(text=args.text, strategy="text")
        time.sleep(max(0.0, args.text_delay))

    if args.clear_after:
        print("Clearing display")
        display.clear()

    display.close()
    print("Done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
