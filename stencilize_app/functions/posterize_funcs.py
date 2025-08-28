import os
import math
import random
import logging
from typing import List

import cv2
import numpy as np
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, A3, letter

# ------------------------
# Setup logging
# ------------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s'
)

# ------------------------
# Auto-level
# ------------------------
def auto_levels(image, clip_percent=0.5, per_channel=True):
    """
    Apply Auto Levels (Auto Contrast) to an image.

    Parameters:
        image (numpy.ndarray): Input image (BGR or grayscale).
        clip_percent (float): Percentage of pixels to clip from each end (default 0.5%).
        per_channel (bool): If True, apply per channel (RGB/BGR).

    Returns:
        numpy.ndarray: Image with auto levels applied.
    """
    # Ensure clip_percent is between 0 and 10
    clip_percent = max(0, min(clip_percent, 10))

    # Convert to float for precision
    img = image.copy().astype(np.float32)

    if len(img.shape) == 2 or not per_channel:
        # Process as single channel (grayscale or combined histogram)
        if len(img.shape) == 3:
            img_gray = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_BGR2GRAY)
        else:
            img_gray = img

        # Compute histogram percentiles for clipping
        hist, bins = np.histogram(img_gray.flatten(), 256, [0, 256])
        cdf = hist.cumsum()
        total_pixels = img_gray.size

        low_val = np.searchsorted(cdf, total_pixels * (clip_percent / 100))
        high_val = np.searchsorted(cdf, total_pixels * (1 - clip_percent / 100)) - 1

        # Apply scaling
        img = np.clip((img - low_val) * (255.0 / (high_val - low_val)), 0, 255)

    else:
        # Process each channel independently
        for ch in range(img.shape[2]):
            channel = img[:, :, ch]

            # Compute histogram and percentiles
            hist, bins = np.histogram(channel.flatten(), 256, [0, 256])
            cdf = hist.cumsum()
            total_pixels = channel.size

            low_val = np.searchsorted(cdf, total_pixels * (clip_percent / 100))
            high_val = np.searchsorted(cdf, total_pixels * (1 - clip_percent / 100)) - 1

            # Apply scaling to channel
            img[:, :, ch] = np.clip((channel - low_val) * (255.0 / (high_val - low_val)), 0, 255)

    return img.astype(np.uint8)

# ------------------------
# Posterize Utilities
# ------------------------

def generate_tiled_pdf(image_path: str, pdf_path: str, paper_size='A4', tiles=1, margin_mm=10, overlap_mm=0):
    """
    Split an image into multiple pages (tiles) for poster printing.

    image_path: Path to the input image
    pdf_path: Path to save the output PDF
    paper_size: 'A4', 'A3', 'Letter', 'DoubleLetter'
    tiles: Number of tiles/pages: 1, 2, 4, or 6
    margin_mm: Margin around each page in mm
    overlap_mm: Overlap between tiles in mm
    """
    logging.info(f"Generating tiled PDF: {pdf_path}")

    # Define supported paper sizes
    sizes = {
        'A4': A4,
        'A3': A3,
        'Letter': letter,
        'DoubleLetter': (2 * letter[0], letter[1])
    }

    if paper_size not in sizes:
        raise ValueError("Invalid paper size")
    page_width, page_height = sizes[paper_size]

    # Define layout (rows x columns)
    layout_options = {1: (1, 1), 2: (2, 1), 4: (2, 2), 6: (3, 2)}
    if tiles not in layout_options:
        raise ValueError("Tiles must be one of [1, 2, 4, 6]")
    rows, cols = layout_options[tiles]

    # Convert mm to points
    def mm_to_pt(mm):
        return mm * 72 / 25.4

    margin = mm_to_pt(margin_mm)
    overlap = mm_to_pt(overlap_mm)

    # Load image
    img = Image.open(image_path)
    img_width, img_height = img.size
    step_x = img_width / cols
    step_y = img_height / rows

    pdf_canvas = canvas.Canvas(pdf_path, pagesize=(page_width, page_height))
    tile_counter = 1

    for row in range(rows):
        for col in range(cols):
            # Crop image tile
            left = int(col * step_x)
            upper = int(row * step_y)
            right = int(min((col + 1) * step_x + overlap, img_width))
            lower = int(min((row + 1) * step_y + overlap, img_height))
            tile_image = img.crop((left, upper, right, lower))

            tmp_filename = f"tmp_tile_{''.join(random.choices('0123456789', k=8))}.png"
            tile_image.save(tmp_filename)

            # Compute available area on page
            avail_width = page_width - 2 * margin
            avail_height = page_height - 2 * margin

            # Maintain aspect ratio
            tile_aspect = tile_image.width / tile_image.height
            page_aspect = avail_width / avail_height
            if tile_aspect > page_aspect:
                draw_width = avail_width
                draw_height = avail_width / tile_aspect
            else:
                draw_height = avail_height
                draw_width = avail_height * tile_aspect

            x_pos = (page_width - draw_width) / 2
            y_pos = (page_height - draw_height) / 2

            # Draw tile and add label
            pdf_canvas.drawImage(tmp_filename, x_pos, y_pos, width=draw_width, height=draw_height)
            pdf_canvas.setFont("Helvetica", 12)
            pdf_canvas.drawString(margin, margin / 2, f"Tile {tile_counter} of {rows * cols}")

            draw_cut_marks(pdf_canvas, page_width, page_height, margin, 15)
            os.remove(tmp_filename)
            pdf_canvas.showPage()
            tile_counter += 1

    pdf_canvas.save()
    logging.info(f"Tiled PDF saved: {pdf_path}")


