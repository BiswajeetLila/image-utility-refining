"""Batch Convert worker — classification + per-class resize/format pipeline.

See `imageutility-batch-convert-tab.md` for the full spec. Pure-function
helpers live above the I/O pipeline so they can be unit-tested in isolation.
"""

from __future__ import annotations

import csv
import os
import re
import shutil
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from PIL import Image, ImageDraw

from utils.logger import get_logger

log = get_logger("batch_convert")

# ── Constants ───────────────────────────────────────────────────────────

IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tga"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm"}
SKIP_FOLDER_NAMES = {"subjects", "rounded", "ingredients", "exported"}

CLASSES = ("keyart", "gameplay", "ui", "icon", "video", "concept", "unknown")

# Mode A — exact crop-to-fill targets
TARGETS_A = {
    "keyart":   {"portrait": (900, 1600),  "landscape": (1600, 900)},
    "gameplay": {"portrait": (864, 1536),  "landscape": (1536, 864)},
    "ui":       {"portrait": (864, 1536),  "landscape": (1536, 864)},
    "icon":     {"square": (1024, 1024)},
}

# Mode B — long-side caps (downsize-only)
CAPS_B = {
    "keyart":   1600,
    "gameplay": 1536,
    "ui":       1536,
    "icon":     1024,
    "concept":  1280,
}

QUALITIES = {
    "keyart":   80,
    "gameplay": 78,
    "ui":       80,
    "concept":  75,
}

# Squircle radius ≈ 22% of 1024
SQUIRCLE_RADIUS_PCT = 0.22


# ── Classification ──────────────────────────────────────────────────────

_ICON_TOKENS    = {"icon", "launcher", "badge", "appicon"}
_UI_TOKENS      = {"ui", "shop", "store", "garage", "workshop", "collection", "roster",
                   "upgrade", "skill", "talent", "loadout", "banner", "summon", "gacha",
                   "map", "worldmap", "draft", "powerup", "results", "runend", "settings",
                   "home", "menu"}
_GAMEPLAY_TOKENS = {"gameplay", "mockup", "drive", "hud", "portrait", "landscape",
                    "combat", "swarm", "ambush", "objective", "rearcam", "chasecam"}
_KEYART_TOKENS  = {"keyart", "hero", "chase", "boss", "showdown", "lowangle",
                   "splash", "poster"}
_CONCEPT_TOKENS = {"concept", "lineup", "moodboard", "variants", "vs",
                   "comparison", "explore"}

_TOKEN_SPLIT_RE = re.compile(r"[_\-\s\d]+")
_M_PREFIX_RE = re.compile(r"^m\d+")
_K_PREFIX_RE = re.compile(r"^k\d+")


def _tokenise(name: str) -> set[str]:
    """Split filename stem on _, -, whitespace, and digits. Lowercased set."""
    name = name.lower()
    parts = {t for t in _TOKEN_SPLIT_RE.split(name) if t}
    return parts


def classify(filename: str) -> str:
    """Return one of CLASSES from filename keywords.

    Token-boundary match, case-insensitive, first matching rule wins
    (with tie-breakers for HUD and vs/lineup/comparison).
    """
    stem, ext = os.path.splitext(filename)
    ext = ext.lower().lstrip(".")
    name = stem.lower()
    tokens = _tokenise(stem)

    # 1. video by extension
    if "." + ext in VIDEO_EXTS:
        return "video"

    # 2. icon
    if tokens & _ICON_TOKENS:
        return "icon"
    if name.endswith("rounded"):
        return "icon"

    # Tie-breakers (override ordered rules):
    # vs/lineup/comparison → concept
    if tokens & _CONCEPT_TOKENS:
        return "concept"
    # hud → gameplay (not keyart)
    if "hud" in tokens:
        return "gameplay"

    # 3. ui
    if tokens & _UI_TOKENS:
        return "ui"

    # 4. gameplay (incl. m<N> prefix)
    if tokens & _GAMEPLAY_TOKENS:
        return "gameplay"
    if _M_PREFIX_RE.match(name):
        return "gameplay"

    # 5. keyart (incl. k<N> prefix)
    if tokens & _KEYART_TOKENS:
        return "keyart"
    if _K_PREFIX_RE.match(name):
        return "keyart"

    return "unknown"


