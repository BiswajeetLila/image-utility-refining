import customtkinter as ctk
import numpy as np
from PIL import Image, ImageTk

from core.atlas_worker import create_atlas
from utils.drag_drop import enable_drop, enable_entry_drop
from utils.file_helpers import ask_open_folder, ask_save_image
from utils.thread_manager import start_task

PREVIEW_MAX = 400
CHECKER_SIZE = 10


def make_checker_bg(w, h):
    yy, xx = np.indices((h, w))
    mask = ((xx // CHECKER_SIZE) + (yy // CHECKER_SIZE)) % 2 == 0
    arr = np.where(mask[..., None], (200, 200, 200), (240, 240, 240)).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


class AtlasCreatorTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._preview_photo = None
        self._output_path = None
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Atlas Creator", font=ctk.CTkFont(size=20, weight="bold")).pack(
            anchor="w", padx=16, pady=(12, 4))

        # --- Top: controls left, preview right ---
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="both", expand=True, padx=16, pady=4)

        left = ctk.CTkFrame(top, fg_color="transparent", width=380)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        # Input folder
        input_frame = ctk.CTkFrame(left, fg_color="transparent")
        input_frame.pack(fill="x", pady=4)
        ctk.CTkLabel(input_frame, text="Input Folder:").pack(side="left")
        self.input_entry = ctk.CTkEntry(input_frame, placeholder_text="Folder with numbered images...")
        self.input_entry.pack(side="left", fill="x", expand=True, padx=8)
        ctk.CTkButton(input_frame, text="Browse", width=80, command=self._browse_input).pack(side="right")

        # Grid settings
        grid_frame = ctk.CTkFrame(left, fg_color="transparent")
        grid_frame.pack(fill="x", pady=8)
        ctk.CTkLabel(grid_frame, text="Rows:").pack(side="left")
        self.rows_entry = ctk.CTkEntry(grid_frame, width=60, placeholder_text="2")
        self.rows_entry.pack(side="left", padx=(4, 16))
        self.rows_entry.insert(0, "2")
        ctk.CTkLabel(grid_frame, text="Cols:").pack(side="left")
        self.cols_entry = ctk.CTkEntry(grid_frame, width=60, placeholder_text="2")
        self.cols_entry.pack(side="left", padx=4)
        self.cols_entry.insert(0, "2")

        # Output file
        output_frame = ctk.CTkFrame(left, fg_color="transparent")
        output_frame.pack(fill="x", pady=4)
        ctk.CTkLabel(output_frame, text="Output File:").pack(side="left")
        self.output_entry = ctk.CTkEntry(output_frame, placeholder_text="Save atlas as...")
        self.output_entry.pack(side="left", fill="x", expand=True, padx=8)
        ctk.CTkButton(output_frame, text="Save As", width=80, command=self._browse_output).pack(side="right")

        enable_drop(self.input_entry, self._on_input_drop)
        enable_entry_drop(self.output_entry)

        # Stitch button
        self.stitch_btn = ctk.CTkButton(left, text="Create Atlas", height=40,
                                        font=ctk.CTkFont(size=14, weight="bold"), command=self._start_stitch,
                                        fg_color="#ce7e4a", hover_color="#b06b3a")
        self.stitch_btn.pack(anchor="w", pady=(12, 4))

        # Info label
        self.info_label = ctk.CTkLabel(left, text="", font=ctk.CTkFont(size=11), text_color=("gray50", "gray60"))
        self.info_label.pack(anchor="w", pady=2)

        # Preview (right side) â€” expands to fill remaining space
        preview_container = ctk.CTkFrame(top)
        preview_container.pack(side="right", fill="both", expand=True, padx=(16, 0))

        ctk.CTkLabel(preview_container, text="Output Preview", font=ctk.CTkFont(size=12, weight="bold")).pack(
            pady=(8, 4))
        self.preview_canvas = ctk.CTkCanvas(preview_container, highlightthickness=0, bg="#2b2b2b")
        self.preview_canvas.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._placeholder_text = self.preview_canvas.create_text(
            0, 0, text="Create an atlas\nto see preview", fill="#666666", font=("Segoe UI", 12), justify="center")
        self.preview_canvas.bind("<Configure>", self._on_canvas_resize)
        # Stash the last preview image so we can re-render on resize
        self._current_preview_pil = None

        # --- Progress ---
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.pack(fill="x", padx=16, pady=4)
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(self, text="Ready", font=ctk.CTkFont(size=12))
        self.status_label.pack(padx=16, pady=(0, 12))

    def _browse_input(self):
        path = ask_open_folder()
        if path:
            self.input_entry.delete(0, "end")
            self.input_entry.insert(0, path)
            self._show_folder_info(path)

    def _on_input_drop(self, path_str):
        """Handle drag-drop on input entry â€” fill path and show folder info."""
        self.input_entry.delete(0, "end")
        self.input_entry.insert(0, path_str)
        self._show_folder_info(path_str)

    def _show_folder_info(self, folder_path):
        """Count images in dropped folder and show first image as preview."""
        from pathlib import Path
        exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".tif"}
        folder = Path(folder_path)
        if not folder.is_dir():
            return
        images = sorted(f for f in folder.iterdir() if f.suffix.lower() in exts)
        count = len(images)
        if count == 0:
            self.info_label.configure(text="No images found in folder.")
            return
        self.info_label.configure(text=f"Found {count} image{'s' if count != 1 else ''} in folder")
        # Show first image as preview thumbnail
        try:
            with Image.open(images[0]) as src:
                self._current_preview_pil = src.copy().convert("RGBA")
            self._render_preview_on_canvas(self._current_preview_pil)
        except Exception:
            pass

    def _on_canvas_resize(self, event=None):
        w = self.preview_canvas.winfo_width()
        h = self.preview_canvas.winfo_height()
        try:
            self.preview_canvas.coords(self._placeholder_text, w // 2, h // 2)
        except Exception:
            pass
        if self._current_preview_pil is not None:
            self._render_preview_on_canvas(self._current_preview_pil)

    def _render_preview_on_canvas(self, pil_img):
        """Render a PIL image onto preview_canvas using current canvas size and a checkerboard background."""
        cw = self.preview_canvas.winfo_width()
        ch = self.preview_canvas.winfo_height()
        if cw < 10 or ch < 10:
            self.after(100, lambda: self._render_preview_on_canvas(pil_img))
            return
        img = pil_img.copy()
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        img.thumbnail((cw, ch), Image.LANCZOS)
        checker = make_checker_bg(img.width, img.height)
        checker.paste(img, mask=img.split()[3])
        self._preview_photo = ImageTk.PhotoImage(checker)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(cw // 2, ch // 2, image=self._preview_photo, anchor="center")

    def _browse_output(self):
        path = ask_save_image()
        if path:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, path)

    def _get_grid(self):
        try:
            rows = int(self.rows_entry.get())
            cols = int(self.cols_entry.get())
            if rows < 1 or cols < 1:
                raise ValueError
            return rows, cols
        except ValueError:
            return None, None

    def _start_stitch(self):
        input_path = self.input_entry.get().strip()
        output_path = self.output_entry.get().strip()
        rows, cols = self._get_grid()

        if not input_path or not output_path:
            self.status_label.configure(text="Please select input folder and output file.", text_color="red")
            return
        if rows is None:
            self.status_label.configure(text="Invalid rows/cols values.", text_color="red")
            return

        self._output_path = output_path
        self.stitch_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self.status_label.configure(text="Stitching...", text_color=("gray40", "gray60"))

        start_task(self, create_atlas, (input_path, rows, cols, output_path),
                   on_progress=self._on_progress,
                   on_complete=self._on_complete,
                   on_error=self._on_error)

    def _on_progress(self, current, total):
        self.progress_bar.set(current / total)
        self.status_label.configure(text=f"Stitching {current}/{total}...")

    def _on_complete(self):
        self.progress_bar.set(1)
        self.status_label.configure(text="Done!", text_color=("green", "#4ade80"))
        self.stitch_btn.configure(state="normal")
        self._show_preview()

    def _show_preview(self):
        if not self._output_path:
            return
        try:
            with Image.open(self._output_path) as src:
                full = src.copy().convert("RGBA")
            self.info_label.configure(text=f"Atlas size: {full.width}x{full.height}")
            self._current_preview_pil = full
            self._render_preview_on_canvas(full)
        except Exception as e:
            self.preview_canvas.delete("all")
            self.preview_canvas.create_text(
                self.preview_canvas.winfo_width() // 2,
                self.preview_canvas.winfo_height() // 2,
                text=f"Failed: {e}", fill="#aa3333", font=("Segoe UI", 11))

    def _on_error(self, message):
        self.status_label.configure(text=f"Error: {message}", text_color="red")
        self.stitch_btn.configure(state="normal")
