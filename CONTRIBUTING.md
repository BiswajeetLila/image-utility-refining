# Contributing to Image Utility (RefiningEnabled)

Quick reference for picking up the project, hacking on it, and submitting changes.

## Prerequisites

- **Windows 10 / 11 64-bit** (only supported OS — `windnd` is Windows-only; macOS port plan in `docs/MAC_PORT_PLAN.md`, currently paused)
- **Python 3.10+** (tested on 3.13)
- **Git** + GitHub CLI (`gh`) if you'll be pushing
- **ffmpeg** *(optional)* — only needed if you test the Batch Convert video class. Install via `winget install --id Gyan.FFmpeg`. The app also offers to do this for you at runtime.
- **NVIDIA GPU** *(optional)* — `onnxruntime-gpu` gives ~5× faster BG removal. The app auto-detects and falls back to CPU.

## Local setup

```powershell
# 1. Clone
git clone https://github.com/BiswajeetLila/image-utility-refining.git
cd image-utility-refining

# 2. Virtual env
python -m venv venv
venv\Scripts\activate

# 3. Install
pip install -r requirements.txt

# 4. Fetch the big rembg models (excluded from git — >100MB each)
python download_models.py
# Puts u2net.onnx + isnet-general-use.onnx in models/

# 5. Run from source
python main.py

# 6. Run tests (43 cases, all must pass before PR)
pytest tests/ -v
```

## Build the exe

```powershell
.\venv\Scripts\python.exe -m PyInstaller build.spec --noconfirm
# Output: dist\ImageUtilityRefining\ImageUtilityRefining.exe (~640 MB bundle)
```

Or:
```powershell
.\build.bat
```

`build.bat` also syncs `HOW_TO_USE.md`, `dist_docs/ABOUT.md`, `dist_docs/CHANGELOG.md` into `dist\ImageUtilityRefining\`.

**Before rebuilding:** kill any running `ImageUtilityRefining.exe` process or PyInstaller fails on locked .pyd files.

## Project layout

```
main.py                      # Splash screen + model prewarm + stdout guard
app.py                       # CTk root window, 6-tab registry, DPI scaling, os._exit on close
tabs/
  bg_removal.py              # BG removal + ⚙ Quality panel (alpha matting + cleanup)
  grid_split.py              # rows × cols → per-cell PNG
  atlas_creator.py           # folder of images → spritesheet PNG
  image_tools.py             # Blur / Sharpen / Upscale / Convert (non-destructive)
  batch_convert.py           # Classify-by-filename → per-class resize → manifest
  log_viewer.py              # Real-time log viewer + filter
core/
  bg_worker.py               # rembg + onnxruntime + quality_params + _post_process_alpha
  grid_worker.py             # PIL grid splitting
  atlas_worker.py            # PIL atlas stitching
  image_tools_worker.py      # PIL blur/sharpen/convert
  upscale_worker.py          # Real-ESRGAN ONNX tile pipeline
  batch_convert_worker.py    # classify + plan + run_batch + ffmpeg helpers
utils/                       # drag_drop, file_helpers, logger, thread_manager
tests/test_batch_convert.py  # 43 cases for the Batch Convert pure functions
build.spec                   # PyInstaller config (windnd + PIL.ImageDraw + PIL.ImageFilter hidden)
download_models.py           # Fetch u2net.onnx + isnet-general-use.onnx (>100MB — gitignored)
models/                      # ONNX models — only realesrgan_x4 committed
```

## Where to make changes

| Area | File |
|---|---|
| BG removal quality knobs | `core/bg_worker.py` + `tabs/bg_removal.py` Quality panel |
| New tab | Make `tabs/<new>.py` + `core/<new>_worker.py`, register in `app.py` `TABS` list |
| Drag-drop bug | `utils/drag_drop.py` — top-level Tk hook + `_safe_invoke` deferral pattern |
| Batch Convert class table or naming | `core/batch_convert_worker.py` constants + tests; sync with `Image_BatchConvert` (standalone repo) and `/ai-art-set` skill's `references/export-spec.md` |
| Build / packaging | `build.spec` (hiddenimports, datas, excludes) + `build.bat` (doc sync) |
| Splash sequence | `main.py` `_do_startup()` |

## Tests

Currently only the Batch Convert worker has tests (43 cases). Adding tests for the other workers is welcome but not gating.

```powershell
pytest tests/ -v
# Expected: 43 passed
```

## Style

- Type hints on public functions in `core/*_worker.py` files.
- Pure functions stay at the top of each worker; I/O / pipeline at the bottom.
- Status-bar messages should use the existing colour palette: green `("green", "#4ade80")` for success, amber `("#d97706", "#fbbf24")` for warnings, red for errors.
- Primary action buttons (Remove Background, Split Image, Create Atlas, Apply, Save Current, Convert): desaturated terracotta orange `fg_color="#ce7e4a"`, `hover_color="#b06b3a"`.

## Branch + PR

```powershell
git checkout -b image-utility-refining/<descriptive-keywords>
# e.g. image-utility-refining/add-webp-batch-input
# e.g. image-utility-refining/fix-atlas-preview-zoom
```

(Random-slug branch names not OK.)

Commit format:
```
<short imperative subject under 72 chars>

Optional body. Why, not what.

Co-Authored-By: <if-paired-with-AI>
```

Push and open a PR via `gh pr create`. CI is manual — confirm `pytest` is green locally before requesting review.

## Sync with the standalone

A lightweight, single-feature spin-off of the Batch Convert tab lives at `https://github.com/BiswajeetLila/batch-convert` (folder: `Image_BatchConvert/`). The worker code there is a line-for-line copy of this repo's `core/batch_convert_worker.py`. Keep them in sync:

1. Land a Batch Convert change here first (where the spec lives and the tab is in context).
2. Copy `core/batch_convert_worker.py` + `tabs/batch_convert.py` over to the standalone repo.
3. Run `pytest tests/` in both.

## Releases

Tag on `main` after a green build:

```powershell
git tag -a v1.6.1 -m "Patch description"
git push origin v1.6.1
gh release create v1.6.1 .\dist\ImageUtilityRefining_v1.6.1.zip --title "v1.6.1 — <short title>" --notes-file dist_docs\CHANGELOG.md
```

## Documentation Files (DO NOT DELETE)

Two surfaces, two locations. See `CLAUDE.md` § "Documentation Files" for the canonical rules.

## Questions

Ping Biswajeet (biswajeet@lilagames.com) or open an issue on the repo.
