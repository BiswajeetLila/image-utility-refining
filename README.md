# Image Utility (RefiningEnabled — latest)

A fast, responsive desktop app for batch image processing: background removal (with optional quality refinement), grid splitting, and atlas creation.

> **This is the current main version.** Built on top of the old Lite v1.3.1 with added BG removal quality controls (alpha matting + alpha cleanup). All previous features carry over unchanged.

## Quick Start

### Option A: Run from Source (requires Python)

1. **Clone/copy the folder** to your machine
2. **Open PowerShell** in the `Image_Editor_RefiningEnabled` folder
3. **Create a virtual environment:**
   ```powershell
   python -m venv venv
   venv\Scripts\activate
   ```
4. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```
5. **Run the app:**
   ```powershell
   python main.py
   ```

**First run:** The app shows a startup splash while it copies bundled models into your user cache (~5s, one-time).

### Option B: Use the Standalone .exe (no Python required)

1. **Download** the `ImageUtilityRefining.exe` package from releases (or build it yourself)
2. **Extract** the folder
3. **Double-click** `ImageUtilityRefining.exe`
4. Done — no installation needed

---

## Features

### 🗑️ Background Removal
- Remove backgrounds from single images or batch folders
- **Drag & drop** images directly onto the input field — instant preview on canvas
- **Model selector:** Choose the best model for your use case
  - `u2net` — General purpose, balanced quality
  - `isnet-general-use` — Sharper edges for product photos (default)
- **Before/After slider** — Compare original vs result side-by-side
- **Batch mode** — Process entire folders, outputs to `{FolderName}_NoBG` subfolder
- **⚙ Quality refinement (NEW v1.4.0)** — collapsible panel with two opt-in passes:
  - **Alpha Matting** — trimap-based edge refinement for hair/fur/feathered subjects. 3 tunable sliders (foreground/background threshold, erode size). ~3× slower.
  - **Alpha Cleanup** — numpy alpha post-process to kill background speckles and fill edge gaps. 2 sliders (min/max alpha thresholds). Negligible speed cost.
- **Fully offline** — All models bundled with the app, no downloads ever needed

### ✂️ Grid Split
- Load an image, specify rows × cols
- **Drag & drop** images — instantly shows preview with grid overlay
- Preview the grid overlay before splitting
- Exports each cell as a separate PNG
- Named `cell_{row}_{col}.png` for easy identification

### 📦 Batch Convert (NEW v1.6.0)
- **Classifies a folder of mixed game art** by filename keywords into 5 deliverable classes + concept + unknown
- **Per-class targets** matching the `/ai-art-set` skill's export spec (keyart 1600×900 / 900×1600, gameplay 1536×864 / 864×1536, ui same, icon 1024², video 720p box)
- **Two size modes** — Normalize (crop-to-fill, fixed res) or Downsize-only (long-side cap, no upscale)
- **Icon corners toggle** — squircle PNG (radius 22%) or square JPG, never mixed
- **Optional rename** to `<slug>_<class>_<NN>_<descriptor>.<ext>` convention
- **Live dry-run preview** — scrollable table with editable class dropdown per row
- **Idempotent** — already-JPG sources at target dims are byte-copied (no re-encode)
- **Reversible** — writes `manifest.csv` (old_path, new_name, class, descriptor, byte counts)
- **Video support** via system ffmpeg; auto-install via winget if missing
- **43 unit tests** in `tests/test_batch_convert.py` covering classify/resolve/crop/scaled_dims/build_name

### 🛠️ Image Tools (v1.5.0 — ported from Advanced)
- **Blur** — Gaussian blur with a single radius slider
- **Sharpen** — Unsharp Mask with radius / percent / threshold sliders
- **Upscale** — Real-ESRGAN ONNX 2×/4× tile-based AI upscale, CPU-only, fully offline
- **Convert** — PNG / JPG / WEBP / BMP / TIFF with optional quality slider
- **Non-destructive workflow** — every operation creates a version; toggle between Original / Blur / Sharpen / Upscale / Convert in the preview; Save Current writes whichever you're viewing
- **Drag & drop** input supported

### 🧩 Atlas Creator
- Load a folder of numbered images
- **Drag & drop** folders — shows image count and first image thumbnail
- Specify grid dimensions (rows × cols)
- Stitches into a single atlas/spritesheet PNG
- **Live preview** of the result after creation
- Natural sort (img10 comes after img9, not img1)

### 📋 Session Logs
- Real-time log viewer tab shows all operations
- Color-coded by level (INFO, WARNING, ERROR, DEBUG)
- Filter by keyword or log level
- Copy logs for bug reports
- Full session log saved to `logs/` folder on disk

---

## System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| **OS** | Windows 10 64-bit | Windows 10/11 64-bit |
| **RAM** | 4 GB | 8 GB+ |
| **CPU** | Any modern x64 | 4+ cores |
| **GPU** | Not required | NVIDIA (4GB+ VRAM) |
| **Disk** | 2 GB free | — |

**GPU Support:**
- ✅ **NVIDIA** → CUDA mode (fastest, ~1 sec/image with batch)
- ✅ **AMD/Intel/None** → CPU mode (slower, ~5 sec/image, but works fine)

---

## Building the .exe

If you want to create a standalone executable for your team:

1. **Install PyInstaller:**
   ```powershell
   pip install pyinstaller
   ```

2. **Run the build script:**
   ```powershell
   .\build.bat
   ```

3. **Output:** `dist\ImageUtilityRefining\` folder (~633MB)
   - Share this folder zipped with your team
   - They extract and run `ImageUtilityRefining.exe` with no setup

---

## Troubleshooting

### App won't start
- Check the logs tab for errors
- Log files are saved to `logs/` folder (see timestamp in Logs tab header)
- Share the log file when reporting issues

### Slow background removal
- **CPU mode is slow** — if you have an NVIDIA GPU, ensure `onnxruntime-gpu` is installed
- Check the Logs tab to see which provider is running (should say "GPU (CUDA)" not "CPU")

### Out of memory during batch processing
- Process smaller batches
- Close other applications to free RAM

---

## Tips & Tricks

### Background Removal
- **Product photos** → use `isnet-general-use` for crisp edges (default)
- **General purpose** → use `u2net` for a balanced all-rounder

### Grid Split
- **Spritesheets** → know the grid size before splitting (e.g., 2×3 for 6 frames)
- **Non-divisible images** → remainder pixels are cropped; the app warns you

### Atlas Creator
- **Numbered files** → Name them `img001.png`, `img002.png` etc. for proper sorting
- **Consistent sizes** → All images are resized to match the first image

---

## Reporting Issues

1. Open the **Logs** tab in the app
2. Click **Copy All** to copy the full session log
3. Share the log along with:
   - What you were trying to do
   - What went wrong
   - Your GPU (if any) and OS

---

## Documentation

Two surfaces. Engineering docs at project root; user-facing docs in `dist_docs/` (and shipped into `dist\ImageUtilityRefining\` by `build.bat`).

### Project root (engineering — NOT shipped)
| File | Purpose |
|---|---|
| `README.md` | This file. Overview + build instructions. |
| `HOW_TO_USE.md` | End-user manual. *(also shipped)* |
| `CHANGELOG.md` | Full numbered engineering changelog since v1.0.0. |
| `CLAUDE.md` | Architecture notes + gotchas for future Claude sessions. |

### `dist_docs/` → `dist\ImageUtilityRefining\` (shipped to users)
| File | Purpose |
|---|---|
| `ABOUT.md` | 10-second intro. What the app is, what each tab does. |
| `CHANGELOG.md` | Short user-facing bulleted changelog. Plain language. |

`build.bat` syncs the user docs into `dist\ImageUtilityRefining\` automatically after every PyInstaller build. The README does NOT ship.

---

## License

MIT — Free to use and modify for your team.
