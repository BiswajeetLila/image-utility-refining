# Image Utility (RefiningEnabled) — Claude Context

> **This is now the latest / main version of the Lite-line.**
> Folder `Image_Editor/` is the older v1.3.1 build. `Image_Editor_RefiningEnabled/` (this folder) is v1.4.0+ — same feature surface plus BG removal quality refinement (alpha matting + alpha cleanup). Future Lite-line changes land here.

## What This Is
Windows desktop image utility for game dev team. 6 tabs: BG Removal, Grid Split, Atlas Creator, Image Tools, Batch Convert, Logs.
Built with CustomTkinter (dark theme), rembg + ONNX Runtime for BG removal, Real-ESRGAN ONNX for upscale, PIL for image ops, ffmpeg for video (via system PATH, winget-installable).
Bundled as PyInstaller --onedir exe (~638MB). Fully offline — all models shipped, zero downloads. ffmpeg is the one optional system dep (only needed for the Batch Convert video class).

There is a separate **Advanced** version at `../Image_Editor_Advanced/` that adds the **AI Describe** tab (Florence/SmolVLM ~250 MB each + httpx). AI Describe stays Advanced-only because of the bundle weight; Image Tools was ported back into RefiningEnabled in v1.5.0.

## Architecture

```
main.py              # Splash: model prewarm (rembg + ESRGAN), stdout guard
app.py               # CTk root window, DPI scaling, tab registry, os._exit(0) on close
tabs/
  bg_removal.py      # BG removal + ⚙ Quality panel (alpha matting + alpha cleanup)
  grid_split.py      # Grid split: rows x cols, preview with grid overlay
  atlas_creator.py   # Atlas stitcher: folder of images -> spritesheet
  image_tools.py     # Blur / Sharpen / Upscale / Convert with non-destructive versions
  batch_convert.py   # Folder → classify-by-filename → per-class resize/format → manifest.csv
  log_viewer.py      # Real-time log viewer with filtering
core/
  bg_worker.py       # rembg + onnxruntime + quality_params plumbing + _post_process_alpha
  grid_worker.py     # PIL grid splitting logic
  atlas_worker.py    # PIL atlas stitching logic
  image_tools_worker.py  # PIL blur/sharpen/convert (pure-PIL, no ONNX)
  upscale_worker.py  # Real-ESRGAN ONNX tile pipeline, session cache, prewarm/clear
  batch_convert_worker.py  # classify/resolve_target/crop_to_fill/round_corners/build_name + run_batch + ffmpeg detect+install
tests/
  test_batch_convert.py  # 43 pytest cases for batch_convert pure functions (spec §9)
utils/
  drag_drop.py       # windnd-based drag & drop (Windows only, top-level window hook)
  file_helpers.py    # File dialog wrappers (ask_open_image / _folder / ask_save_image)
  logger.py          # Logging setup, file + in-memory handler
  thread_manager.py  # start_task() — threading + queue.Queue for non-blocking UI
build.spec           # PyInstaller config (windnd + PIL.ImageFilter in hiddenimports), exe name = ImageUtilityRefining
models/              # Bundled ONNX: isnet-general-use, u2net, realesrgan_x4
```

## Key Patterns

### Quality Refinement (v1.4.0)
`core/bg_worker.process_single_to_pil(input_path, session, quality_params=None)` accepts a dict:
```python
{
  "alpha_matting": bool,           # toggle rembg's trimap-based edge pass
  "fg_threshold": int,             # 0-255, default 240
  "bg_threshold": int,             # 0-255, default 10
  "erode_size":   int,             # default 10
  "post_process": bool,            # toggle numpy alpha cleanup
  "alpha_min":    int,             # below this -> 0 (transparent)
  "alpha_max":    int,             # above this -> 255 (opaque)
}
```
`_post_process_alpha(img, alpha_min, alpha_max)` does the cleanup pass; runs in same thread as `remove()`.
Batch path uses a closure inside `_start_batch()` because `start_task()` doesn't take kwargs.

### Drag & Drop
`utils/drag_drop.py` hooks the TOP-LEVEL Tk window once via `windnd.hook_dropfiles()`, then routes drops to registered widgets by mouse position or focus. This solves the customtkinter compound widget problem where child HWNDs swallow WM_DROPFILES.

- `enable_drop(widget, callback)` — register with custom callback (used for input entries that need preview)
- `enable_entry_drop(entry)` — convenience: drop fills the entry text

All 3 input tabs use custom drop handlers that fill entry AND show preview:
- BG Removal: `_on_input_drop` -> `_load_input_preview` (shows image on canvas)
- Grid Split: `_on_input_drop` -> `_load_preview` (shows image with grid overlay)
- Atlas Creator: `_on_input_drop` -> `_show_folder_info` (counts images, shows first thumbnail)

