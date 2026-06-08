# Mac M-chip Port Plan (Paused)

Status: Plan drafted, paused before implementation. Revisit when ready.

## Locked Decisions

| Question | Choice |
|---|---|
| Build host | Borrow teammate's M-chip Mac (one-off per release) |
| Code signing | Ad-hoc sign only (`codesign -s -`) — free, stops "damaged" error, Gatekeeper still prompts once |
| ML backend | CPU only (matches Windows behavior, predictable) |
| Distribution | `.dmg` installer |

## Compatibility Analysis

### Works as-is
- `pathlib.Path` everywhere → cross-platform paths
- `sys.executable -m pip` → no Windows-specific pip path
- CustomTkinter + Tk → runs on macOS
- `~/.u2net` via `os.path.expanduser` → resolves to `/Users/<name>/.u2net`
- `.onnx` models → platform-agnostic
- `subprocess.Popen` with stdout pipes → POSIX-friendly

### Needs change
1. **PyInstaller cannot cross-compile.** Must build on M-chip Mac (or `macos-14` GitHub Actions runner).
2. **`onnxruntime` wheel swap.** Reinstall on Mac venv — pip auto-resolves arm64 wheel.
3. **`.app` bundle format.** Add `BUNDLE()` directive in spec → produces `ImageUtility.app`.
4. **Gatekeeper / quarantine.** Ad-hoc sign required to stop "damaged" error on Apple Silicon. Users right-click → Open once.
5. **Logger path.** `.app` bundles are read-only when signed. Move logs to `~/Library/Logs/ImageUtility/` on macOS.
6. **`windnd` is Windows-only.** Current `utils/drag_drop.py` uses `windnd` (Win32 API). Mac needs alternative:
   - Option A: Stub `enable_entry_drop()` as no-op on macOS (file dialogs still work)
   - Option B: Use `tkinterdnd2` (cross-platform) — replaces `windnd` everywhere
7. **`build.bat` Windows-only.** Add `build_mac.sh`.

## Plan

### Phase 1 — Cross-platform code prep (do on Windows, commit, pull on Mac)

**1.1 Patch `utils/logger.py`** — branch log dir per platform:
```python
import sys
from pathlib import Path

if sys.platform == "darwin":
    LOG_DIR = Path.home() / "Library" / "Logs" / "ImageUtility"
else:
    LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
```

**1.2 Patch `utils/drag_drop.py`** — guard windnd import:
```python
import sys
if sys.platform == "win32":
    import windnd
    # existing implementation
else:
    def enable_entry_drop(entry):
        pass  # no-op; file dialogs still work
```

Decide later: stub vs `tkinterdnd2` replacement. Stub is faster; tkinterdnd2 is consistent UX.

**1.3 Create `build_mac.spec`**

Mirrors `build.spec` but with `BUNDLE()` directive after `COLLECT`:
```python
app = BUNDLE(
    coll,
    name='ImageUtility.app',
    icon=None,
    bundle_identifier='com.lilagames.imageutility',
    info_plist={
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': 'True',
        'LSMinimumSystemVersion': '12.0',
    },
)
```

Also remove `windnd` from `hiddenimports` for Mac spec (don't try to bundle Win32 module).

**1.4 Create `build_mac.sh`**
```bash
#!/bin/bash
set -e
.venv/bin/pyinstaller --clean -y build_mac.spec
codesign --force --deep --sign - dist/ImageUtility.app
hdiutil create -volname "ImageUtility" -srcfolder dist/ImageUtility.app \
  -ov -format UDZO dist/ImageUtility.dmg
echo "Done. Output: dist/ImageUtility.dmg"
```

**1.5 Update `requirements.txt`** — split or conditionally install:
```
customtkinter>=5.2.0
pillow>=10.0.0
rembg>=2.0.50
onnxruntime>=1.16.0
windnd>=1.0.7; sys_platform == "win32"
pyinstaller>=6.0.0
```

**1.6 Commit + push**

### Phase 2 — On borrowed M-chip Mac

**2.1 Prereqs**
```bash
sw_vers                    # macOS 12+
uname -m                   # arm64
python3 --version          # 3.10+
xcode-select --install
```

**2.2 Clone + venv**
```bash
cd ~/Desktop
git clone <repo-url> Image_Editor
cd Image_Editor
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
```

**2.3 Get models** (git LFS or scp from Windows)
```bash
# From Windows PowerShell:
scp models/*.onnx mac-user@mac-ip:~/Desktop/Image_Editor/models/
# Or:
python download_models.py
```

**2.4 Smoke test from source**
```bash
python main.py
```
Verify: splash shows, models seed, BG removal works.

**2.5 Build**
```bash
chmod +x build_mac.sh
./build_mac.sh
```
Output: `dist/ImageUtility.dmg`

**2.6 Test dmg**
```bash
open dist/ImageUtility.dmg
# Drag .app out, double-click (right-click → Open first time)
```

**2.7 Transfer dmg back** (Drive/SharePoint/scp)

### Phase 3 — Distribute to team

1. Send `.dmg` via shared drive
2. Teammate mounts dmg, drags `ImageUtility.app` to `/Applications`
3. First launch: right-click → Open (one-time Gatekeeper bypass)
4. Subsequent: double-click

## Risk Register

| Risk | Mitigation |
|------|------------|
| `numba`/`llvmlite` arm64 wheel issue | Native arm64 wheels since 2022. Pin versions if break. |
| PyInstaller misses `.dylib` deps | `otool -L dist/ImageUtility.app/Contents/MacOS/ImageUtility` — add missing to `binaries`. |
| Models dir >100MB blocks git push | Use Git LFS, or scp out-of-band. |
| Tk fonts small on Retina | Bump baseline `CTkFont(size=14)`. Cosmetic only. |
| `~/Library/Logs/` not auto-created | `mkdir(parents=True, exist_ok=True)` handles it. |
| `windnd` import crash on macOS | Phase 1.2 platform guard fixes. |

## Codebase State at Pause

Files known modified since plan drafted (do not revert when resuming):
- `app.py` — DPI-aware sizing (0.85 for 4K, 0.9 for QHD), screen centering, `os._exit(0)` on close
- `main.py` — prewarm switched to `isnet-general-use`, stdout/stderr None guard for --windowed
- `requirements.txt` — added `windnd>=1.0.7`
- `build.spec` — added `windnd` to hiddenimports
- `tabs/bg_removal.py` — custom drag-drop with image preview, default model = isnet-general-use, shorter slider (width=250), Remove BG button below browse rows
- `tabs/grid_split.py` — custom drag-drop handler: fills entry + calls `_load_preview` (grid overlay)
- `tabs/atlas_creator.py` — custom drag-drop handler: fills entry + `_show_folder_info` (counts images, shows first thumbnail). Browse also calls `_show_folder_info`.
- New file: `utils/drag_drop.py` — hooks TOP-LEVEL WINDOW once via windnd, routes drops to registered widgets by mouse position/focus. Works with customtkinter compound widgets. Windows-only.
- `README.md` — updated to match current features (removed stale silueta/isnet-anime/text-removal refs)

When resuming Mac port: Phase 1.2 (drag-drop platform guard) becomes mandatory.
