#encoding: utf-8
"""
analyze.py — Analyze an image and recommend optimal convert.py parameters.

Usage:
    python3 analyze.py image.jpg
    python3 analyze.py image.jpg --apply
    python3 analyze.py image.jpg --apply --output result.bmp
"""
import sys
import os
import os.path
import argparse
import subprocess
import numpy as np
from PIL import Image, ImageFilter, ImageStat


# ── Analysis functions ────────────────────────────────────────────────────────

def get_target_size(width, height, direction):
    if direction:
        return (800, 480) if direction == 'landscape' else (480, 800)
    return (800, 480) if width > height else (480, 800)


def suggest_mode(width, height, target_w, target_h):
    img_ar  = width / height
    tgt_ar  = target_w / target_h
    ar_diff = abs(img_ar - tgt_ar) / tgt_ar
    if ar_diff < 0.15:
        return 'cut',   (f'image aspect ratio ({img_ar:.2f}) is close to the display '
                         f'({tgt_ar:.2f}), cropping loses very little')
    else:
        return 'scale', (f'image aspect ratio ({img_ar:.2f}) differs from the display '
                         f'({tgt_ar:.2f}) by {ar_diff*100:.0f}%, letterboxing avoids unwanted cropping')


def analyze_brightness(mean_l):
    if mean_l < 70:
        return 1.5,  f'mean luminance {mean_l:.1f}/255 — very dark image, strong boost needed'
    elif mean_l < 100:
        return 1.3,  f'mean luminance {mean_l:.1f}/255 — dark image, moderate boost needed'
    elif mean_l < 130:
        return 1.15, f'mean luminance {mean_l:.1f}/255 — slightly dark, small boost helps'
    elif mean_l < 175:
        return 1.0,  f'mean luminance {mean_l:.1f}/255 — well exposed, no adjustment needed'
    else:
        return 0.9,  f'mean luminance {mean_l:.1f}/255 — bright image, slight reduction helps e-ink rendering'


def analyze_contrast(stddev_l):
    if stddev_l < 30:
        return 2.5, f'luminance std dev {stddev_l:.1f} — very flat histogram, heavy contrast boost needed'
    elif stddev_l < 50:
        return 2.0, f'luminance std dev {stddev_l:.1f} — compressed tonal range, contrast boost needed'
    elif stddev_l < 65:
        return 1.5, f'luminance std dev {stddev_l:.1f} — moderate tonal range, standard boost'
    else:
        return 1.2, f'luminance std dev {stddev_l:.1f} — good tonal range, light boost only'


def analyze_saturation(rgb_img):
    w, h   = rgb_img.size
    total  = w * h
    n      = max(1, int((total / 10000) ** 0.5))
    px     = np.array(rgb_img, dtype=np.float32)[::n, ::n] / 255.0
    maxc   = px.max(axis=2)
    s      = np.where(maxc > 0, (maxc - px.min(axis=2)) / maxc, 0.0)
    mean_s = float(s.mean())
    if mean_s < 0.08:
        return 3.0, f'mean HSV saturation {mean_s:.2f} — nearly grayscale, heavy boost needed to hit colour palette'
    elif mean_s < 0.20:
        return 2.5, f'mean HSV saturation {mean_s:.2f} — low saturation, strong boost needed'
    elif mean_s < 0.35:
        return 2.0, f'mean HSV saturation {mean_s:.2f} — moderate saturation, standard boost'
    elif mean_s < 0.50:
        return 1.5, f'mean HSV saturation {mean_s:.2f} — good saturation, light boost sufficient'
    else:
        return 1.2, f'mean HSV saturation {mean_s:.2f} — already vibrant, minimal boost'


def analyze_sharpness(gray_img):
    edges     = gray_img.filter(ImageFilter.FIND_EDGES)
    mean_edge = ImageStat.Stat(edges).mean[0]
    if mean_edge < 3:
        return 3.0, f'mean edge response {mean_edge:.2f} — very blurry image, strong sharpening needed'
    elif mean_edge < 7:
        return 2.5, f'mean edge response {mean_edge:.2f} — soft image, good sharpening needed'
    elif mean_edge < 12:
        return 2.0, f'mean edge response {mean_edge:.2f} — normal sharpness, standard boost'
    else:
        return 1.5, f'mean edge response {mean_edge:.2f} — already sharp, light post-quantization crisp-up'


