# What's New

## v1.6.0 — Batch Convert Tab
- **New tab** that turns a messy folder of game art into a clean, share-ready deliverable set.
- **Auto-classify by filename** — keyart, gameplay, ui, icon, video. Unknown files are flagged for you to assign manually.
- **Two size modes** — Normalize (every same-class file ends up at exactly the same dims, crop-to-fill) or Downsize-only (just shrink, never upscale, keep framing).
- **Icon corners** — all rounded (squircle PNG) or all square (JPG). No mixing.
- **Optional rename** — `<theme-slug>_<class>_<NN>_<descriptor>.<ext>` with auto numbering per class.
- **Preview before convert** — click **Refresh preview** to see the planned class, dims, and new name for every file. Override any unknown row with the dropdown, then Refresh again. Preview does not auto-update — tweak options freely without re-rendering.
- **Recurse subfolders** is pre-checked.
- **Writes `manifest.csv`** alongside the output so you can trace or undo.
- **Video** support — needs ffmpeg. If missing, you'll be prompted to install it via winget; or skip videos and they're copied as-is.

## v1.5.0 — Image Tools Tab
- **New Image Tools tab** between Atlas Creator and Logs.
- **Blur** — Gaussian blur with one radius slider.
- **Sharpen** — Unsharp Mask with radius, percent, and threshold sliders.
- **Upscale** — AI upscale 2× or 4× using Real-ESRGAN (CPU, all local). Tile-based — large images may take a minute.
- **Convert** — format dropdown (PNG / JPG / WEBP / BMP / TIFF) with optional quality slider.
- **Non-destructive workflow** — every operation creates a new version. Use the View toggle to flip between Original / Blur / Sharpen / Upscale / Convert. **Save Current** writes whichever version is on screen.

## v1.4.0 — Sharper Cutouts
- **New ⚙ Quality button on BG Removal.** Click to expand quality controls.
- **Alpha Matting** — turn on for sharper edges around hair, fur, and feathered subjects. About 3× slower per image, but cleaner cutouts. Three sliders let you tune the edge tightness.
- **Alpha Cleanup** — kills residual speckles in the background and fills tiny gaps along the subject edge. Two sliders: minimum alpha (speckle cutoff) and maximum alpha (solidify threshold).
- Both features are **opt-in** — defaults match the old behaviour, no change unless you flip the toggles.
- Status bar now tells you which quality modes are active during processing.

## v1.3.1
- Docs bundled with the exe folder. `ABOUT.md`, `HOW_TO_USE.md`, and this changelog ship alongside `ImageUtility.exe`.

## v1.3.0
- Orange action buttons (Remove Background, Split Image, Create Atlas) — easier to spot.
- Window resize: the image preview now takes max space; controls stay compact.
- Before/After slider scales to match the image.

## v1.2.0
- Fixed silent drag-drop crash on Grid Split / Atlas Creator.
- Drops now go to the correct active tab.
- Grid Split handles non-RGB images cleanly.

## v1.1.0
- Drag an image → it previews instantly. Same for folders on Atlas Creator.
- Default cutout model is now `isnet-general-use` (sharper edges).
- Window auto-sizes for 4K / QHD screens.
- "Remove Background" button moved to a more visible spot.

## v1.0.0
- First release. 4 tabs: BG Removal, Grid Split, Atlas Creator, Logs.
- Fully offline. All models bundled. ~633 MB total.
