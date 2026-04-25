#!/usr/bin/env python3
import argparse
import os
import random
import subprocess
import sys

_DEFAULT_DISPLAY_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "display_picture.py")

def main():
    parser = argparse.ArgumentParser(description="Pick a random BMP and display it on the e-ink screen.")
    parser.add_argument("--image-dir", required=True,
                        help="Directory containing BMP images")
    parser.add_argument("--display-script", default=_DEFAULT_DISPLAY_SCRIPT,
                        help="Path to the display script (default: ../display_picture.py relative to this script)")
    args = parser.parse_args()

    # Get all BMP files
    images = [f for f in os.listdir(args.image_dir) if f.lower().endswith(".bmp")]

    if not images:
        print("No images found!")
        sys.exit(1)

    # Pick random image
    chosen = random.choice(images)
    image_path = os.path.join(args.image_dir, chosen)

    print(f"Selected: {image_path}")

    # Run your existing display script
    subprocess.run([
        "python3",
        args.display_script,
        image_path
    ], check=True)

    print("Display complete.")

if __name__ == "__main__":
    main()