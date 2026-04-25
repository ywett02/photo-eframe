# E-Paper Photo Frame

Convert photos on your Mac and display them on a Waveshare 7.3" E6 e-paper display connected to a Raspberry Pi Zero.

The display supports 6 colors: **black, white, red, yellow, green, blue**. Photos with bold, saturated colors look best.

---

## Requirements

**Mac** (conversion):
- Python 3
- `Pillow`, `numpy`
- `scikit-image` (optional — only needed for `--lab` dithering mode)

**Raspberry Pi** (display):
- Python 3
- `Pillow`
- Waveshare e-Paper driver library

---

## Workflow

### Step 1 — Convert the photo (on your Mac)

Let `analyze.py` examine the image and automatically choose the best conversion parameters:

```bash
python3 6ColorsConverter/analyze.py myphoto.jpg --apply --output myphoto.bmp
```

Or convert manually with `convert.py`:

```bash
python3 6ColorsConverter/convert.py myphoto.jpg --mode cut --output myphoto.bmp
```

### Step 2 — Copy to the Pi

```bash
scp myphoto.bmp <user>@<pi-hostname>:~/Pictures/
```

### Step 3 — Display on the frame (on the Pi)

```bash
python3 display_picture.py ~/Pictures/myphoto.bmp
```

The full refresh takes about 20–30 seconds — this is normal for e-paper. Once complete, the image stays on screen indefinitely with no power needed.

---

## Scripts

### `6ColorsConverter/analyze.py` — Recommended starting point

Analyzes an image (brightness, contrast, saturation, sharpness, aspect ratio) and prints the recommended `convert.py` parameters. Pass `--apply` to run the conversion immediately.

```bash
python3 6ColorsConverter/analyze.py <image_file> [--apply] [--output PATH]
```

### `6ColorsConverter/convert.py` — Image conversion

Resizes, enhances, and quantizes an image to the 6-color e-ink palette. Output is a `.bmp` file sized to 800×480 or 480×800 px.

```bash
python3 6ColorsConverter/convert.py <image_file> [options]
```

| Option | Default | Description |
|---|---|---|
| `--dir landscape\|portrait` | auto | Force orientation. Auto-detected from image dimensions if omitted. |
| `--mode scale\|cut` | `scale` | `scale`: fit whole image, may add white bars. `cut`: fill screen, may crop edges. |
| `--dither 0\|3` | `3` | `3` = Floyd-Steinberg (best quality). `0` = none. |
| `--saturation FLOAT` | `2.0` | Adaptive saturation boost. `1.0` = no change. |
| `--contrast FLOAT` | `1.5` | CLAHE local contrast multiplier. `1.0` = minimal. |
| `--sharpness FLOAT` | `2.0` | Sharpness after quantization. `1.0` = no change. |
| `--brightness FLOAT` | `1.0` | Local tone mapping target. `>1.0` = brighter. |
| `--gamma FLOAT` | `1.0` | Gamma correction. `<1.0` brightens midtones. |
| `--gamap FLOAT` | `0.25` | Soft gamut mapping strength toward palette (0.0–1.0). |
| `--lab` | off | CIELAB Floyd-Steinberg dithering. Requires `scikit-image`, ~60s. |
| `--output PATH` | `<input>_<mode>_output.bmp` | Output file path. |

**Examples:**

```bash
# Fill the whole screen (recommended for photos)
python3 6ColorsConverter/convert.py myphoto.jpg --mode cut

# Custom enhancement
python3 6ColorsConverter/convert.py myphoto.jpg --mode cut --saturation 2.5 --contrast 1.8

# Batch convert all JPGs in a folder
for f in *.jpg; do python3 6ColorsConverter/convert.py "$f" --mode cut; done
```

### `display_picture.py` — Send image to the display (run on the Pi)

Clears the screen and displays a converted BMP. The image persists on screen after the script exits.

```bash
python3 display_picture.py <image_file>
```

Requires the Waveshare driver library installed under `lib/` next to the script.

---

## Tips

- Use `--mode cut` for photos — it fills the whole screen without white bars.
- If colors look washed out, increase `--saturation` (e.g. `3.0`).
- If the image looks too dark or too bright, adjust `--brightness` or `--gamma`.
- E-paper holds its image with zero power — you can unplug the Pi after displaying.