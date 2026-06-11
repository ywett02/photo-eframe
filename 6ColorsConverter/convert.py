#encoding: utf-8
import sys
import os.path
import numpy as np
from PIL import Image, ImagePalette, ImageOps, ImageFilter
import argparse

# ── Palette constants (measured Waveshare E6 pigment colors) ──────────────────
PALETTE_RGB = np.array([
    [  0,   0,   0],   # black
    [255, 255, 255],   # white
    [255, 200,   0],   # yellow
    [155,  20,  10],   # red
    [210, 100,  20],   # orange
    [ 25,  55, 175],   # blue
    [ 18, 120,  40],   # green
], dtype=np.float32)

PALETTE_RGB_UINT8 = PALETTE_RGB.astype(np.uint8)

# Create an ArgumentParser object
parser = argparse.ArgumentParser(description='Process some images.')
# Add orientation parameter
parser.add_argument('image_file', type=str, help='Input image file')
parser.add_argument('--dir', choices=['landscape', 'portrait'], help='Image direction (landscape or portrait)')
parser.add_argument('--mode', choices=['scale', 'cut'], default='scale', help='Image conversion mode (scale or cut)')
parser.add_argument('--dither', type=int, choices=[Image.NONE, Image.FLOYDSTEINBERG], default=Image.FLOYDSTEINBERG, help='Image dithering algorithm (NONE(0) or FLOYDSTEINBERG(3))')
parser.add_argument('--saturation', type=float, default=2.0, help='Adaptive saturation strength — stronger boost for less-saturated pixels (1.0 = no change, default 2.0)')
parser.add_argument('--contrast', type=float, default=1.5, help='CLAHE clip limit multiplier for local contrast (1.0 = minimal, default 1.5)')
parser.add_argument('--sharpness', type=float, default=2.0, help='Sharpness enhancement applied after quantization (1.0 = no change, default 2.0)')
parser.add_argument('--brightness', type=float, default=1.0, help='Local tone mapping target (1.0 = equalize only, >1.0 = brighter target)')
parser.add_argument('--gamma', type=float, default=1.0, help='Gamma correction applied before quantization (1.0 = no change, <1.0 brightens midtones)')
parser.add_argument('--output', type=str, default=None, help='Output file path (default: <input>_<mode>_output.bmp)')
parser.add_argument('--output-dir', type=str, default=None, help='Directory to write the output BMP into (overrides the directory part of --output)')
parser.add_argument('--gamap', type=float, default=0.25, help='Soft gamut mapping strength before quantization (0.0–1.0, default 0.25)')
parser.add_argument('--lab', action='store_true', help='Use CIELAB Floyd-Steinberg dithering (requires scikit-image, slow ~60s)')
# Parse command line arguments
args = parser.parse_args()


# ── Adaptive enhancement functions ───────────────────────────────────────────

def apply_local_tone_mapping(rgb_np, brightness):
    """Adjust each pixel relative to its local neighbourhood brightness."""
    img_float   = rgb_np.astype(np.float32)
    pil_img     = Image.fromarray(rgb_np)
    blurred     = np.array(pil_img.filter(ImageFilter.GaussianBlur(radius=50)),
                           dtype=np.float32)
    global_mean = img_float.mean()
    ratio = np.ones_like(blurred)
    np.divide(global_mean * brightness, blurred, where=blurred > 0, out=ratio)
    ratio = np.clip(ratio, 0.5, 2.0)  # cap extreme corrections
    return np.clip(img_float * ratio, 0, 255).astype(np.uint8)


