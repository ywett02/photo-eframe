#!/usr/bin/env python3
"""Display a random picture then shut down the system."""
import subprocess
import sys
import os
import time

KEEPALIVE_FILE = "/boot/firmware/keepalive"
SHUTDOWN_DELAY_SECONDS = 5 * 60

sys.path.insert(0, os.path.dirname(__file__))
from display_random_picture import main

main()

if os.path.exists(KEEPALIVE_FILE):
    print(f"Keepalive file found at {KEEPALIVE_FILE}, skipping shutdown.")
else:
    print(f"Shutting down in {SHUTDOWN_DELAY_SECONDS // 60} minutes...")
    time.sleep(SHUTDOWN_DELAY_SECONDS)
    subprocess.run(["sudo", "shutdown", "-h", "now"])