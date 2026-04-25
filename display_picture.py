#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import argparse
import cv2
import os
import sys
import time
import importlib
from PIL import Image
import numpy as np

# Set path for Waveshare driver
DRIVER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib')
sys.path.append(DRIVER_DIR)

def load_image(image_path):
    """Load image from specified path using OpenCV"""
    return cv2.imread(image_path)

def save_image(image_path, image):
    """Save image to specified path using OpenCV"""
    cv2.imwrite(image_path, image)

def rotate_image_if_needed(image, disp_w, disp_h):
    """Rotate image directly to match screen orientation if necessary"""
    img_h, img_w = image.shape[:2]
    print(f"Original image WxH: {img_w} x {img_h}")

    # Check if 90-degree rotation is needed
    if img_w == disp_h and img_h == disp_w:
        image = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        print(f"Image rotated 90 degrees: {image.shape[1]}x{image.shape[0]}")
    return image

def crop(image, disp_w, disp_h, intelligent=True):
    """Intelligently crop the rotated image to fit display dimensions"""
    img_h, img_w, img_c = image.shape
    print(f"Input WxH: {img_w} x {img_h}")

    img_aspect = img_w / img_h
    disp_aspect = disp_w / disp_h

    print(f"Image aspect ratio {img_aspect} ({img_w} x {img_h})")
    print(f"Display aspect ratio {disp_aspect} ({disp_w} x {disp_h})")

    # Calculate resize dimensions to maintain aspect ratio
    if img_aspect < disp_aspect:
        resize = (disp_w, int(disp_w / img_aspect))
    else:
        resize = (int(disp_h * img_aspect), disp_h)

    print(f"Resizing to {resize}")
    image = cv2.resize(image, resize)
    img_h, img_w, img_c = image.shape

    # Calculate offset for centering
    x_off = int((img_w - disp_w) / 2)
    y_off = int((img_h - disp_h) / 2)
    assert x_off == 0 or y_off == 0, "Aspect ratio calculation error"

    if intelligent:
        # Use saliency detection for smart cropping
        saliency = cv2.saliency.StaticSaliencySpectralResidual_create()
        (success, saliencyMap) = saliency.computeSaliency(image)
        saliencyMap = (saliencyMap * 255).astype("uint8")

        if not x_off:  # Vertical cropping needed
            vert = np.max(saliencyMap, axis=1)
            vert = np.convolve(vert, np.ones(64)/64, "same")  # Smooth signal
            sal_centre = int(np.argmax(vert))  # Most important vertical position
            img_centre = int(img_h / 2)
            # Adjust crop to focus on salient region
            shift_y = max(min(sal_centre - img_centre, y_off), -y_off)
            y_off += shift_y
        else:  # Horizontal cropping needed
            horiz = np.max(saliencyMap, axis=0)
            horiz = np.convolve(horiz, np.ones(64)/64, "same")  # Smooth signal
            sal_centre = int(np.argmax(horiz))  # Most important horizontal position
            img_centre = int(img_w / 2)
            # Adjust crop to focus on salient region
            shift_x = max(min(sal_centre - img_centre, x_off), -x_off)
            x_off += shift_x

    # Perform final crop
    image = image[y_off:y_off + disp_h, x_off:x_off + disp_w]
    img_h, img_w, img_c = image.shape
    print(f"Cropped WxH: {img_w} x {img_h}")
    return image

def dynamic_load_driver(display_model):
    """Dynamically load the display driver module based on model name"""
    try:
        module_name = f"waveshare_epd.epd{display_model}"
        driver_module = importlib.import_module(module_name)
        print(f"Successfully loaded {display_model} driver module: {module_name}")
        return driver_module
    except ModuleNotFoundError:
        try:
            # Alternative module naming convention
            module_name = f"waveshare_epd.{display_model}"
            driver_module = importlib.import_module(module_name)
            print(f"Successfully loaded {display_model} driver module: {module_name}")
            return driver_module
        except Exception as e:
            print(f"Error: Failed to load {display_model} driver module: {e}")
            sys.exit(1)
    except Exception as e:
        print(f"Error: Exception occurred while loading driver: {e}")
        sys.exit(1)

