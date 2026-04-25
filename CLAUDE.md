# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This project converts images for display on a **Waveshare E6 e-ink display** (800×480 or 480×800 px) using a fixed 7-color palette: black, white, yellow, red, orange, blue, green.

## Scripts

Both scripts live in `6ColorsConverter/`.

### `convert.py` — Image conversion

Resizes, enhances, and quantizes an image to the 6-color e-ink palette.

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