# ── Target resolution ───────────────────────────────────────────────────

def _orientation(w: int, h: int) -> str:
    if w == h:
        return "square"
    return "portrait" if h > w else "landscape"


def resolve_target(cls: str, w: int, h: int, mode: str = "A") -> tuple[int, int] | None:
    """Return (target_w, target_h) for the given class + source dims + mode.

    Mode A: exact crop-to-fill targets.
    Mode B: scaled_dims under the long-side cap (no upscale).
    Returns None if the class has no resize spec (e.g. video, unknown).
    """
    if mode not in ("A", "B"):
        raise ValueError(f"mode must be 'A' or 'B', got {mode!r}")

    if cls == "icon":
        if mode == "A":
            return TARGETS_A["icon"]["square"]
        # Mode B: cap, but never upscale
        return scaled_dims(w, h, CAPS_B["icon"])

    if cls in ("keyart", "gameplay", "ui"):
        if mode == "A":
            ori = _orientation(w, h)
            if ori == "square":
                # Pick landscape as default for square sources
                ori = "landscape"
            return TARGETS_A[cls][ori]
        # Mode B
        return scaled_dims(w, h, CAPS_B[cls])

    if cls == "concept":
        return scaled_dims(w, h, CAPS_B["concept"])

    return None


# ── Image resizing helpers ──────────────────────────────────────────────

def scaled_dims(w: int, h: int, cap: int) -> tuple[int, int]:
    """Downsize so max(w,h) <= cap, preserving aspect. Never upscale."""
    m = max(w, h)
    if m <= cap:
        return (w, h)
    factor = cap / m
    return (max(1, round(w * factor)), max(1, round(h * factor)))


def crop_to_fill(img: Image.Image, tw: int, th: int) -> Image.Image:
    """Scale-to-cover + center-crop to (tw, th). May upscale a small source."""
    w, h = img.size
    scale = max(tw / w, th / h)
    nw = max(tw, round(w * scale))
    nh = max(th, round(h * scale))
    resized = img.resize((nw, nh), Image.LANCZOS)
    x0 = (nw - tw) // 2
    y0 = (nh - th) // 2
    return resized.crop((x0, y0, x0 + tw, y0 + th))


