import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from utils.logger import get_logger

log = get_logger("upscale")

_session_cache = {}

TILE_SIZE = 512
TILE_OVERLAP = 16
MODEL_FILENAME = "realesrgan_x4.onnx"


def _resolve_model_path(filename: str) -> Path | None:
    """Search for the ONNX model file in standard locations.
    Order: PyInstaller bundle -> project models/ -> user home models/."""
    candidates = []

    # 1. PyInstaller bundle
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "models" / filename)

    # 2. Project-local models/
    candidates.append(Path(__file__).parent.parent / "models" / filename)

    # 3. User home directory
    candidates.append(Path(os.path.expanduser("~/.image_utility/models")) / filename)

    for path in candidates:
        if path.is_file():
            log.debug("Model resolved: %s", path)
            return path

    log.warning("Model not found in any location: %s", filename)
    return None


def _get_session(scale: int = 4):
    """Load or retrieve a cached ONNX InferenceSession for Real-ESRGAN."""
    if scale in _session_cache:
        return _session_cache[scale]

    import onnxruntime as ort

    model_path = _resolve_model_path(MODEL_FILENAME)
    if model_path is None:
        raise FileNotFoundError(
            f"Real-ESRGAN model '{MODEL_FILENAME}' not found. "
            "Place it in ~/.image_utility/models/ or the project models/ directory."
        )

    opts = ort.SessionOptions()
    opts.intra_op_num_threads = os.cpu_count() or 4
    opts.inter_op_num_threads = 1
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

    log.info("Loading Real-ESRGAN session from %s (threads=%d)",
             model_path, opts.intra_op_num_threads)
    session = ort.InferenceSession(str(model_path), sess_options=opts,
                                   providers=["CPUExecutionProvider"])
    _session_cache[scale] = session
    return session


def _pad_to_tile(img_np: np.ndarray, tile_size: int) -> tuple[np.ndarray, tuple[int, int]]:
    """Pad H,W dimensions so they are divisible by tile_size.
    Returns (padded_array, (orig_h, orig_w))."""
    _, _, h, w = img_np.shape
    pad_h = (tile_size - h % tile_size) % tile_size
    pad_w = (tile_size - w % tile_size) % tile_size
    if pad_h > 0 or pad_w > 0:
        img_np = np.pad(img_np, ((0, 0), (0, 0), (0, pad_h), (0, pad_w)),
                        mode="reflect")
    return img_np, (h, w)


def _linear_blend_weights(overlap: int) -> np.ndarray:
    """Create a 1D linear ramp from 0 to 1 over `overlap` pixels."""
    return np.linspace(0.0, 1.0, overlap, dtype=np.float32)


