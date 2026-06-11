#!/usr/bin/env python3
"""Run the one-shot random display script on a fixed interval."""
import argparse
import os
import subprocess
import sys
import time

_DEFAULT_DISPLAY_SCRIPT = os.path.join(os.path.dirname(__file__), "display_random_picture.py")
DEFAULT_INTERVAL_HOURS = 24.0


def display_once(image_dir, display_script):
    subprocess.run([
        "python3",
        display_script,
        "--image-dir",
        image_dir,
    ], check=True)


def run_frame(image_dir, display_script, interval_hours, sleeper=time.sleep):
    interval_seconds = interval_hours * 60 * 60

    while True:
        display_once(image_dir, display_script)
        print(f"Waiting {interval_hours:g} hours before next refresh...", flush=True)
        sleeper(interval_seconds)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the random picture display script on a fixed interval."
    )
    parser.add_argument("--image-dir", required=True,
                        help="Directory containing BMP images")
    parser.add_argument("--display-script", default=_DEFAULT_DISPLAY_SCRIPT,
                        help="Path to the one-shot random display script (default: ./display_random_picture.py)")
    parser.add_argument("--interval-hours", type=float, default=DEFAULT_INTERVAL_HOURS,
                        help="Hours to wait between refreshes (default: 24)")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.interval_hours <= 0:
        print("--interval-hours must be greater than 0", file=sys.stderr)
        sys.exit(1)

    run_frame(args.image_dir, args.display_script, args.interval_hours)


if __name__ == "__main__":
    main()
