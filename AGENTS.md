# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

This project converts images for display on a **Waveshare E6 e-ink display** (800×480 or 480×800 px).

The physical Waveshare PhotoPainter display hardware supports 6 colors: black, white, red, yellow, green, blue.

`convert.py` intentionally uses the project's current fixed 7-color software palette for generated BMPs: black, white, yellow, red, orange, blue, green. The extra orange entry is part of the current preferred converted look and is protected by the regression test. Do not remove orange or switch to direct 6-color conversion unless the goal is explicitly to change the output look. The bundled Waveshare display driver still packs images for the 6-color hardware when sending them to the frame.

## Pipeline

```bash
# Step 1: analyze and convert
python3 6ColorsConverter/analyze.py photo.jpg --apply --output photo.bmp

# Step 2: display on the e-ink screen
python3 display_picture.py photo.bmp
```

`display_picture.py` expects the image to already be sized and color-quantized by `convert.py`. It does no image processing itself.

## Scripts

### `display_picture.py` — Send image to the display

Clears the screen, loads a BMP, and sends it to the Waveshare epd7in3e display via the driver in `./lib`.

```bash
python3 display_picture.py <image_file>
```

Requires the Waveshare driver installed under `lib/` (path is resolved relative to the script).

### `piBoot/display_random_picture.py` — Pick and display a random image

Picks a random BMP from a given directory and displays it. No shutdown.

```bash
python3 piBoot/display_random_picture.py --image-dir <path>
```

### `piBoot/run_frame.py` — Boot script (display + shutdown)

Calls `display_random_picture.main()`, then waits 5 minutes and shuts down the Pi. Designed to run on boot via systemd. If `/boot/firmware/keepalive` exists, shutdown is skipped.

```bash
python3 piBoot/run_frame.py --image-dir <path>
```

---

Scripts for conversion live in `6ColorsConverter/`.

### `convert.py` — Image conversion

Resizes, enhances, and quantizes an image to the project's 7-color software palette.

```bash
python3 6ColorsConverter/convert.py <image_file> [options]
```

Key options:
- `--dir landscape|portrait` — force orientation (auto-detected from image aspect ratio if omitted)
- `--mode scale|cut` — `scale` letterboxes with white borders; `cut` crops to fill (default: `scale`)
- `--dither 0|3` — `0`=none, `3`=Floyd-Steinberg (default: `3`)
- `--saturation FLOAT` — adaptive saturation boost (default: `2.0`)
- `--contrast FLOAT` — CLAHE clip limit multiplier (default: `1.5`)
- `--sharpness FLOAT` — UnsharpMask strength post-quantization (default: `2.0`)
- `--brightness FLOAT` — local tone mapping target (default: `1.0`)
- `--gamma FLOAT` — gamma correction pre-quantization (default: `1.0`, `<1.0` brightens midtones)
- `--gamap FLOAT` — soft gamut mapping strength toward palette (0.0–1.0, default: `0.25`)
- `--lab` — use CIELAB Floyd-Steinberg dithering (requires `scikit-image`, ~60s)
- `--output PATH` — output BMP path (default: `<input>_<mode>_output.bmp`)

### `analyze.py` — Parameter recommendation

Analyzes an image and prints recommended `convert.py` parameters. Optionally runs the conversion automatically.

```bash
python3 6ColorsConverter/analyze.py <image_file> [--apply] [--output PATH]
```

`--apply` runs `convert.py` with the recommended parameters immediately.

## Enhancement Pipeline Order

`convert.py` applies enhancements in this fixed order before quantization:
1. Local tone mapping (`--brightness`)
2. CLAHE on luminance channel (`--contrast`)
3. Adaptive saturation boost (`--saturation`)
4. Soft gamut mapping (`--gamap`)
5. Gamma correction (`--gamma`)
6. Sharpening (`--sharpness`)
7. Palette quantization (PIL Floyd-Steinberg or CIELAB)

## Dependencies

- `Pillow`
- `numpy`
- `scikit-image` (optional — only needed for `--lab`)
- Waveshare e-Paper driver (installed under `lib/`, not on PyPI)