def upscale_pil(
    pil_img: Image.Image,
    scale: int,
    progress_callback,
) -> Image.Image:
    """Tile-based Real-ESRGAN upscale of a PIL Image.

    Steps:
        1. Convert PIL to numpy float32 [0,1] in NCHW layout
        2. Pad to tile_size-divisible dimensions
        3. Split into tiles with overlap
        4. Run each tile through the ONNX session
        5. Stitch tiles with linear blending in overlap zones
        6. Crop to original_size * scale
        7. Return PIL Image
    """
    model_scale = 4  # The model always upscales 4x
    session = _get_session(model_scale)

    # 1. PIL -> numpy NCHW float32 [0,1]
    img = pil_img.convert("RGB")
    orig_w, orig_h = img.size
    arr = np.asarray(img, dtype=np.float32) / 255.0   # (H, W, 3)
    arr = np.transpose(arr, (2, 0, 1))                 # (3, H, W)
    arr = np.expand_dims(arr, axis=0)                   # (1, 3, H, W)

    # 2. Pad
    arr, (src_h, src_w) = _pad_to_tile(arr, TILE_SIZE)
    _, _, pad_h, pad_w = arr.shape

    # 3. Compute tile grid
    tiles_y = max(1, (pad_h - TILE_OVERLAP) // (TILE_SIZE - TILE_OVERLAP))
    tiles_x = max(1, (pad_w - TILE_OVERLAP) // (TILE_SIZE - TILE_OVERLAP))
    total_tiles = tiles_y * tiles_x
    log.info("Upscale %dx%d -> %dx tiles, grid %dx%d (%d tiles, tile=%d, overlap=%d)",
             orig_w, orig_h, scale, tiles_x, tiles_y, total_tiles, TILE_SIZE, TILE_OVERLAP)
    progress_callback(0, total_tiles)

    # Allocate output buffer (at model_scale)
    out_h = pad_h * model_scale
    out_w = pad_w * model_scale
    output = np.zeros((1, 3, out_h, out_w), dtype=np.float32)
    weight_map = np.zeros((1, 1, out_h, out_w), dtype=np.float32)

    blend = _linear_blend_weights(TILE_OVERLAP * model_scale)

    tile_idx = 0
    for ty in range(tiles_y):
        for tx in range(tiles_x):
            # Input tile coordinates
            y0 = ty * (TILE_SIZE - TILE_OVERLAP)
            x0 = tx * (TILE_SIZE - TILE_OVERLAP)
            y1 = min(y0 + TILE_SIZE, pad_h)
            x1 = min(x0 + TILE_SIZE, pad_w)
            y0 = max(0, y1 - TILE_SIZE)
            x0 = max(0, x1 - TILE_SIZE)

            tile_input = arr[:, :, y0:y1, x0:x1]

            # Pad tile if smaller than TILE_SIZE (edge case)
            th, tw = tile_input.shape[2], tile_input.shape[3]
            if th < TILE_SIZE or tw < TILE_SIZE:
                padded = np.zeros((1, 3, TILE_SIZE, TILE_SIZE), dtype=np.float32)
                padded[:, :, :th, :tw] = tile_input
                tile_input = padded

            # 4. Run inference
            tile_output = session.run(None, {"input": tile_input})[0]

            # Output tile coordinates (scaled)
            oy0 = y0 * model_scale
            ox0 = x0 * model_scale
            oy1 = y1 * model_scale
            ox1 = x1 * model_scale
            oth = oy1 - oy0
            otw = ox1 - ox0

            tile_result = tile_output[:, :, :oth, :otw]

            # 5. Build per-tile weight mask with linear blend in overlaps
            tile_weight = np.ones((1, 1, oth, otw), dtype=np.float32)

            # Blend top overlap
            if ty > 0:
                overlap_h = TILE_OVERLAP * model_scale
                for i in range(min(overlap_h, oth)):
                    tile_weight[:, :, i, :] *= blend[i]

            # Blend left overlap
            if tx > 0:
                overlap_w = TILE_OVERLAP * model_scale
                for j in range(min(overlap_w, otw)):
                    tile_weight[:, :, :, j] *= blend[j]

            output[:, :, oy0:oy1, ox0:ox1] += tile_result * tile_weight
            weight_map[:, :, oy0:oy1, ox0:ox1] += tile_weight

            tile_idx += 1
            progress_callback(tile_idx, total_tiles)

    # Normalise by weight map
    weight_map = np.maximum(weight_map, 1e-8)
    output /= weight_map

    # 6. Crop to original_size * model_scale
    crop_h = src_h * model_scale
    crop_w = src_w * model_scale
    output = output[:, :, :crop_h, :crop_w]

    # Convert back to uint8 PIL
    output = np.clip(output[0], 0.0, 1.0)              # (3, H, W)
    output = np.transpose(output, (1, 2, 0))            # (H, W, 3)
    output = (output * 255.0).astype(np.uint8)
    result = Image.fromarray(output, "RGB")

    # For 2x: downscale the 4x output by half
    if scale == 2:
        target_w = orig_w * 2
        target_h = orig_h * 2
        log.info("Downscaling 4x output to 2x: %dx%d", target_w, target_h)
        result = result.resize((target_w, target_h), Image.LANCZOS)
    elif scale != 4:
        # Generic fallback for other scale factors
        target_w = orig_w * scale
        target_h = orig_h * scale
        log.info("Resizing 4x output to %dx: %dx%d", scale, target_w, target_h)
        result = result.resize((target_w, target_h), Image.LANCZOS)

    log.info("Upscale complete: %dx%d", result.width, result.height)
    return result


def upscale_image(
    input_path: str,
    output_path: str,
    scale: int,
    progress_callback,
) -> None:
    """File-based wrapper: load image, upscale, save result."""
    log.info("Upscale file: %s -> %s (scale=%dx)", input_path, output_path, scale)
    img = Image.open(input_path)
    result = upscale_pil(img, scale, progress_callback)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path)
    img.close()
    result.close()
    log.info("Upscale saved: %s", output_path)


def prewarm_esrgan() -> None:
    """Pre-load the ONNX session if the model file exists."""
    if model_exists():
        _get_session(4)
        log.info("Real-ESRGAN session pre-warmed")
    else:
        log.info("Real-ESRGAN model not found; skipping prewarm")


def clear_esrgan_sessions() -> None:
    """Release all cached ONNX sessions."""
    _session_cache.clear()
    log.info("Real-ESRGAN sessions cleared")


def model_exists() -> bool:
    """Check whether the Real-ESRGAN model file can be found."""
    return _resolve_model_path(MODEL_FILENAME) is not None
