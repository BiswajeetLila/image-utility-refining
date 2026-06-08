# How to Use — Image Utility

**Do not delete this file.** It is the user-facing manual. Update it whenever workflows change.

---

## Launch

Double-click `ImageUtilityRefining.exe` in `dist\ImageUtilityRefining\`. First launch shows a splash for ~5s while models seed into your user cache. No internet required.

You'll see 6 tabs across the top: **BG Removal**, **Grid Split**, **Atlas Creator**, **Image Tools**, **Batch Convert**, **Logs**.

---

## Tab 1 — BG Removal

Remove the background from one image or a whole folder.

### Single Image Workflow

1. Make sure the **Single Image** radio button is selected (default).
2. Provide the input image — either:
   - **Drag & drop** the image file anywhere onto the Input field, OR
   - Click **Browse** next to Input and pick a file.
   - As soon as the path appears, the image previews on the canvas below.
3. Set the **Output** folder the same way (drag a folder onto Output, or Browse).
4. Pick a model from the dropdown:
   - **`isnet-general-use`** (default) — sharp edges, best for product/game assets.
   - **`u2net`** — general-purpose, balanced.
5. Click **Remove Background**. Status bar shows progress.
6. When done, drag the **Before / After** slider (right under the canvas) to compare. Result PNG is saved to your Output folder as `<filename>_nobg.png`.

### Quality Refinement (NEW in v1.4.0)

If the default cutout leaves fringe haloes around hair/fur or speckle residue in the background, click the **⚙ Quality** button (right of the orange Remove Background button) to open the quality panel.

**Alpha Matting** — sharper edges, ~3× slower.
1. Tick the **Alpha Matting** checkbox.
2. Tune the three sliders if needed:
   - **Foreground threshold** (default 240) — higher = stricter foreground edge.
   - **Background threshold** (default 10) — lower = stricter background separation.
   - **Erode size** (default 10) — larger = more aggressive edge tightening.
3. Re-run **Remove Background**. The slider will show the improved result.

**Alpha Cleanup** — kills speckles, fills edge gaps. Negligible speed cost.
1. Tick the **Alpha Cleanup** checkbox.
2. Tune sliders if needed:
   - **Min alpha** (default 10) — pixels below this alpha become fully transparent. Raise if you still see ghost residue.
   - **Max alpha** (default 230) — pixels above this alpha become fully opaque. Lower if you see edge gaps.
3. Re-run **Remove Background**.

You can combine both for best results. Status bar shows which modes are active during processing (`Processing... | alpha matting ON | cleanup ON`).

The Quality panel collapses when you click ⚙ again. Settings stay until you change them.

### Batch Folder Workflow

1. Click the **Batch Folder** radio button.
2. Drag a folder onto Input (or Browse and pick one).
3. Drag the Output folder onto Output.
4. Pick a model, hit **Remove Background**.
5. All images in the input folder are processed. Results land in `<OutputFolder>/<InputFolderName>_NoBG/`.

---

## Tab 2 — Grid Split

Cut an image into a uniform rows × cols grid. Useful for spritesheets.

1. Drag an image onto **Image** (or Browse). The preview appears on the right with a red grid overlay.
2. Set **Rows** and **Cols** (defaults to 2 × 2). Click **Update Preview** to refresh the overlay.
3. Drag your destination folder onto **Output** (or Browse).
4. Click **Split Image**.
5. Each cell saves as `cell_<row>_<col>.png` in the Output folder.

The Size label tells you the original image size, each cell size, and total cell count before you split.

---

## Tab 3 — Atlas Creator

Stitch a folder full of numbered images into one big atlas / spritesheet.

1. Drag a folder of images onto **Input Folder** (or Browse). The info line tells you how many images were found, and the first image previews on the right.
2. Set **Rows** and **Cols** — must match (or exceed) the number of images. Files are placed left-to-right, top-to-bottom in natural sort order (`img1`, `img2`, ... `img10`).
3. Drag any folder onto **Output File** and edit the filename, or click **Save As**.
4. Click **Create Atlas**.
5. When complete, the stitched atlas previews on the right with a checkerboard background to show transparency.

All images are resized to match the first image's dimensions.

---

## Tab 4 — Image Tools

Non-destructive single-image editing: blur, sharpen, AI upscale, format convert. Every operation creates a new "version" you can flip to with the **View** toggle below the preview — your original is never modified. **Save Current** writes whichever version is on screen.

### Common workflow

1. Drag an image onto **Input** (or Browse). The preview shows on the canvas.
2. Pick a tool from the **Blur | Sharpen | Upscale | Convert** segmented button. Controls below it swap to match.
3. Tune the sliders.
4. Click the orange **Apply** button. The preview updates and a new version button appears in the **View** row (e.g. *Original | Blur*).
5. Repeat with more tools if needed — each one creates its own version (*Original | Blur | Sharpen | Upscale | Convert*). Click any view to flip the preview to that version.
6. Set the **Output** folder.
7. Click the orange **Save Current** button. Saves the version currently on screen as `<originalname>_<view>.png` (e.g. `photo_blur.png`).

### Blur (Gaussian)
- One slider: **Radius** (0.5 – 20, default 3.0). Larger = blurrier.

### Sharpen (Unsharp Mask)
- **Radius** (0.1 – 10, default 2.0) — pixel radius of the sharpening kernel.
- **Percent** (50 – 500, default 150) — sharpening strength.
- **Threshold** (0 – 10, default 3) — minimum brightness change before a pixel is sharpened (higher = less noise amplification).

### Upscale (AI — Real-ESRGAN, fully offline)
- **Scale**: 2× or 4×. The model upscales to 4× internally; selecting 2× downscales via LANCZOS for a cleaner mid-resolution.
- Live "Output: WxH" label shows the final resolution before you hit Apply.
- CPU-only (no GPU path). Big images can take 30 sec – 2 min depending on tile count. The progress bar shows tiles processed.
- Output is RGB — alpha channels are flattened.

### Convert (format change)
- **Format** dropdown: PNG, JPG, WEBP, BMP, TIFF.
- **Quality** slider appears for JPG and WEBP (1 – 100, default 85).
- RGBA → RGB autoflatten on white for formats that don't support alpha (JPG, BMP).
- Save uses the chosen format's extension automatically.

---

## Tab 5 — Batch Convert

Turn a messy folder of game art into a clean deliverable set. The tab classifies each file by filename keywords, resizes/recompresses per class, optionally renames everything to a convention, and writes a reversible `manifest.csv`.

### Workflow

1. Click **Browse** next to **Source** (or drag a folder onto the entry). **Recurse subfolders** is pre-checked.
2. Set **Output** (defaults to `<source>/exported/` — usually fine).
3. Pick options:
   - **Size mode**: *Normalize (fixed res)* forces every same-class file to exact target dims (crop-to-fill, may upscale small sources) — best for building a comparable test set. *Downsize-only* just shrinks oversized files, keeps framing, never upscales.
   - **Icon corners**: *All rounded (PNG)* applies an iOS-style squircle alpha mask; *All square (JPG)* keeps icons rectangular. Either way, all icons in the set get the same treatment.
   - **Rename to convention**: writes files as `<theme-slug>_<class>_<NN>_<descriptor>.<ext>`. Type your **Theme slug** (kebab-case, e.g. `wild-wild-west`).
4. Click **Refresh preview**. The table fills (dry-run — nothing written yet). Each row shows:
   - The file
   - Its detected class (dropdown — change it if it's wrong, or to handle an `unknown` row)
   - Current dims/size → planned dims/size
   - The planned new filename
5. Fix any `unknown` rows by clicking the dropdown and choosing a class, then click **Refresh preview** again to recompute names + sizes.
6. Tweak options (size mode, icon corners, rename, slug) as much as you like — **the preview does NOT auto-refresh.** Click **Refresh preview** whenever you want to see the new plan.
7. Click **Convert**. Progress bar fills as files are written. When done, the status bar shows: total in → out, % saved, per-class counts.

### Class table (what gets written)

| Class | Landscape | Portrait | Square | Format |
|---|---|---|---|---|
| keyart | 1600×900 | 900×1600 | — | JPG q80 |
| gameplay | 1536×864 | 864×1536 | — | JPG q78 (only dual-orientation class) |
| ui | 1536×864 | 864×1536 | — | JPG q80 |
| icon | — | — | 1024×1024 | PNG (rounded) or JPG (square) |
| video | — | — | — | H.264 720p box CRF 28, AAC 96k |
| concept | — | — | — | always skipped (override per row to include) |

In **Downsize-only** mode these numbers act as long-side caps instead of exact targets (no upscaling).

### Idempotent

Already-JPG sources at the target dims get byte-copied (no re-encode). Re-running on an exported folder is a near no-op.

### Video — needs ffmpeg

The header shows a green ✓ if ffmpeg is on your PATH, amber ⚠ if not. If you click Convert with videos in the batch and ffmpeg is missing, the app offers to install it via `winget` (1–3 min). Decline and videos are copied as-is.

### manifest.csv

Every Convert run writes `manifest.csv` to the output folder with columns: `old_path, new_name, class, descriptor, old_bytes, new_bytes`. Use it to trace or reverse the conversion.

---

## Tab 6 — Logs

Real-time log of everything the app is doing.

- **Filter:** type any keyword to filter rows.
- **Level dropdown:** show only INFO, WARNING, ERROR, etc.
- **Copy All:** copies the full visible log to the clipboard — paste into a bug report.
- Full session log is also saved to `logs\session_<timestamp>.log` for sharing later.

---

## Tips & Tricks

- **Drag & drop everywhere.** Every input or output field accepts a dragged file or folder. The active tab is the only one that catches drops, so switch tabs first if you have multiple open.
- **GPU vs CPU.** The badge in the top-right corner of BG Removal shows whether you're on GPU (CUDA) or CPU. Check the Logs tab on startup to confirm.
- **Closing the app.** Just hit the X. The window destroys cleanly and the process force-exits (intentional — onnxruntime keeps native threads alive otherwise).
- **Bug reports.** Always include the file from `logs\` and the steps to reproduce. Open the Logs tab → Copy All before closing the app.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| App won't launch | Check `logs\` folder for the latest `.log` file; share it. |
| "No images found in folder" | Atlas Creator expects PNG/JPG/JPEG/BMP/WEBP/TIFF. Check file extensions. |
| Background removal is slow | If you have an NVIDIA GPU, install `onnxruntime-gpu`. Logs tab tells you the active provider. |
| Drag & drop does nothing | Make sure the file actually exists. Make sure you're on the tab you want — drops only fire on the visible tab. |
| Folder locked when trying to delete | Make sure the app is fully closed (process should exit; if it didn't, end it from Task Manager). |
