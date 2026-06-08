import re
from pathlib import Path

from PIL import Image

from utils.file_helpers import IMAGE_EXTENSIONS
from utils.logger import get_logger

log = get_logger("atlas_creator")


def natural_sort_key(name):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]


def create_atlas(input_folder, rows, cols, output_path, progress_callback):
    input_folder = Path(input_folder)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(
        (f for f in input_folder.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS),
        key=lambda f: natural_sort_key(f.name),
    )
    if not files:
        raise ValueError("No image files found in the selected folder.")

    expected = rows * cols
    if len(files) < expected:
        raise ValueError(f"Need {expected} images for a {rows}x{cols} grid, but only found {len(files)}.")

    with Image.open(files[0]) as sample:
        cell_w, cell_h = sample.size
    log.info("Creating atlas %dx%d from %d files, cell size %dx%d", rows, cols, len(files), cell_w, cell_h)

    atlas = Image.new("RGBA", (cell_w * cols, cell_h * rows), (0, 0, 0, 0))

    for i, file in enumerate(files[:expected]):
        with Image.open(file) as src:
            img = src.convert("RGBA")
        if img.size != (cell_w, cell_h):
            log.warning("Resizing %s from %s to %dx%d", file.name, img.size, cell_w, cell_h)
            img = img.resize((cell_w, cell_h), Image.LANCZOS)
        row, col = divmod(i, cols)
        atlas.paste(img, (col * cell_w, row * cell_h))
        img.close()
        progress_callback(i + 1, expected)

    atlas.save(output_path)
    log.info("Atlas saved to %s (%dx%d)", output_path, atlas.width, atlas.height)
    return output_path
