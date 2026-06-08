# Changelog — Image Utility (RefiningEnabled)

All changes since the first approved release (v1.0.0). This is now the **latest** version, superseding the Lite build.

---

## v1.6.0 — Batch Convert tab

New tab for batch-classifying and converting messy folders of game art into the right per-class format + size, matching the export ruleset of the `/ai-art-set` skill. Designed to take a cleaned-up legacy folder and produce a deliverable set identical in spec to a freshly-generated one.

### Features
1. **Six-class filename classifier.** Token-boundary keyword match (not raw substring — `build_screen` no longer falsely hits `ui`). Classes: keyart, gameplay, ui, icon, video, concept; unmatched files become `unknown`. Tie-breakers encoded: `hud` → gameplay (not keyart); `vs`/`lineup`/`comparison` → concept; `menu`/`home`/`settings` → ui.
2. **Two size modes (toggle).** Mode A = Normalize to fixed resolution (crop-to-fill, may upscale small sources for uniformity); Mode B = Downsize-only (long-side cap, never upscale, preserves framing).
3. **Per-class targets** — keyart 1600×900 / 900×1600 JPG q80, gameplay 1536×864 / 864×1536 JPG q78 (only dual-orientation class), ui 1536×864 / 864×1536 JPG q80, icon 1024² PNG (rounded) or JPG (square), video 720p H.264 CRF 28 + AAC 96k.
4. **Icon corner toggle** — all rounded squircle (PNG, radius 22% via `PIL.ImageDraw.rounded_rectangle`) or all square (JPG). All-or-none per spec §4b — never mixed.
5. **Rename toggle + theme slug.** Outputs as `<slug>_<class>_<NN>_<descriptor>.<ext>`. NN is 2-digit per-class. Descriptor strips id prefixes (M1/K2), version tags (v2/v4), model noise (pro/gpt/edit), and pure digits. Gameplay descriptors auto-include orientation (`portrait` / `landscape`).
6. **Live dry-run preview.** Scrollable table — file, detected class (editable CTkOptionMenu per row to override unknowns), current dims+size, planned dims+est size, planned new name. Auto-refreshes on every option change. Zero writes until you click Convert.
7. **Idempotent fast path.** Already-JPG sources already at target dims are byte-copied (no re-encode). Re-running on an exported folder is a near no-op.
8. **Reversible manifest.csv** written to output dir — `old_path, new_name, class, descriptor, old_bytes, new_bytes`. Powers the size summary and lets you undo.
9. **FFmpeg integration for video.** On tab open, detects ffmpeg in PATH and shows a green ✓ or amber ⚠ badge in the header. If Convert hits videos without ffmpeg, prompts `Install ffmpeg via winget?` — runs `winget install --id Gyan.FFmpeg` in a background thread. User can also choose to skip videos (they're copied as-is).
10. **Folder skipping.** Recurse mode auto-skips intermediate folders named `subjects`, `rounded`, `ingredients`, `exported`.

### Files Added
- `core/batch_convert_worker.py` — pure functions (`classify`, `resolve_target`, `crop_to_fill`, `scaled_dims`, `round_corners`, `build_name`, `derive_descriptor`) + planning + I/O pipeline + ffmpeg helpers.
- `tabs/batch_convert.py` — UI with scrollable preview, options panel, ffmpeg badge, ffmpeg install flow.
- `tests/test_batch_convert.py` — 43 pytest cases covering all pure functions per spec §9. **All 43 pass.**
- `tests/__init__.py` — empty package marker.

### Files Changed
- `app.py` — registered `BatchConvertTab` between Image Tools and Logs (tab order: BG Removal · Grid Split · Atlas Creator · Image Tools · Batch Convert · Logs).
- `build.spec` — added `PIL.ImageDraw` to hiddenimports (used for squircle alpha mask).

### Spec Reference
Implementation follows `imageutility-batch-convert-tab.md` §§1–10. Sync target: `/ai-art-set` skill's `references/export-spec.md` — the resolve_target table, squircle policy (22%), and naming convention match exactly.

### Notes
- Concept class is **always skipped** by default (per user decision during planning). Override per-row via the Class dropdown if you want to include them.
- Output collisions: existing `exported/` files are overwritten, with a warning in the status bar.
- Tab is concept-only-no-bundle: pure Python + PIL + numpy (already shipped). No new model assets, no bundle-size impact.

### Post-ship tweaks (v1.6.0)
- **Preview no longer auto-refreshes** on every option change — it was distracting. Refresh now only fires when the user clicks **Refresh preview**. Class-dropdown overrides are stored but require a Refresh click to take visual effect (status bar nudges the user). Initial folder pick also stops auto-loading — the user clicks Refresh to load.
- **Recurse subfolders is now pre-checked** (was unchecked by default).

---

## v1.5.0 — Image Tools tab (ported from Advanced)

Brought the Image Tools facility over from `Image_Editor_Advanced/` so the RefiningEnabled build now covers BG removal + grid split + atlas creator + image editing in one exe. AI Describe stays in the Advanced version (heavier deps, separate exe).

### Features
1. **New "Image Tools" tab.** Sits between Atlas Creator and Logs. Non-destructive editing — every operation stores a result in a `_versions` dict; the View segmented button (Original / Blur / Sharpen / Upscale / Convert) toggles which version the preview shows. **Save Current** writes whichever version is on screen.
2. **Blur (Gaussian)** — `PIL.ImageFilter.GaussianBlur` with a single radius slider (0.5 – 20, default 3.0).
3. **Sharpen (Unsharp Mask)** — `PIL.ImageFilter.UnsharpMask` with three sliders: radius (0.1 – 10), percent (50 – 500), threshold (0 – 10).
4. **Upscale (Real-ESRGAN 4x ONNX)** — bundled `realesrgan_x4.onnx` (~4.7 MB). Tile-based inference (512px tiles, 16px overlap, linear-blend reconstruction). Scale segmented button: 2x or 4x. 2x downscales the 4x output via LANCZOS. CPU-only via `onnxruntime`. Output dimensions shown live next to the scale selector.
5. **Convert** — format dropdown (PNG / JPG / WEBP / BMP / TIFF). JPEG/WEBP show a Quality slider (1 – 100). RGBA → RGB images get auto-composited on white for formats that don't support alpha (JPEG, BMP).
6. **Save Current button (orange).** Saves the currently-viewed version to the output folder with a `_<view>` suffix (e.g. `photo_blur.png`, `photo_upscale.png`). Convert uses the selected format's extension.
7. **Drag-drop input.** Works the same as the other tabs — drop an image onto the Input entry and it loads instantly.
8. **ESRGAN session prewarm.** Splash screen now prewarms the upscale session if the model is present (no first-click stall on the Image Tools tab).

### Files Added
- `core/image_tools_worker.py` — pure-PIL blur/sharpen/convert (in-memory + file variants).
- `core/upscale_worker.py` — Real-ESRGAN ONNX session caching, tile pipeline, prewarm + cleanup.
- `tabs/image_tools.py` — full tab UI (tool segmented button + dynamic controls + preview canvas + view toggle + save).
- `models/realesrgan_x4.onnx` — bundled model (4.7 MB).

### Files Changed
- `app.py` — registered `ImageToolsTab`; `_on_close` now also calls `clear_esrgan_sessions()`.
- `main.py` — splash sequence checks for ESRGAN model + prewarms when present.
- `build.spec` — added `PIL.ImageFilter` to hiddenimports.

### Notes
- AI Describe NOT ported. Heavy (Florence/SmolVLM ~250 MB each + httpx/tokenizers). Stays in `Image_Editor_Advanced/`.
- Bundle size impact: +5 MB for `realesrgan_x4.onnx`. New total ~638 MB.
- Upscale uses CPU only — no GPU path. Roughly 2-5 sec/tile on a modern CPU; large images can take 30s–2min.

---

## v1.4.0 — BG Removal Quality Refinement

Built as a separate exe (`ImageUtilityRefining.exe`) in a parallel folder so we could validate it without putting the working Lite build at risk. Once verified, this becomes the new main version.

### Features
1. **Alpha matting (trimap-based edge refinement).** New optional pass inside `core/bg_worker.py` that calls `rembg.remove()` with `alpha_matting=True` plus three tunable parameters: foreground threshold (0–255), background threshold (0–100), erode size (0–40). Kills fringe haloes around hair, fur, and feathered edges. Roughly 3× slower per image — opt-in only.
2. **Post-process alpha cleanup.** New numpy-based pass after `remove()` that strips weak alpha pixels (below user-set `alpha_min`, default 10) to fully transparent and solidifies near-opaque pixels (above `alpha_max`, default 230) to fully opaque. Two effects: speckles / residual ghost pixels in the "background" region disappear, and faint gaps along the subject edge fill in.
3. **Quality settings panel — collapsible.** New `⚙ Quality` toggle button in BG Removal tab, sitting beside the orange Remove Background button. Click to expand a panel with the alpha matting + cleanup sections; each has its own enable checkbox and slider group. Sliders grey out when their section is disabled. Status bar shows which modes are active during processing (e.g. `Processing... | alpha matting ON | cleanup ON`).
4. **Quality params thread through batch mode.** Both single-image and batch paths now route through `process_single_to_pil()` with a `quality_params` dict so refinement applies consistently. Batch path uses a closure (kept `thread_manager.start_task()` signature unchanged).

### Files Changed
- `core/bg_worker.py` — added `numpy` import, `_post_process_alpha()` helper, `quality_params` plumbing through `process_single_to_pil()` and `process_batch()`.
- `tabs/bg_removal.py` — full UI restructure with Quality button, collapsible panel, two checkbox+slider sections, status-line summary, closure-based batch worker.
- `build.spec` — exe name `ImageUtility` → `ImageUtilityRefining`.
- `build.bat` — dist folder path updated to `dist\ImageUtilityRefining\`.

### Notes
- All existing Lite features carry over unchanged — drag-and-drop, before/after slider, model selector, batch mode, DPI scaling, dark theme, logs tab, orange action buttons.
- Default state: both quality features OFF. Existing workflows behave identically until user opens the Quality panel.
- Bundled size unchanged (~633 MB) — no new models, just code.

---

## v1.3.1 — Packaging Docs

1. **Split doc surface.** Engineering docs (`README.md`, full `CHANGELOG.md`, `CLAUDE.md`) stay at the project root for devs. End-user docs (`ABOUT.md`, short `CHANGELOG.md`, `HOW_TO_USE.md`) ship inside `dist\ImageUtility\` alongside the exe.
2. **New `dist_docs/` source folder** at project root holds the user-facing `ABOUT.md` + short `CHANGELOG.md`. `build.bat` copies them into `dist\ImageUtility\` automatically after every PyInstaller run, so the shipped docs stay in sync with source. README is NOT shipped — it's a dev doc.
3. **New `ABOUT.md`** in dist — quick 10-second intro for end users: what the app is, why it exists, what each tab does, key features.

---

## v1.3.0 — Resize Behavior + Theme

### Features
1. **Image area now takes maximum space when resizing.** Previously the left-side controls grew with the window and squeezed the preview. Now the controls column is locked at 380px and the preview canvas absorbs all extra space. Image stays as large as possible at every window size.
2. **Before / After slider scales with displayed image.** No longer fixed at 250px — slider width matches the actual rendered image width on every render (clamped to a 150px minimum). Always visible, always proportional.
3. **Grid Split / Atlas Creator previews now use a CTkCanvas instead of a fixed-size CTkLabel.** Preview re-renders on every window resize via `<Configure>` binding.

### UX Changes
1. **Primary action buttons are now desaturated terracotta-orange** (`#ce7e4a` / hover `#b06b3a`) for clearer visual distinction from secondary controls. Applies to: Remove Background, Split Image, Create Atlas. (Advanced version also gets: Apply, Save Current, Describe Image, Save to MD.)

---

## v1.2.0 — Drag & Drop Crash Fix

### Bug Fixes
1. **Fixed silent crash when dragging onto Grid Split / Atlas Creator tabs.** Drop callback ran inside the native `WM_DROPFILES` Win32 handler. Calling `PIL.ImageTk.PhotoImage()` from there triggered Tk reentrancy → silent native crash (no Python exception, process died mid-session). Fixed by deferring all drop callbacks via `widget.after(10, ...)` so they run on the next Tk idle cycle.
2. **Fixed drops being routed to inactive tab widgets.** Old routing chose the "first visible" widget regardless of which CTkTabview tab was active. A drop on Grid Split could fire Atlas Creator's callback (or vice versa). Added `winfo_viewable()` filter so only widgets in the currently active tab receive drops.
3. **Fixed Grid Split preview failing for non-RGB images.** `ImageDraw.Draw` on palette/grayscale images raised. Added mode check + RGB convert before drawing the grid overlay.

---

## v1.1.0 — Drag & Drop Preview + UX Polish

### Bug Fixes
1. **Fixed drag & drop in bundled exe.** `windnd` was missing from `build.spec` hiddenimports → silent DnD failure in packaged build only (worked fine from `python main.py`).
2. **Fixed drag & drop with CustomTkinter compound widgets.** CTkEntry is a Frame > Entry; child HWNDs swallowed `WM_DROPFILES` before the hooked Frame saw it. Rewrote `utils/drag_drop.py` to hook the top-level window once and route drops to registered targets by mouse position / focus.
4. **Fixed zombie process on close.** onnxruntime native threads kept the process alive after `self.destroy()`, preventing folder deletion on other machines. Added `os._exit(0)` after window destroy.

### Features
1. **Drag & drop image preview — BG Removal.** Dropping an image on the input field immediately displays it on the canvas (no need to hit Remove Background first).
2. **Drag & drop image preview — Grid Split.** Dropping an image shows it instantly with the red grid overlay applied.
3. **Drag & drop folder preview — Atlas Creator.** Dropping a folder shows image count in the info label and first image as a thumbnail in the preview panel.
4. **Browse-also-shows-preview.** Grid Split and Atlas Creator browse buttons now trigger the same preview as drag & drop.

### UX Changes
1. **Shorter Before/After slider.** Reduced width from full-panel span to 250px; quicker to swipe.
2. **Default model changed to `isnet-general-use`.** Sharper edges, better for game asset cutouts.
3. **Remove Background button moved.** Now sits directly below the browse rows (full width), not floated at bottom of the form.
4. **DPI-aware window scaling.** Window opens at 75% of screen size, centered; widget scaling set to 0.85× on 4K (>2000px height) and 0.9× on QHD (>1440px) for compact controls.

---

## v1.0.0 — Initial Release

1. Background Removal tab: single image + batch folder, `u2net` / `isnet-general-use` models, before/after slider, GPU auto-detect.
2. Grid Split tab: rows × cols, red grid overlay preview, per-cell PNG export.
3. Atlas Creator tab: folder of images → spritesheet PNG, natural sort, checkerboard transparency preview.
4. Logs tab: real-time log viewer, keyword filter, level filter, copy-all.
5. PyInstaller `--onedir` bundle (~633MB), fully offline, all models bundled.
6. DPI-aware sizing, dark theme.