def apply_clahe(gray_np, contrast, tile_size=64):
    """Contrast Limited Adaptive Histogram Equalization."""
    h, w      = gray_np.shape
    grid_rows = max(2, round(h / tile_size))
    grid_cols = max(2, round(w / tile_size))
    pad_h  = (-h) % grid_rows
    pad_w  = (-w) % grid_cols
    padded = np.pad(gray_np, ((0, pad_h), (0, pad_w)), mode='reflect')
    ph, pw = padded.shape
    th, tw = ph // grid_rows, pw // grid_cols

    # Build one equalization LUT per tile
    luts = np.zeros((grid_rows, grid_cols, 256), dtype=np.float32)
    for r in range(grid_rows):
        for c in range(grid_cols):
            tile       = padded[r*th:(r+1)*th, c*tw:(c+1)*tw]
            hist, _    = np.histogram(tile, bins=256, range=(0, 256))
            clip       = max(1, int(contrast * tile.size / 256))
            excess     = int(np.sum(np.maximum(hist - clip, 0)))
            hist       = np.minimum(hist, clip)
            hist      += excess // 256
            cdf        = np.cumsum(hist).astype(np.float32)
            cdf        = (cdf - cdf.min()) / max(tile.size - cdf.min(), 1) * 255
            luts[r, c] = cdf

    # Vectorized bilinear interpolation across tile boundaries
    ys, xs = np.mgrid[0:h, 0:w]
    fy = np.clip((ys + 0.5) / th - 0.5, 0, grid_rows - 1)
    fx = np.clip((xs + 0.5) / tw - 0.5, 0, grid_cols - 1)
    r0 = np.clip(fy.astype(int),     0, grid_rows - 1)
    r1 = np.clip(r0 + 1,             0, grid_rows - 1)
    c0 = np.clip(fx.astype(int),     0, grid_cols - 1)
    c1 = np.clip(c0 + 1,             0, grid_cols - 1)
    wr = fy - r0
    wc = fx - c0
    pix    = gray_np
    result = (luts[r0, c0, pix] * (1 - wr) * (1 - wc) +
              luts[r0, c1, pix] * (1 - wr) * wc        +
              luts[r1, c0, pix] * wr        * (1 - wc) +
              luts[r1, c1, pix] * wr        * wc)
    return np.clip(result, 0, 255).astype(np.uint8)


def apply_adaptive_saturation(rgb_np, strength):
    """Boost saturation inversely proportional to existing saturation per pixel."""
    f    = rgb_np.astype(np.float32) / 255.0
    maxc = f.max(axis=2)
    minc = f.min(axis=2)
    s = np.zeros_like(maxc)
    np.divide(maxc - minc, maxc, where=maxc > 0, out=s)
    adaptive_mult = 1.0 + (strength - 1.0) * (1.0 - s)  # stronger where S is low
    new_s = np.clip(s * adaptive_mult, 0.0, 1.0)
    scale = np.ones_like(s)
    np.divide(new_s, s, where=s > 0, out=scale)
    scale = scale[..., np.newaxis]
    maxc3  = maxc[..., np.newaxis]
    result = np.clip((maxc3 - (maxc3 - f) * scale) * 255, 0, 255).astype(np.uint8)
    return result


def soft_gamut_map(rgb_np, strength=0.25):
    """Gently pull each pixel toward its nearest palette colour to reduce dither error."""
    flat    = rgb_np.reshape(-1, 3).astype(np.float32)
    dists   = np.linalg.norm(flat[:, None] - PALETTE_RGB[None], axis=2)
    nearest = PALETTE_RGB[np.argmin(dists, axis=1)]
    blended = flat + strength * (nearest - flat)
    return np.clip(blended, 0, 255).astype(np.uint8).reshape(rgb_np.shape)


def dither_lab(rgb_img, palette_lab, palette_rgb_uint8):
    """Floyd-Steinberg dithering in CIELAB perceptual colour space."""
    try:
        from skimage.color import rgb2lab
    except ImportError:
        print('Warning: scikit-image not installed, falling back to PIL quantize.')
        return None
    arr = np.array(rgb_img, dtype=np.float32) / 255.0
    lab = rgb2lab(arr)
    h, w = lab.shape[:2]
    out = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            px  = lab[y, x]
            d   = np.sum((palette_lab - px) ** 2, axis=1)
            idx = int(np.argmin(d))
            out[y, x] = palette_rgb_uint8[idx]
            err = px - palette_lab[idx]
            if x + 1 < w:
                lab[y,   x + 1] += err * (7 / 16)
            if y + 1 < h:
                if x > 0:
                    lab[y + 1, x - 1] += err * (3 / 16)
                lab[y + 1, x    ] += err * (5 / 16)
                if x + 1 < w:
                    lab[y + 1, x + 1] += err * (1 / 16)
    return Image.fromarray(out, 'RGB')


# ── Main processing ───────────────────────────────────────────────────────────

# Get input parameter
input_filename = args.image_file
display_direction = args.dir
display_mode = args.mode
display_dither = Image.Dither(args.dither)

# Check whether the input file exists
if not os.path.isfile(input_filename):
    print(f'Error: file {input_filename} does not exist')
    sys.exit(1)

# Read input image
input_image = Image.open(input_filename)

# Get the original image size
width, height = input_image.size

# Specified target size
if display_direction:
    if display_direction == 'landscape':
        target_width, target_height = 800, 480
    else:
        target_width, target_height = 480, 800
else:
    if width > height:
        target_width, target_height = 800, 480
    else:
        target_width, target_height = 480, 800

if display_mode == 'scale':
    scale_ratio = min(target_width / width, target_height / height)
    resized_width = int(width * scale_ratio)
    resized_height = int(height * scale_ratio)
    content_image = input_image.resize((resized_width, resized_height), Image.LANCZOS)
    paste_left = (target_width - resized_width) // 2
    paste_top  = (target_height - resized_height) // 2
