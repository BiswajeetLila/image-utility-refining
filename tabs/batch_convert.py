"""Batch Convert tab — point at folder, dry-run preview, convert."""

from __future__ import annotations

import threading
from pathlib import Path

import customtkinter as ctk

from core.batch_convert_worker import (
    CLASSES, PlannedRow, enumerate_files, ffmpeg_available,
    install_ffmpeg_via_winget, plan_batch, run_batch,
)
from utils.drag_drop import enable_drop
from utils.file_helpers import ask_open_folder
from utils.logger import get_logger
from utils.thread_manager import start_task

log = get_logger("batch_convert_tab")

CLASS_OPTIONS = list(CLASSES)  # editable dropdown values


def _fmt_bytes(n: int) -> str:
    if n <= 0:
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} TB"


class BatchConvertTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._files: list[Path] = []
        self._rows: list[PlannedRow] = []
        self._overrides: dict[Path, str] = {}
        self._row_widgets: list[dict] = []
        self._build_ui()
        self._check_ffmpeg()

    # ── UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(header, text="Batch Convert",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        self.ffmpeg_badge = ctk.CTkLabel(
            header, text="", font=ctk.CTkFont(size=12), text_color=("#888", "#999"))
        self.ffmpeg_badge.pack(side="right")

        # Source row
        src_row = ctk.CTkFrame(self, fg_color="transparent")
        src_row.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(src_row, text="Source:", width=70).pack(side="left")
        self.src_entry = ctk.CTkEntry(src_row, placeholder_text="Pick the messy folder...")
        self.src_entry.pack(side="left", fill="x", expand=True, padx=8)
        ctk.CTkButton(src_row, text="Browse", width=80,
                      command=self._browse_src).pack(side="right")
        enable_drop(self.src_entry, self._on_src_drop)

        # Output row
        out_row = ctk.CTkFrame(self, fg_color="transparent")
        out_row.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(out_row, text="Output:", width=70).pack(side="left")
        self.out_entry = ctk.CTkEntry(out_row, placeholder_text="(defaults to <source>/exported)")
        self.out_entry.pack(side="left", fill="x", expand=True, padx=8)
        ctk.CTkButton(out_row, text="Browse", width=80,
                      command=self._browse_out).pack(side="right")

        # Options
        opts = ctk.CTkFrame(self, fg_color=("gray90", "gray20"), corner_radius=8)
        opts.pack(fill="x", padx=16, pady=(8, 2))

        opts_row1 = ctk.CTkFrame(opts, fg_color="transparent")
        opts_row1.pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(opts_row1, text="Size mode:").pack(side="left")
        self.mode_var = ctk.StringVar(value="A")
        self._mode_segbtn = ctk.CTkSegmentedButton(
            opts_row1, values=["Normalize (fixed res)", "Downsize-only"])
        self._mode_segbtn.set("Normalize (fixed res)")
        self._mode_segbtn.pack(side="left", padx=(4, 20))

        ctk.CTkLabel(opts_row1, text="Icon corners:").pack(side="left")
        self._icon_segbtn = ctk.CTkSegmentedButton(
            opts_row1, values=["All rounded (PNG)", "All square (JPG)"])
        self._icon_segbtn.set("All rounded (PNG)")
        self._icon_segbtn.pack(side="left", padx=(4, 20))

        self.recurse_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(opts_row1, text="Recurse subfolders",
                        variable=self.recurse_var).pack(side="left")

        opts_row2 = ctk.CTkFrame(opts, fg_color="transparent")
        opts_row2.pack(fill="x", padx=12, pady=(0, 8))

        self.rename_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(opts_row2, text="Rename to convention",
                        variable=self.rename_var).pack(side="left")

        ctk.CTkLabel(opts_row2, text="Theme slug:").pack(side="left", padx=(20, 4))
        self.theme_entry = ctk.CTkEntry(opts_row2, placeholder_text="e.g. wild-wild-west",
                                        width=240)
        self.theme_entry.pack(side="left")

        # Action buttons
        act = ctk.CTkFrame(self, fg_color="transparent")
        act.pack(fill="x", padx=16, pady=(4, 2))
        self.refresh_btn = ctk.CTkButton(act, text="Refresh preview",
                                         width=140, command=self._on_refresh)
        self.refresh_btn.pack(side="left")
        self.convert_btn = ctk.CTkButton(
            act, text="Convert", width=140, height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_convert,
            fg_color="#ce7e4a", hover_color="#b06b3a")
        self.convert_btn.pack(side="right")

        # Preview header
        hdr_row = ctk.CTkFrame(self, fg_color=("gray85", "gray25"))
        hdr_row.pack(fill="x", padx=16, pady=(8, 0))
        for text, w, anchor in [
            ("File", 240, "w"),
            ("Class", 110, "w"),
            ("Current", 130, "w"),
            ("Planned", 130, "w"),
            ("New name", 260, "w"),
        ]:
            ctk.CTkLabel(hdr_row, text=text, width=w, anchor=anchor,
                         font=ctk.CTkFont(size=11, weight="bold")).pack(
                side="left", padx=4)

        # Preview scrollable
        self.preview = ctk.CTkScrollableFrame(self, fg_color=("gray95", "gray15"))
        self.preview.pack(fill="both", expand=True, padx=16, pady=(0, 4))

        # Progress + status
        self.progress = ctk.CTkProgressBar(self)
        self.progress.pack(fill="x", padx=16, pady=(4, 2))
        self.progress.set(0)
        self.status = ctk.CTkLabel(self, text="Pick a source folder to begin.",
                                   font=ctk.CTkFont(size=12))
        self.status.pack(padx=16, pady=(0, 8))

    # ── ffmpeg state ────────────────────────────────────────────────────

    def _check_ffmpeg(self):
        if ffmpeg_available():
            self.ffmpeg_badge.configure(
                text="✓ ffmpeg available",
                text_color=("#2d8a4e", "#4ade80"))
        else:
            self.ffmpeg_badge.configure(
                text="⚠ ffmpeg missing (videos skipped)",
                text_color=("#d97706", "#fbbf24"))

    def _prompt_install_ffmpeg(self):
        from tkinter import messagebox
        ok = messagebox.askyesno(
            "Install ffmpeg?",
            "Videos detected in the batch, but ffmpeg is not installed.\n\n"
            "Install ffmpeg via winget now? (takes 1–3 minutes)\n\n"
            "Click No to skip videos for this run.")
        if not ok:
            return False
        self.status.configure(text="Installing ffmpeg via winget...",
                              text_color=("#d97706", "#fbbf24"))
        self.update_idletasks()

        done = threading.Event()
        success = [False]

        def worker():
            success[0] = install_ffmpeg_via_winget(
                log_cb=lambda m: self.after(0, lambda: self.status.configure(text=m)))
            done.set()

        threading.Thread(target=worker, daemon=True).start()

        # block UI until done — simple wait loop
        while not done.is_set():
            self.update()
            self.after(100)

        self._check_ffmpeg()
        return success[0] and ffmpeg_available()

    # ── Browsing ────────────────────────────────────────────────────────

    def _browse_src(self):
        path = ask_open_folder()
        if path:
            self.src_entry.delete(0, "end")
            self.src_entry.insert(0, path)
            self.status.configure(
                text="Source set. Click Refresh preview to load.",
                text_color=("gray40", "gray60"))

    def _browse_out(self):
        path = ask_open_folder()
        if path:
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, path)

    def _on_src_drop(self, path_str):
        p = Path(path_str)
        if p.is_dir():
            self.src_entry.delete(0, "end")
            self.src_entry.insert(0, str(p))
            self.status.configure(
                text="Source set. Click Refresh preview to load.",
                text_color=("gray40", "gray60"))

    # ── Preview build ───────────────────────────────────────────────────

    def _resolve_mode(self) -> str:
        return "A" if self._mode_segbtn.get().startswith("Normalize") else "B"

    def _icons_rounded(self) -> bool:
        return self._icon_segbtn.get().startswith("All rounded")

    def _on_refresh(self, _evt=None):
        src = self.src_entry.get().strip()
        if not src or not Path(src).is_dir():
            self._clear_preview()
            self.status.configure(text="Pick a source folder to begin.",
                                  text_color=("gray40", "gray60"))
            return

        self._files = enumerate_files(Path(src), self.recurse_var.get())
        if not self._files:
            self._clear_preview()
            self.status.configure(
                text="No image or video files found in that folder.",
                text_color="red")
            return

        theme = self.theme_entry.get().strip() or Path(src).name
        self._rows = plan_batch(
            self._files,
            mode=self._resolve_mode(),
            rename=self.rename_var.get(),
            theme_slug=theme,
            icons_rounded=self._icons_rounded(),
            overrides=self._overrides,
        )
        self._render_preview()

        unknown_n = sum(1 for r in self._rows if r.cls == "unknown")
        skip_n = sum(1 for r in self._rows if r.skip)
        total_in = sum(r.orig_bytes for r in self._rows)
        total_est = sum(r.est_bytes for r in self._rows if not r.skip)
        msg = f"{len(self._rows)} files · {_fmt_bytes(total_in)} → ~{_fmt_bytes(total_est)}"
        if unknown_n:
            msg += f"  ·  ⚠ {unknown_n} unknown — assign class to include"
        if skip_n - unknown_n:
            msg += f"  ·  {skip_n - unknown_n} skipped (concept/error)"
        self.status.configure(text=msg, text_color=("gray40", "gray60"))

    def _clear_preview(self):
        for w in self.preview.winfo_children():
            w.destroy()
        self._row_widgets.clear()

    def _render_preview(self):
        self._clear_preview()
        for idx, row in enumerate(self._rows):
            bg = ("gray92", "gray18") if idx % 2 == 0 else ("gray88", "gray22")
            r = ctk.CTkFrame(self.preview, fg_color=bg)
            r.pack(fill="x", pady=1)

            ctk.CTkLabel(r, text=row.src_path.name, width=240, anchor="w",
                         font=ctk.CTkFont(size=11)).pack(side="left", padx=4)

            cls_var = ctk.StringVar(value=row.cls)
            cls_menu = ctk.CTkOptionMenu(
                r, variable=cls_var, values=CLASS_OPTIONS, width=110,
                command=lambda v, p=row.src_path: self._on_class_change(p, v))
            cls_menu.pack(side="left", padx=4)

            if row.orig_w and row.orig_h:
                cur = f"{row.orig_w}×{row.orig_h}  ({_fmt_bytes(row.orig_bytes)})"
            else:
                cur = _fmt_bytes(row.orig_bytes)
            ctk.CTkLabel(r, text=cur, width=130, anchor="w",
                         font=ctk.CTkFont(size=11),
                         text_color=("gray40", "gray70")).pack(side="left", padx=4)

            if row.skip:
                planned = row.skip_reason
                colour = ("#d97706", "#fbbf24")
            elif row.cls == "video":
                planned = "720p box (H.264)"
                colour = ("gray40", "gray70")
            else:
                planned = f"{row.target_w}×{row.target_h}  →  ~{_fmt_bytes(row.est_bytes)}"
                if row.will_copy:
                    planned += "  (copy)"
                colour = ("gray40", "gray70")
            ctk.CTkLabel(r, text=planned, width=130, anchor="w",
                         font=ctk.CTkFont(size=11),
                         text_color=colour).pack(side="left", padx=4)

            name_txt = row.planned_name if not row.skip else "—"
            ctk.CTkLabel(r, text=name_txt, width=260, anchor="w",
                         font=ctk.CTkFont(size=11),
                         text_color=("gray40", "gray70")).pack(side="left", padx=4)

            self._row_widgets.append({"row": r, "var": cls_var})

    def _on_class_change(self, path: Path, new_cls: str):
        """Store override but DON'T full-refresh. Tell user to click Refresh."""
        self._overrides[path] = new_cls
        self.status.configure(
            text=f"Class override set ({path.name} → {new_cls}). "
                 f"Click Refresh preview to recompute names/sizes.",
            text_color=("#d97706", "#fbbf24"))

    # ── Convert ─────────────────────────────────────────────────────────

    def _on_convert(self):
        if not self._rows:
            self.status.configure(text="Nothing to convert. Refresh the preview first.",
                                  text_color="red")
            return

        src = self.src_entry.get().strip()
        out = self.out_entry.get().strip() or str(Path(src) / "exported")
        out_path = Path(out)

        unknown_n = sum(1 for r in self._rows if r.cls == "unknown")
        if unknown_n:
            from tkinter import messagebox
            ok = messagebox.askyesno(
                "Unknown rows",
                f"{unknown_n} files have an unknown class and will be skipped.\n\n"
                "Convert anyway?")
            if not ok:
                return

        # ffmpeg check
        video_n = sum(1 for r in self._rows if r.cls == "video" and not r.skip)
        if video_n and not ffmpeg_available():
            installed = self._prompt_install_ffmpeg()
            if not installed:
                from tkinter import messagebox
                messagebox.showinfo(
                    "Continuing without ffmpeg",
                    f"{video_n} video file(s) will be copied as-is (no recompression).")

        # Overwrite warning
        if out_path.exists() and any(out_path.iterdir()):
            self.status.configure(
                text=f"Output {out_path.name}/ exists — files will be overwritten.",
                text_color=("#d97706", "#fbbf24"))

        self.convert_btn.configure(state="disabled")
        self.refresh_btn.configure(state="disabled")
        self.progress.set(0)

        mode = self._resolve_mode()
        icons_rounded = self._icons_rounded()
        rows_snapshot = list(self._rows)

        def worker(progress_cb):
            self._batch_result = run_batch(
                rows_snapshot, out_path, mode, icons_rounded,
                progress_cb=progress_cb)

        start_task(self, worker, (),
                   on_progress=self._on_progress,
                   on_complete=self._on_complete,
                   on_error=self._on_error)

    def _on_progress(self, current, total):
        self.progress.set(current / max(total, 1))
        self.status.configure(text=f"Converting {current}/{total}...")

    def _on_complete(self):
        r = self._batch_result
        self.progress.set(1)
        pct = (1 - r.bytes_out / r.bytes_in) * 100 if r.bytes_in else 0
        per_cls = "  ".join(f"{cls}:{n}" for cls, n in r.per_class_counts.items())
        msg = (f"Done. {r.total_out}/{r.total_in} written. "
               f"{_fmt_bytes(r.bytes_in)} → {_fmt_bytes(r.bytes_out)} "
               f"({pct:+.0f}%).  {per_cls}")
        if r.unknown:
            msg += f"  ⚠ {r.unknown} unknown skipped."
        self.status.configure(text=msg, text_color=("green", "#4ade80"))
        self.convert_btn.configure(state="normal")
        self.refresh_btn.configure(state="normal")
        log.info("Batch result: %s", msg)

    def _on_error(self, message):
        log.error("Batch convert failed: %s", message)
        self.status.configure(text=f"Error: {message}", text_color="red")
        self.convert_btn.configure(state="normal")
        self.refresh_btn.configure(state="normal")