def round_corners(img: Image.Image, radius_pct: float = SQUIRCLE_RADIUS_PCT) -> Image.Image:
    """Apply a squircle (rounded-rectangle) alpha mask. Returns RGBA."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    w, h = img.size
    r = round(min(w, h) * radius_pct)
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=255)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask=mask)
    return out


# ── Naming ──────────────────────────────────────────────────────────────

_DESCRIPTOR_STRIP_TOKENS = {
    "pro", "gpt", "edit", "ai", "model", "output", "image",
    "render", "draft", "final", "v", "ver", "version",
}
_ID_PREFIX_RE = re.compile(r"^[mk]\d+$")
_VERSION_RE = re.compile(r"^v\d+$")


def derive_descriptor(stem: str, cls: str | None = None,
                       orientation: str | None = None) -> str:
    """Pull a short kebab-case descriptor token from the filename stem.

    Strips id prefixes (M1, K12), version tags (v2, v4), model noise, and
    pure digits. Returns the first meaningful remaining token, or "".
    For gameplay, forces inclusion of orientation when supplied.
    """
    parts = re.split(r"[_\-\s]+", stem.lower())
    cleaned: list[str] = []
    for p in parts:
        if not p:
            continue
        if p.isdigit():
            continue
        if _ID_PREFIX_RE.match(p):
            continue
        if _VERSION_RE.match(p):
            continue
        if p in _DESCRIPTOR_STRIP_TOKENS:
            continue
        if p == cls:
            continue
        cleaned.append(p)

    descriptor = cleaned[0] if cleaned else ""

    if cls == "gameplay" and orientation in ("portrait", "landscape"):
        if descriptor and orientation not in descriptor:
            descriptor = f"{orientation}-{descriptor}"
        elif not descriptor:
            descriptor = orientation
    return descriptor


def build_name(theme_slug: str, cls: str, idx: int,
               descriptor: str, ext: str) -> str:
    """Compose <theme-slug>_<class>_<NN>_<descriptor>.<ext>. Drops descriptor if empty."""
    base = f"{theme_slug}_{cls}_{idx:02d}"
    if descriptor:
        base = f"{base}_{descriptor}"
    return f"{base}.{ext.lstrip('.')}"


# ── FFmpeg detection / install ──────────────────────────────────────────

def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def install_ffmpeg_via_winget(log_cb: Callable[[str], None] | None = None) -> bool:
    """Run winget install for ffmpeg. Returns True on success."""
    if log_cb is None:
        log_cb = lambda _msg: None
    log_cb("Installing ffmpeg via winget — this may take 1–3 minutes...")
    try:
        proc = subprocess.run(
            ["winget", "install", "--id", "Gyan.FFmpeg",
             "-e", "--accept-source-agreements", "--accept-package-agreements"],
            capture_output=True, text=True, timeout=600,
        )
        if proc.returncode == 0:
            log_cb("ffmpeg installed. You may need to restart the app for PATH to refresh.")
            log.info("winget ffmpeg install ok")
            return True
        log_cb(f"winget failed (rc={proc.returncode}): {proc.stderr.strip()[:200]}")
        log.warning("winget ffmpeg install failed: %s", proc.stderr[:500])
        return False
    except FileNotFoundError:
        log_cb("winget not found on this machine. Install ffmpeg manually.")
        log.warning("winget binary not found")
        return False
    except subprocess.TimeoutExpired:
        log_cb("winget install timed out.")
        log.warning("winget ffmpeg install timed out")
        return False


# ── File enumeration ────────────────────────────────────────────────────

def enumerate_files(root: Path, recurse: bool) -> list[Path]:
    """List all image+video files under root, skipping known intermediate folders."""
    out: list[Path] = []
    if recurse:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel_parts = {p.lower() for p in path.relative_to(root).parts[:-1]}
            if rel_parts & SKIP_FOLDER_NAMES:
                continue
            if path.suffix.lower() in IMG_EXTS or path.suffix.lower() in VIDEO_EXTS:
                out.append(path)
    else:
        for path in sorted(root.iterdir()):
            if not path.is_file():
                continue
            if path.suffix.lower() in IMG_EXTS or path.suffix.lower() in VIDEO_EXTS:
                out.append(path)
    return sorted(out)


# ── Per-row planning (dry-run) ──────────────────────────────────────────

@dataclass
class PlannedRow:
    src_path: Path
    cls: str                       # current (possibly user-overridden) class
    orig_w: int                    # 0 for video
    orig_h: int                    # 0 for video
    orig_bytes: int
    target_w: int = 0              # 0 if no resize spec
    target_h: int = 0
    planned_ext: str = ""          # "jpg", "png", "mp4", ""
    planned_name: str = ""
    est_bytes: int = 0
    will_copy: bool = False        # already JPG at/below target → byte-copy
    skip: bool = False             # concept (always) or unknown (until reassigned)
    skip_reason: str = ""
    orientation: str = ""


def plan_file(path: Path, mode: str, rename: bool, theme_slug: str,
              icons_rounded: bool, per_class_counter: dict,
              override_class: str | None = None) -> PlannedRow:
    """Build a PlannedRow without touching disk. Increments per_class_counter for rename."""
    ext = path.suffix.lower()
    orig_bytes = path.stat().st_size if path.exists() else 0

    if ext in VIDEO_EXTS:
        cls = override_class or "video"
    else:
        cls = override_class or classify(path.name)

    row = PlannedRow(src_path=path, cls=cls, orig_w=0, orig_h=0,
                     orig_bytes=orig_bytes)

    # Skip rules
    if cls == "concept":
        row.skip = True
        row.skip_reason = "concept skipped by default"
        return row
    if cls == "unknown":
        row.skip = True
        row.skip_reason = "unknown class — assign one"
        return row

    if cls == "video":
        row.planned_ext = "mp4"
        descriptor = derive_descriptor(path.stem, "video")
        idx = per_class_counter["video"] = per_class_counter.get("video", 0) + 1
        if rename:
            row.planned_name = build_name(theme_slug, "video", idx, descriptor, "mp4")
        else:
            row.planned_name = path.stem + ".mp4"
        # est bytes — unknown without ffprobe; show 0 (placeholder)
        row.est_bytes = 0
        return row

    # Image — read dims (lazy open)
    try:
        with Image.open(path) as im:
            row.orig_w, row.orig_h = im.size
    except Exception as e:
        log.warning("Could not open %s: %s", path, e)
        row.skip = True
        row.skip_reason = f"open failed: {e}"
        return row

    target = resolve_target(cls, row.orig_w, row.orig_h, mode=mode)
    if target is None:
        row.skip = True
        row.skip_reason = "no resize rule for class"
        return row
    row.target_w, row.target_h = target

    # Orientation (for gameplay descriptor)
    row.orientation = _orientation(row.target_w, row.target_h)

    # File extension decision
    if cls == "icon" and icons_rounded:
        row.planned_ext = "png"
    else:
        row.planned_ext = "jpg"

    # Idempotency: already JPG and already at target/cap → copy-as-is
    is_jpg = ext in (".jpg", ".jpeg")
    at_target = (row.orig_w == row.target_w and row.orig_h == row.target_h)
    if is_jpg and at_target and row.planned_ext == "jpg":
        row.will_copy = True

    # Build name
    descriptor = derive_descriptor(path.stem, cls, row.orientation)
    if cls == "icon":
        descriptor = ""        # icons may have none per spec
    idx = per_class_counter[cls] = per_class_counter.get(cls, 0) + 1
    if rename:
        row.planned_name = build_name(theme_slug, cls, idx,
                                      descriptor, row.planned_ext)
    else:
        row.planned_name = f"{path.stem}.{row.planned_ext}"

    # Rough size estimate — JPG ~0.15 bytes/px @ q80, PNG ~1 byte/px
    pixels = row.target_w * row.target_h
    if row.planned_ext == "jpg":
        row.est_bytes = int(pixels * 0.15)
    elif row.planned_ext == "png":
        row.est_bytes = int(pixels * 0.6)
    else:
        row.est_bytes = orig_bytes

    return row


def plan_batch(paths: Iterable[Path], mode: str, rename: bool,
               theme_slug: str, icons_rounded: bool,
               overrides: dict[Path, str] | None = None) -> list[PlannedRow]:
    """Build planned rows for every file. Returns rows in input order."""
    overrides = overrides or {}
    counter: dict = {}
    rows: list[PlannedRow] = []
    for p in paths:
        rows.append(plan_file(p, mode, rename, theme_slug,
                              icons_rounded, counter,
                              override_class=overrides.get(p)))
    return rows


# ── Actual conversion ───────────────────────────────────────────────────

def _flatten_to_rgb(img: Image.Image) -> Image.Image:
    """Composite RGBA on white → RGB. Pass through if already RGB."""
    if img.mode in ("RGB", "L"):
        return img.convert("RGB")
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        return bg
    return img.convert("RGB")


def _convert_image(row: PlannedRow, out_path: Path,
                   mode: str, icons_rounded: bool) -> None:
    """Read row.src_path → apply per-class resize → write to out_path."""
    src = row.src_path

    # Bytes-copy fast path
    if row.will_copy:
        shutil.copy2(src, out_path)
        return

    with Image.open(src) as im:
        im.load()
        if row.cls == "icon":
            # Always crop-to-fill to 1024² (mode A); for mode B, use scaled_dims
            if mode == "A":
                img = crop_to_fill(im, row.target_w, row.target_h)
            else:
                img = im.resize((row.target_w, row.target_h), Image.LANCZOS)
            if icons_rounded:
                img = round_corners(img)
                img.save(out_path, format="PNG")
                return
            else:
                img = _flatten_to_rgb(img)
                img.save(out_path, format="JPEG", quality=95, optimize=True)
                return

        # keyart / gameplay / ui / concept
        if mode == "A":
            img = crop_to_fill(im, row.target_w, row.target_h)
        else:
            # Mode B downsize — already in scaled_dims, so just resize
            if (im.size[0], im.size[1]) == (row.target_w, row.target_h):
                img = im
            else:
                img = im.resize((row.target_w, row.target_h), Image.LANCZOS)

        img = _flatten_to_rgb(img)
        quality = QUALITIES.get(row.cls, 80)
        img.save(out_path, format="JPEG", quality=quality, optimize=True)


def _convert_video(row: PlannedRow, out_path: Path) -> bool:
    """Recompress to 720p box / CRF 28 / AAC 96k. Keep whichever of original
    or recompressed is smaller. Returns True if any file was written."""
    if not ffmpeg_available():
        log.warning("ffmpeg missing, copying video as-is: %s", row.src_path)
        shutil.copy2(row.src_path, out_path)
        return True

    tmp = out_path.with_suffix(".tmp.mp4")
    cmd = [
        "ffmpeg", "-y", "-i", str(row.src_path),
        "-vf", "scale='if(gt(iw,ih),min(1280,iw),-2)':'if(gt(iw,ih),-2,min(1280,ih))'",
        "-c:v", "libx264", "-crf", "28", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart",
        str(tmp),
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=900)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        log.warning("ffmpeg failed for %s: %s", row.src_path, e)
        if tmp.exists():
            tmp.unlink()
        shutil.copy2(row.src_path, out_path)
        return True

    orig = row.src_path.stat().st_size
    new = tmp.stat().st_size
    if new < orig:
        tmp.replace(out_path)
    else:
        tmp.unlink()
        shutil.copy2(row.src_path, out_path)
    return True


@dataclass
class BatchResult:
    total_in: int = 0
    total_out: int = 0
    bytes_in: int = 0
    bytes_out: int = 0
    skipped: int = 0
    unknown: int = 0
    per_class_counts: dict = field(default_factory=lambda: defaultdict(int))
    manifest_path: Path | None = None


def run_batch(rows: list[PlannedRow], output_dir: Path,
              mode: str, icons_rounded: bool,
              progress_cb: Callable[[int, int], None] | None = None) -> BatchResult:
    """Execute the plan. Writes files to output_dir + manifest.csv."""
    if progress_cb is None:
        progress_cb = lambda _c, _t: None

    output_dir.mkdir(parents=True, exist_ok=True)

    result = BatchResult(total_in=len(rows))
    manifest_rows: list[dict] = []

    total = len(rows)
    for i, row in enumerate(rows, 1):
        result.bytes_in += row.orig_bytes
        if row.skip:
            result.skipped += 1
            if row.cls == "unknown":
                result.unknown += 1
            progress_cb(i, total)
            continue

        out_path = output_dir / row.planned_name
        try:
            if row.cls == "video":
                _convert_video(row, out_path)
            else:
                _convert_image(row, out_path, mode, icons_rounded)
        except Exception as e:
            log.exception("Conversion failed for %s: %s", row.src_path, e)
            result.skipped += 1
            progress_cb(i, total)
            continue

        new_bytes = out_path.stat().st_size if out_path.exists() else 0
        result.bytes_out += new_bytes
        result.total_out += 1
        result.per_class_counts[row.cls] += 1
        manifest_rows.append({
            "old_path": str(row.src_path),
            "new_name": row.planned_name,
            "class": row.cls,
            "descriptor": derive_descriptor(row.src_path.stem, row.cls,
                                            row.orientation),
            "old_bytes": row.orig_bytes,
            "new_bytes": new_bytes,
        })
        progress_cb(i, total)

    # Write manifest
    manifest_path = output_dir / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "old_path", "new_name", "class", "descriptor",
            "old_bytes", "new_bytes",
        ])
        writer.writeheader()
        writer.writerows(manifest_rows)
    result.manifest_path = manifest_path
    log.info("Batch complete: %d/%d files, %d bytes in → %d bytes out",
             result.total_out, result.total_in, result.bytes_in, result.bytes_out)
    return result
