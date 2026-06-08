import os
import shutil
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image
from rembg import new_session, remove

from utils.file_helpers import IMAGE_EXTENSIONS
from utils.logger import get_logger

log = get_logger("bg_removal")
_session_cache = {}


def _post_process_alpha(img_rgba, alpha_min=10, alpha_max=230):
    """Strip weak alpha pixels (speckles) and solidify near-opaque pixels (fill edge gaps)."""
    arr = np.array(img_rgba)
    alpha = arr[..., 3].astype(np.int32)
    alpha = np.where(alpha < alpha_min, 0, alpha)
    alpha = np.where(alpha > alpha_max, 255, alpha)
    arr[..., 3] = alpha.astype(np.uint8)
    return Image.fromarray(arr)


def _bundled_models_dir():
    if hasattr(sys, "_MEIPASS"):
        candidate = Path(sys._MEIPASS) / "models"
    else:
        candidate = Path(__file__).parent.parent / "models"
    return candidate if candidate.is_dir() else None


def seed_model_cache():
    """Copy bundled .onnx models into ~/.u2net/ so rembg never needs to download.
    Safe to call multiple times — skips files that already exist."""
    bundled = _bundled_models_dir()
    if bundled is None:
        log.info("No bundled models directory found; rembg will download on demand")
        return

    cache_dir = Path(os.path.expanduser("~/.u2net"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    seeded = 0
    for onnx in bundled.glob("*.onnx"):
        target = cache_dir / onnx.name
        if not target.exists():
            log.info("Seeding model: %s -> %s", onnx.name, cache_dir)
            shutil.copy2(onnx, target)
            seeded += 1
    if seeded:
        log.info("Seeded %d model file(s) into %s", seeded, cache_dir)
    else:
        log.info("Model cache already populated at %s", cache_dir)


def model_cache_dir():
    return Path(os.environ.get("U2NET_HOME", os.path.expanduser("~/.u2net")))


def model_file_exists(model_name):
    return (model_cache_dir() / f"{model_name}.onnx").exists()


def clear_sessions():
    _session_cache.clear()


def detect_providers():
    cpu_count = os.cpu_count() or 4
    log.info("ONNX provider: CPU (%d threads available)", cpu_count)
    return ["CPUExecutionProvider"], f"CPU ({cpu_count} threads)"


def _make_session_options():
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = os.cpu_count() or 4
    opts.inter_op_num_threads = 1
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return opts


def get_session(model_name, providers):
    key = (model_name, tuple(providers))
    if key not in _session_cache:
        log.info("Creating rembg session: model=%s, providers=%s", model_name, providers)
        _session_cache[key] = new_session(
            model_name, providers=providers, sess_options=_make_session_options()
        )
    return _session_cache[key]


def prewarm(model_name="u2net"):
    """Load the default model session at startup so first BG removal is instant."""
    providers, _ = detect_providers()
    get_session(model_name, providers)
    log.info("Pre-warmed session for %s", model_name)


def process_single(input_path, output_path, session):
    with open(input_path, "rb") as f:
        result = remove(f.read(), session=session)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(result)
    log.debug("Processed: %s -> %s", input_path, output_path)


def process_single_to_pil(input_path, session, quality_params=None):
    """Remove background and return RGBA PIL image.

    quality_params dict keys (all optional):
      alpha_matting      bool  — enable trimap-based edge refinement
      fg_threshold       int   — alpha matting foreground threshold (0-255, default 240)
      bg_threshold       int   — alpha matting background threshold (0-255, default 10)
      erode_size         int   — alpha matting erode kernel size (default 10)
      post_process       bool  — strip weak/solidify strong alpha pixels
      alpha_min          int   — pixels below this alpha → 0 (default 10)
      alpha_max          int   — pixels above this alpha → 255 (default 230)
    """
    qp = quality_params or {}
    with open(input_path, "rb") as f:
        data = f.read()

    kwargs = {"session": session}
    if qp.get("alpha_matting"):
        kwargs["alpha_matting"] = True
        kwargs["alpha_matting_foreground_threshold"] = int(qp.get("fg_threshold", 240))
        kwargs["alpha_matting_background_threshold"] = int(qp.get("bg_threshold", 10))
        kwargs["alpha_matting_erode_size"] = int(qp.get("erode_size", 10))
        log.debug("Alpha matting: fg=%s bg=%s erode=%s",
                  kwargs["alpha_matting_foreground_threshold"],
                  kwargs["alpha_matting_background_threshold"],
                  kwargs["alpha_matting_erode_size"])

    result_bytes = remove(data, **kwargs)
    img = Image.open(BytesIO(result_bytes)).convert("RGBA")

    if qp.get("post_process"):
        alpha_min = int(qp.get("alpha_min", 10))
        alpha_max = int(qp.get("alpha_max", 230))
        log.debug("Post-process alpha: min=%d max=%d", alpha_min, alpha_max)
        img = _post_process_alpha(img, alpha_min=alpha_min, alpha_max=alpha_max)

    return img


def process_batch(input_folder, output_folder, model_name, providers, progress_callback,
                  quality_params=None):
    input_folder = Path(input_folder)
    output_folder = Path(output_folder)

    subfolder_name = f"{input_folder.name}_NoBG"
    actual_output = output_folder / subfolder_name
    actual_output.mkdir(parents=True, exist_ok=True)
    log.info("Batch output folder: %s", actual_output)

    files = sorted(
        f for f in input_folder.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not files:
        raise ValueError("No image files found in the selected folder.")

    log.info("Batch processing %d files with model=%s, quality_params=%s",
             len(files), model_name, quality_params)
    session = get_session(model_name, providers)

    for i, file in enumerate(files):
        out_path = actual_output / (file.stem + ".png")
        img = process_single_to_pil(file, session, quality_params=quality_params)
        img.save(out_path)
        log.debug("Saved: %s", out_path)
        progress_callback(i + 1, len(files))

    log.info("Batch complete: %d files saved to %s", len(files), actual_output)


def process_single_file(input_path, output_folder, model_name, providers, progress_callback):
    input_path = Path(input_path)
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    log.info("Single file: %s, model=%s", input_path.name, model_name)
    session = get_session(model_name, providers)
    out_path = output_folder / (input_path.stem + "_nobg.png")
    process_single(input_path, out_path, session)
    progress_callback(1, 1)
    return out_path