def draw_cut_marks(pdf_canvas, page_width, page_height, margin, mark_length=15):
    """Draw cut marks at all four corners of a PDF page."""
    # Top-left
    pdf_canvas.line(margin - mark_length, page_height - margin, margin, page_height - margin)
    pdf_canvas.line(margin, page_height - margin, margin, page_height - margin + mark_length)
    # Top-right
    pdf_canvas.line(page_width - margin, page_height - margin, page_width - margin + mark_length, page_height - margin)
    pdf_canvas.line(page_width - margin, page_height - margin, page_width - margin, page_height - margin + mark_length)
    # Bottom-left
    pdf_canvas.line(margin - mark_length, margin, margin, margin)
    pdf_canvas.line(margin, margin - mark_length, margin, margin)
    # Bottom-right
    pdf_canvas.line(page_width - margin, margin, page_width - margin + mark_length, margin)
    pdf_canvas.line(page_width - margin, margin - mark_length, page_width - margin, margin)


# ------------------------
# Posterize Core Functions
# ------------------------

def posterize(image: np.ndarray, layers: int, variation_strength: int = 5,blurring: int = 3) -> List[np.ndarray]:
    """Generate multiple posterized variations of an image with Gaussian blur and median filter."""
    logging.info("Converting image to grayscale")
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    logging.info("Applying Gaussian blur")
    blurred_image = cv2.GaussianBlur(gray_image, (blurring, blurring), 0)

    thresholds = np.linspace(0, 255, layers + 2)[1:-1].astype(int)
    variations = []

    for variation_idx in range(5):
        noise = np.random.normal(0, variation_strength, size=len(thresholds)).astype(int)
        varied_thresholds = np.clip(thresholds + noise, 0, 255)
        varied_thresholds = np.sort(varied_thresholds)

        result_image = np.zeros_like(blurred_image)
        prev_threshold = 0
        for t in varied_thresholds:
            result_image[(blurred_image >= prev_threshold) & (blurred_image < t)] = t
            prev_threshold = t
        result_image[blurred_image >= varied_thresholds[-1]] = 255

        result_image = cv2.medianBlur(result_image, 9)
        variations.append(result_image)

    logging.info(f"Generated {len(variations)} posterized variations")
    return variations


def generate_binary_layers(grayscale_image: np.ndarray) -> List[np.ndarray]:
    """Generate black-and-white masks for each brightness level."""
    unique_values = sorted(list(set(np.unique(grayscale_image))), reverse=True)
    logging.info(f"Unique brightness levels: {unique_values}")
    binary_layers = [np.where(grayscale_image >= level, 255, 180).astype(np.uint8) for level in unique_values]
    logging.info(f"Generated {len(binary_layers)} binary layers")
    return binary_layers



# ------------------------
# Test Posterize Workflow
# ------------------------

def posterize_main(image_path: str, layers: int,tiling: int,papersize="A4",blurring=1):
    """Posterize an image, save variations, and generate tiled PDFs for layers."""
    if not os.path.exists(image_path):
        logging.error(f"File not found: {image_path}")
        return

    logging.info(f"Reading image: {image_path}")
    img = cv2.imread(image_path)
    if img is None:
        logging.error("Unable to read image. Check file format.")
        return

    img = auto_levels(img)

    variations = posterize(img, layers,blurring)
    base_output_folder = "posterized_variations"
    os.makedirs(base_output_folder, exist_ok=True)

    for variation_idx, variation_img in enumerate(variations, start=1):
        variation_folder = os.path.join(base_output_folder, f"variation_{variation_idx}")
        os.makedirs(variation_folder, exist_ok=True)

        # Save main variation image
        variation_filename = os.path.join(variation_folder, f"posterized_version_{variation_idx}.png")
        cv2.imwrite(variation_filename, variation_img)
        logging.info(f"Saved variation: {variation_filename}")

        # Generate and save binary layers
        binary_layers = generate_binary_layers(variation_img)
        for layer_idx, layer_img in enumerate(binary_layers):
            if layer_idx < len(binary_layers) - 1:
                layer_filename = os.path.join(variation_folder, f"layer_{variation_idx}_{layer_idx}.png")
                cv2.imwrite(layer_filename, layer_img)
                logging.info(f"Saved binary layer: {layer_filename}")

                pdf_filename = os.path.join(variation_folder, f"printable_layer_{variation_idx}_{layer_idx}.pdf")
                generate_tiled_pdf(layer_filename, pdf_filename, paper_size=papersize, tiles=tiling)


# ------------------------
# Entry Point
# ------------------------
if __name__ == "__main__":
    image_path = r"C:\Users\omar_\Downloads\sample_2.jpg"
    posterize_main(image_path, layers=5,tiling=1)