### Threading
`start_task(widget, worker_fn, args, on_progress, on_complete, on_error)` runs worker in thread, polls queue from UI thread via `widget.after()`. Worker calls `progress_cb(current, total)`. Signature does NOT take kwargs — wrap with a closure if you need to pass extra state.

### DPI Scaling
`app.py` sets `ctk.set_widget_scaling()`: 0.85 for 4K (>2000px height), 0.9 for QHD (>1440px). Window sized to 75% of screen, centered.

### App Close
`os._exit(0)` after `self.destroy()` — required because onnxruntime native threads don't exit cleanly and keep the process alive as a zombie.

## Models
- `isnet-general-use` — default BG removal, sharper edges, best for clean cutouts
- `u2net` — general purpose BG removal all-rounder
- `realesrgan_x4` — Real-ESRGAN 4x upscale ONNX (used by `core/upscale_worker.py`). Tile size 512px, 16px overlap, linear-blend stitching. CPU only.

## Batch Convert Spec
Source-of-truth doc: `imageutility-batch-convert-tab.md` (user provided). Class table + squircle policy + naming convention must stay in sync with `/ai-art-set` skill's `references/export-spec.md`. If one changes, change both.

Key constants in `core/batch_convert_worker.py`:
- `TARGETS_A` — Mode A exact crop-to-fill dims per class+orientation.
- `CAPS_B` — Mode B long-side caps per class.
- `QUALITIES` — JPG quality per class (keyart 80, gameplay 78, ui 80, concept 75).
- `_ICON_TOKENS / _UI_TOKENS / _GAMEPLAY_TOKENS / _KEYART_TOKENS / _CONCEPT_TOKENS` — keyword sets.
- `SQUIRCLE_RADIUS_PCT = 0.22`.

Run tests: `pytest tests/` from project root (uses Lite venv).

## Build
```powershell
# From venv (reuse Lite's venv to save space):
& "..\Image_Editor\venv\Scripts\python.exe" -m PyInstaller build.spec --noconfirm
# Output: dist\ImageUtilityRefining\ImageUtilityRefining.exe
```

**Before rebuilding**: kill any running `ImageUtilityRefining` process or PyInstaller will fail with PermissionError on locked .pyd files.

## Known Gotchas
- `windnd` must be in `build.spec` hiddenimports or drag-drop fails in bundled exe
- CustomTkinter CTkEntry is a compound widget (Frame > Entry) — can't hook individual widget HWNDs for drag-drop
- PyInstaller `--windowed` sets `sys.stdout`/`sys.stderr` to None — `main.py` has guards for this
- `os._exit(0)` is intentional, not a hack — onnxruntime spawns native threads that outlive Python
- `start_task()` doesn't accept kwargs — use a closure to thread `quality_params` (see `BgRemovalTab._start_batch`)
- Alpha matting requires `pymatting` (already in rembg's deps) — `build.spec` has `copy_metadata("pymatting")` for the import-time version lookup

## Mac Port
Plan drafted at `docs/MAC_PORT_PLAN.md`. Status: paused. Key blocker: windnd is Windows-only, needs platform guard or tkinterdnd2 replacement.

## Documentation Files (DO NOT DELETE)

Two surfaces, two locations. Keep them separate.

### Engineering docs — project root (NOT shipped)
- `README.md` — project overview / quick start / build instructions.
- `CHANGELOG.md` — full engineering changelog. Numbered since v1.0.0. Append on top, never rewrite.
- `CLAUDE.md` — this file. Architecture + gotchas for future Claude sessions.
- `HOW_TO_USE.md` — user manual. Lives at root AND ships to dist.

### End-user docs — `dist_docs/` (source) → `dist\ImageUtilityRefining\` (shipped)
- `dist_docs/ABOUT.md` — 10-second intro. What the app is, what each tab does.
- `dist_docs/CHANGELOG.md` — short user-facing bulleted changelog. Plain language.

`build.bat` copies `HOW_TO_USE.md`, `dist_docs\ABOUT.md`, `dist_docs\CHANGELOG.md` into `dist\ImageUtilityRefining\` after every build. README is NOT shipped.

### Rules for future changes
- New feature → update root `CHANGELOG.md` (full detail) AND `dist_docs/CHANGELOG.md` (one-line user bullet) AND `HOW_TO_USE.md` (workflow).
- Architecture change → update `CLAUDE.md`.
- New tab → also update `ABOUT.md`.
- Same structure mirrored in `../Image_Editor_Advanced/` — keep them consistent.

## Related
- Older Lite (v1.3.1, frozen reference build): `../Image_Editor/`
- Advanced version: `../Image_Editor_Advanced/` (separate codebase, separate chat sessions)
- Advanced plan: `~/.claude/plans/need-to-make-a-recursive-flute.md`