elif display_mode == 'cut':
    img_ar = width / height
    tgt_ar = target_width / target_height
    if img_ar >= tgt_ar:
        new_w = int(height * tgt_ar)
        x0    = (width - new_w) // 2
        box   = (x0, 0, x0 + new_w, height)
    else:
        new_h = int(width / tgt_ar)
        y0    = (height - new_h) // 2
        box   = (0, y0, width, y0 + new_h)
    content_image = input_image.crop(box).resize((target_width, target_height), Image.LANCZOS)

# Adaptive enhancement pipeline — applied to image content only, before white borders are added
print(f'Enhancing image (adaptive saturation={args.saturation}, '
      f'CLAHE contrast={args.contrast}, local brightness={args.brightness}, '
      f'gamma={args.gamma})...')
content_image = content_image.convert('RGB')
rgb_np = np.array(content_image)

# 1. Local tone mapping (per-pixel brightness relative to neighbourhood)
if args.brightness != 1.0:
    rgb_np = apply_local_tone_mapping(rgb_np, args.brightness)

# 2. CLAHE on luminance channel (adaptive local contrast)
gray_np  = np.array(Image.fromarray(rgb_np).convert('L'))
clahe_np = apply_clahe(gray_np, args.contrast)
ratio    = np.ones_like(gray_np, dtype=np.float32)
np.divide(clahe_np.astype(np.float32), gray_np.astype(np.float32),
          where=gray_np > 0, out=ratio)
ratio    = ratio[..., np.newaxis]
rgb_np   = np.clip(rgb_np.astype(np.float32) * ratio, 0, 255).astype(np.uint8)

# 3. Adaptive saturation (stronger where colours are dull)
rgb_np = apply_adaptive_saturation(rgb_np, args.saturation)

# 4. Soft gamut mapping (pull pixels toward palette before quantization)
if args.gamap > 0.0:
    rgb_np = soft_gamut_map(rgb_np, args.gamap)

content_image = Image.fromarray(rgb_np)

# Paste enhanced content onto white canvas (scale mode adds letterbox borders here,
# after enhancement, so borders are guaranteed pure white)
if display_mode == 'scale':
    resized_image = Image.new('RGB', (target_width, target_height), (255, 255, 255))
    resized_image.paste(content_image, (paste_left, paste_top))
else:
    resized_image = content_image

# Apply gamma correction
if args.gamma != 1.0:
    gamma_lut = [int(pow(i / 255.0, 1.0 / args.gamma) * 255) for i in range(256)] * 3
    resized_image = resized_image.point(gamma_lut)

# Apply sharpening before quantization (avoids colour halos on palette boundaries)
if args.sharpness != 1.0:
    unsharp_percent = int((args.sharpness - 1.0) * 150)
    print(f'Sharpening image (UnsharpMask percent={unsharp_percent})...')
    resized_image = resized_image.filter(
        ImageFilter.UnsharpMask(radius=1.5, percent=unsharp_percent, threshold=3))

# Create a palette object using measured Waveshare E6 pigment colors
pal_image = Image.new("P", (1, 1))
pal_image.putpalette((
      0,   0,   0,   # black
    255, 255, 255,   # white
    255, 200,   0,   # yellow
    155,  20,  10,   # red
    210, 100,  20,   # orange
     25,  55, 175,   # blue
     18, 120,  40,   # green
) + (0, 0, 0) * 249)

# Quantize: use CIELAB dithering if --lab is set and scikit-image is available,
# otherwise fall back to PIL's RGB Floyd-Steinberg
print('Quantizing colors...')
quantized_image = None
if args.lab:
    try:
        from skimage.color import rgb2lab as _rgb2lab
        palette_lab = _rgb2lab(
            PALETTE_RGB_UINT8.reshape(1, 7, 3).astype(np.float32) / 255.0
        ).reshape(7, 3)
        quantized_image = dither_lab(resized_image, palette_lab, PALETTE_RGB_UINT8)
    except ImportError:
        print('Warning: scikit-image not installed, falling back to PIL quantize.')
if quantized_image is None:
    quantized_image = resized_image.quantize(dither=display_dither, palette=pal_image).convert('RGB')

# Save output image
output_filename = args.output if args.output else os.path.splitext(input_filename)[0] + '_' + display_mode + '_output.bmp'
if args.output_dir:
    os.makedirs(args.output_dir, exist_ok=True)
    output_filename = os.path.join(args.output_dir, os.path.basename(output_filename))
quantized_image.save(output_filename)
print(f'Successfully converted {input_filename} to {output_filename}')