def display_image(epd, image, disp_w, disp_h, portrait=False):
    """Display image on e-paper using dynamically loaded driver"""
    # Rotate for portrait mode if required
    if portrait:
        image = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        print("Force rotated 90 degrees for portrait mode")
    
    # Convert color space and format for display
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(image)
    
    try:
        # Send image to display
        epd.display(epd.getbuffer(pil_img))
        time.sleep(1)  # Wait for display to complete
        
        # Put display into low-power sleep mode
        epd.sleep()
        print("Display completed successfully, screen in sleep mode")
        
    except AttributeError as e:
        print(f"Error: Driver module missing required attribute: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error during display process: {e}")
        # Ensure proper cleanup
        if hasattr(epd, 'epdconfig'):
            epd.epdconfig.module_exit()
        sys.exit(1)

if __name__ == "__main__":
    # Calculate default directory (consistent with other scripts: PaperPiAI/output_dir)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_dir = os.path.abspath(os.path.join(script_dir, "..", "output_dir"))
    
    # Default input image: output.png in default directory
    default_image = os.path.join(default_dir, "output.png")
    
    ap = argparse.ArgumentParser(description="Dynamic e-paper display image tool")
    
    # Image input with default path
    ap.add_argument(
        "image", 
        nargs='?',  # Make argument optional
        default=default_image,
        help=f"Input image path (default: {default_image})"
    )
    
    # Output directory with default path
    ap.add_argument(
        "-o", "--output", 
        default=default_dir, 
        help=f"Save cropped image to directory (default: {default_dir})"
    )
    ap.add_argument("-p", "--portrait", action="store_true", help="Portrait mode (force 90° rotation)")
    ap.add_argument("-c", "--centre_crop", action="store_true", help="Center crop instead of intelligent cropping")
    ap.add_argument("-r", "--resize_only", action="store_true", help="Only resize image without cropping")
    ap.add_argument("-s", "--simulate_display", action="store_true", help="Simulate display without actual output")
    ap.add_argument("-m", "--model", required=True, help="Display model (e.g., epd7in3e, epd5in65f)")
    ap.add_argument("--skip-fit", action="store_true", default=True, help="Skip adjustment if image size matches display exactly")
    args = vars(ap.parse_args())
    
    simulate_display = args["simulate_display"]
    display_model = args["model"]

    disp_w, disp_h = 800, 480  # Default resolution
    epd = None

    if not simulate_display:
        try:
            driver_module = dynamic_load_driver(display_model)
            epd = driver_module.EPD()
            epd.init()
            disp_w, disp_h = epd.width, epd.height
            print(f"Detected display resolution: {disp_w}x{disp_h}")
        except Exception as e:
            print(f"Failed to initialize display: {e}")
            sys.exit(1)

    # Load and process image
    image = load_image(args["image"])
    
    # Rotate image if needed
    image = rotate_image_if_needed(image, disp_w, disp_h)

    # Get image dimensions before processing
    img_h, img_w = image.shape[:2]

    # Skip processing if size matches and --skip-fit is enabled
    if args["skip_fit"] and img_w == disp_w and img_h == disp_h:
        print(f"Image size {img_w}x{img_h} matches display exactly, skipping adjustment")
    else:
        if args["resize_only"]:
            print(f"Resizing image to {disp_w}x{disp_h}")
            image = cv2.resize(image, (disp_w, disp_h))
        else:
            # Use intelligent cropping unless center crop is specified
            image = crop(image, disp_w, disp_h, not args["centre_crop"])

    # Save processed image if output directory is specified
    if args["output"]:
        # Create output directory if it doesn't exist
        os.makedirs(args["output"], exist_ok=True)
        # Generate output filename with timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_filename = f"processed_{timestamp}.png"
        output_path = os.path.join(args["output"], output_filename)
        save_image(output_path, image)
        print(f"Processed image saved to: {output_path}")

    # Display image if not in simulation mode
    if not simulate_display and epd:
        try:
            display_image(epd, image, disp_w, disp_h, args["portrait"])
        except Exception as e:
            print(f"Display error: {e}")
            if hasattr(driver_module, 'epdconfig'):
                driver_module.epdconfig.module_exit()
            sys.exit(1)