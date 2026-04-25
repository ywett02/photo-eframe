#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import sys
import os
import logging
import argparse
from PIL import Image

# Set path for Waveshare driver
DRIVER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib')
sys.path.append(DRIVER_DIR)

from waveshare_epd import epd7in3e

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Display an image on the e-paper screen.")
    parser.add_argument("image_file", type=str, help="Path to the BMP image file")
    args = parser.parse_args()

    if not os.path.isfile(args.image_file):
        logging.error(f"File not found: {args.image_file}")
        sys.exit(1)

    logging.info("Initializing display...")
    epd = epd7in3e.EPD()
    epd.init()

    logging.info("Clearing display...")
    epd.Clear()

    logging.info(f"Loading image: {args.image_file}")
    image = Image.open(args.image_file)

    logging.info("Sending image to display...")
    epd.display(epd.getbuffer(image))

    logging.info("Done! Image will remain on screen.")
    epd7in3e.epdconfig.module_exit(cleanup=False)