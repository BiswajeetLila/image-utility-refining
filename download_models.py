"""Pre-download rembg models for bundling into the exe.

Run once before building: `venv\\Scripts\\python.exe download_models.py`
Populates ./models/ with all .onnx files used by the app.
"""
import os
import shutil
import sys
from pathlib import Path

from rembg import new_session

MODELS = ["u2net", "isnet-general-use"]
TARGET = Path(__file__).parent / "models"
TARGET.mkdir(exist_ok=True)

cache = Path(os.environ.get("U2NET_HOME", os.path.expanduser("~/.u2net")))

for m in MODELS:
    dst = TARGET / f"{m}.onnx"
    if dst.exists():
        size = dst.stat().st_size / 1024 / 1024
        print(f"[skip] {m}.onnx already in models/ ({size:.1f} MB)")
        continue

    print(f"[download] {m}...", flush=True)
    new_session(m)

    src = cache / f"{m}.onnx"
    if not src.exists():
        print(f"[error] expected {src} but it doesn't exist", file=sys.stderr)
        sys.exit(1)

    shutil.copy2(src, dst)
    size = dst.stat().st_size / 1024 / 1024
    print(f"[done] {dst} ({size:.1f} MB)")

print(f"\nAll models in {TARGET}")
total = sum(f.stat().st_size for f in TARGET.glob("*.onnx")) / 1024 / 1024
print(f"Total size: {total:.1f} MB")
