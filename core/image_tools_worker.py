import os
from pathlib import Path

from PIL import Image, ImageFilter

from utils.logger import get_logger

log = get_logger("image_tools")

_session_cache = {}

# Formats that do not support an alpha channel
_NO_ALPHA_FORMATS = {"JPEG", "JPG", "BMP"}

# Formats that accept a quality parameter
_QUALITY_FORMATS = {"JPEG", "JPG", "WEBP"}


def _normalise_format(fmt: str) -> str:
    """Normalise user-facing format string to PIL's expected save format."""
    fmt = fmt.upper().strip().lstrip(".")
    if fmt == "JPG":
        return "JPEG"
    if fmt == "TIF":
        return "TIFF"
    return fmt


def _composite_on_white(img: Image.Image) -> Image.Image:
    """Flatten RGBA onto a white background, returning an RGB image."""
    background = Image.new("RGB", img.size, (255, 255, 255))
    background.paste(img, mask=img.split()[3])
    return background


# ── In-memory (PIL-to-PIL) helpers ──────────────────────────────────────

def apply_blur_pil(pil_img: Image.Image, radius: float) -> Image.Image:
    """Apply Gaussian blur and return a new PIL Image."""
    log.debug("Blur (in-memory): radius=%.1f, size=%s", radius, pil_img.size)
    return pil_img.filter(ImageFilter.GaussianBlur(radius=radius))


def apply_sharpen_pil(
    pil_img: Image.Image,
    radius: float,
    percent: int,
    threshold: int,
) -> Image.Image:
    """Apply UnsharpMask sharpening and return a new PIL Image."""
    log.debug("Sharpen (in-memory): radius=%.1f, percent=%d, threshold=%d, size=%s",
              radius, percent, threshold, pil_img.size)
    return pil_img.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold))


def convert_format_pil(
    pil_img: Image.Image,
    target_format: str,
) -> Image.Image:
    """Prepare a PIL Image for the target format (RGBA -> RGB compositing
    when needed). Does not save; returns the ready-to-save image."""
    fmt = _normalise_format(target_format)
    log.debug("Convert prep (in-memory): target=%s, mode=%s", fmt, pil_img.mode)
    if fmt in _NO_ALPHA_FORMATS and pil_img.mode == "RGBA":
        return _composite_on_white(pil_img)
    return pil_img.copy()


# ── File-based workers (accept progress_callback as last arg) ───────────

def apply_blur(
    input_path: str,
    output_path: str,
    radius: float,
    progress_callback,
) -> None:
    """Load an image, apply Gaussian blur, and save the result."""
    log.info("Blur: %s -> %s (radius=%.1f)", input_path, output_path, radius)
    progress_callback(0, 3)

    img = Image.open(input_path)
    progress_callback(1, 3)

    result = apply_blur_pil(img, radius)
    progress_callback(2, 3)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path)
    img.close()
    result.close()
    progress_callback(3, 3)
    log.info("Blur complete: %s", output_path)


def apply_sharpen(
    input_path: str,
    output_path: str,
    radius: float,
    percent: int,
    threshold: int,
    progress_callback,
) -> None:
    """Load an image, apply UnsharpMask sharpening, and save the result."""
    log.info("Sharpen: %s -> %s (radius=%.1f, percent=%d, threshold=%d)",
             input_path, output_path, radius, percent, threshold)
    progress_callback(0, 3)

    img = Image.open(input_path)
    progress_callback(1, 3)

    result = apply_sharpen_pil(img, radius, percent, threshold)
    progress_callback(2, 3)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path)
    img.close()
    result.close()
    progress_callback(3, 3)
    log.info("Sharpen complete: %s", output_path)


def convert_format(
    input_path: str,
    output_path: str,
    target_format: str,
    quality: int,
    progress_callback,
) -> None:
    """Convert an image to the target format (PNG/JPG/WEBP/BMP/TIFF).
    RGBA images are composited onto white for formats without alpha support.
    The quality parameter is applied for JPEG and WEBP."""
    fmt = _normalise_format(target_format)
    log.info("Convert: %s -> %s (format=%s, quality=%d)", input_path, output_path, fmt, quality)
    progress_callback(0, 3)

    img = Image.open(input_path)
    progress_callback(1, 3)

    result = convert_format_pil(img, target_format)
    progress_callback(2, 3)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    save_kwargs = {"format": fmt}
    if fmt in _QUALITY_FORMATS:
        save_kwargs["quality"] = quality
    result.save(output_path, **save_kwargs)
    img.close()
    result.close()
    progress_callback(3, 3)
    log.info("Convert complete: %s (%s)", output_path, fmt)
