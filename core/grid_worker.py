from pathlib import Path

from PIL import Image

from utils.logger import get_logger

log = get_logger("grid_split")


def split_grid(image_path, rows, cols, output_folder, progress_callback):
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    with Image.open(image_path) as img:
        img.load()
        w, h = img.size
        cell_w = w // cols
        cell_h = h // rows
        total = rows * cols

        log.info("Splitting %s (%dx%d) into %dx%d grid, cell size %dx%d",
                 image_path, w, h, rows, cols, cell_w, cell_h)

        for idx in range(total):
            row, col = divmod(idx, cols)
            box = (col * cell_w, row * cell_h, (col + 1) * cell_w, (row + 1) * cell_h)
            cell = img.crop(box)
            cell.save(output_folder / f"cell_{row}_{col}.png")
            cell.close()
            progress_callback(idx + 1, total)

    log.info("Grid split complete: %d cells saved to %s", total, output_folder)