def analyze_gamma(gray_img):
    hist  = gray_img.histogram()
    total = sum(hist)
    if total == 0:
        return 1.0, 'empty image'
    mean     = sum(i * hist[i] for i in range(256)) / total
    variance = sum((i - mean) ** 2 * hist[i] for i in range(256)) / total
    stddev   = variance ** 0.5
    if stddev < 1e-6:
        return 1.0, 'uniform image — no gamma correction needed'
    skewness = sum((i - mean) ** 3 * hist[i] for i in range(256)) / (total * stddev ** 3)
    if skewness > 1.5:
        return 0.70, (f'histogram skewness {skewness:.2f} — heavy dark bias, '
                      'significant midtone lift will help dithering quality')
    elif skewness > 0.5:
        return 0.85, (f'histogram skewness {skewness:.2f} — dark-leaning distribution, '
                      'gentle midtone lift recommended')
    elif skewness < -0.5:
        return 1.15, (f'histogram skewness {skewness:.2f} — bright-leaning distribution, '
                      'slight midtone pull-down recommended')
    else:
        return 1.0,  (f'histogram skewness {skewness:.2f} — balanced distribution, '
                      'no gamma correction needed')


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Analyze an image and recommend optimal convert.py parameters.')
    parser.add_argument('image_file', type=str, help='Input image file')
    parser.add_argument('--dir', choices=['landscape', 'portrait'],
                        help='Force display orientation (passed through to convert.py)')
    parser.add_argument('--dither', type=int, choices=[0, 3], default=3,
                        help='Dither algorithm to pass through: 0=NONE, 3=FLOYDSTEINBERG (default 3)')
    parser.add_argument('--apply', action='store_true',
                        help='Run convert.py with the recommended parameters after analysis')
    parser.add_argument('--output', type=str, default=None,
                        help='Output file path passed to convert.py (default: <input>_<mode>_output.bmp)')
    parser.add_argument('--gamap', type=float, default=0.25,
                        help='Soft gamut mapping strength (0.0–1.0, default 0.25, passed to convert.py)')
    parser.add_argument('--lab', action='store_true',
                        help='Enable CIELAB dithering (passed to convert.py, requires scikit-image)')
    args = parser.parse_args()

    if not os.path.isfile(args.image_file):
        print(f'Error: file {args.image_file} does not exist')
        sys.exit(1)

    img           = Image.open(args.image_file)
    width, height = img.size
    target_w, target_h = get_target_size(width, height, args.dir)

    rgb  = img.convert('RGB')
    gray = img.convert('L')
    stat = ImageStat.Stat(gray)

    DIVIDER = '─' * 57

    print()
    print('=' * 57)
    print(f'  Image Analysis Report')
    print(f'  File   : {args.image_file}')
    print(f'  Size   : {width} x {height} px')
    print(f'  Target : {target_w} x {target_h} px (e-ink display)')
    print('=' * 57)

    mode,       mode_reason       = suggest_mode(width, height, target_w, target_h)
    brightness, brightness_reason = analyze_brightness(stat.mean[0])
    contrast,   contrast_reason   = analyze_contrast(stat.stddev[0])
    saturation, saturation_reason = analyze_saturation(rgb)
    sharpness,  sharpness_reason  = analyze_sharpness(gray)
    gamma,      gamma_reason      = analyze_gamma(gray)

    params = [
        ('MODE',       mode,       mode_reason),
        ('BRIGHTNESS', brightness, brightness_reason),
        ('CONTRAST',   contrast,   contrast_reason),
        ('SATURATION', saturation, saturation_reason),
        ('SHARPNESS',  sharpness,  sharpness_reason),
        ('GAMMA',      gamma,      gamma_reason),
    ]

    for name, value, reason in params:
        print()
        print(DIVIDER)
        val_str = value if isinstance(value, str) else f'{value:.2f}'.rstrip('0').rstrip('.')
        print(f'  {name:<12} →  {val_str}')
        print(f'  {reason}')

    print()
    print('=' * 57)

    # Build the convert.py command
    script_dir     = os.path.dirname(os.path.abspath(__file__))
    convert_script = os.path.join(script_dir, 'convert.py')

    cmd = [
        sys.executable, convert_script,
        args.image_file,
        '--mode',       mode,
        '--dither',     str(args.dither),
        '--brightness', f'{brightness:.2f}',
        '--contrast',   f'{contrast:.2f}',
        '--saturation', f'{saturation:.2f}',
        '--sharpness',  f'{sharpness:.2f}',
        '--gamma',      f'{gamma:.2f}',
    ]
    if args.dir:
        cmd += ['--dir', args.dir]
    if args.output:
        cmd += ['--output', args.output]
    cmd += ['--gamap', f'{args.gamap:.2f}']
    if args.lab:
        cmd += ['--lab']

    # Print human-readable command (omit interpreter + script path)
    display_cmd = 'python3 convert.py ' + ' '.join(cmd[2:])
    print()
    print('  Suggested command:')
    print()
    print(f'  {display_cmd}')
    print()
    print('=' * 57)
    print()

    if args.apply:
        print('Running conversion...')
        print()
        sys.stdout.flush()
        result = subprocess.run(cmd)
        sys.exit(result.returncode)


if __name__ == '__main__':
    main()
