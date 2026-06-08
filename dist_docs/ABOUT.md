# IMAGE UTILITY

A lightweight, fast desktop tool built to handle quick image batch tasks without the RAM/VRAM overhead of Photoshop (2–4 seconds per image).

**Why it exists:** Needed a quick, nifty tool for repetitive image work — removing backgrounds, splitting spritesheets, stitching atlases. No bloat, no subscriptions, runs offline on any Windows PC.

**How it works:** (More info in `HOW_TO_USE.md` inside this folder.)

- **Background Removal:** Pick an image (or folder). Choose a model. Click. Get a PNG with transparent background in seconds. Optional **⚙ Quality** panel adds alpha matting (sharper edges for hair/fur) and alpha cleanup (removes background speckles, fills edge gaps).
- **Grid Split:** Load an image. Set rows/cols. Get individual cells cut out and saved (`cell_0_0.png`, `cell_0_1.png`, etc).
- **Atlas Creator:** Point to a folder of numbered images. Set grid size. Get a single spritesheet stitched together.
- **Image Tools:** Single-image editor — Gaussian blur, Unsharp Mask sharpen, AI upscale 2×/4× (Real-ESRGAN, fully offline, CPU), and format convert (PNG/JPG/WEBP/BMP/TIFF). Non-destructive: every operation creates a new version you can toggle between.
- **Batch Convert:** Point at a messy folder of game art → auto-classifies each file by filename (keyart / gameplay / ui / icon / video) → resizes to the right per-class format + size → optionally renames everything to a convention → writes the cleaned set to `exported/` along with a `manifest.csv`. Live dry-run preview before any writes; override the detected class for any row.

**Key features:**

- All models bundled — zero downloads ever
- CPU-only, ~633 MB total — runs anywhere
- Quality refinement controls for tricky cutouts (hair, fur, feathered edges)
- Real-time logs for debugging
- Foolproof: extract and click, it works
