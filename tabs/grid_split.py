import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

from core.grid_worker import split_grid
from utils.drag_drop import enable_drop, enable_entry_drop
from utils.file_helpers import ask_open_folder, ask_open_image
from utils.thread_manager import start_task

PREVIEW_SIZE = 300


class GridSplitTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._preview_photo = None
        self._source_image = None
        self._build_ui()

    def _build_ui(self):
        ctk.CTkLabel(self, text="Grid Split", font=ctk.CTkFont(size=20, weight="bold")).pack(
            anchor="w", padx=16, pady=(16, 8))

        # --- Top section: input + settings on left, preview on right ---
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="both", expand=True, padx=16, pady=4)

        left = ctk.CTkFrame(top, fg_color="transparent", width=380)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        # Input
        input_frame = ctk.CTkFrame(left, fg_color="transparent")
        input_frame.pack(fill="x", pady=4)
        ctk.CTkLabel(input_frame, text="Image:").pack(side="left")
        self.input_entry = ctk.CTkEntry(input_frame, placeholder_text="Select image...")
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

        ctk.CTkButton(left, text="Update Preview", width=120, command=self._update_preview).pack(anchor="w", pady=4)

        # Output
        output_frame = ctk.CTkFrame(left, fg_color="transparent")
        output_frame.pack(fill="x", pady=4)
        ctk.CTkLabel(output_frame, text="Output:").pack(side="left")
        self.output_entry = ctk.CTkEntry(output_frame, placeholder_text="Select output folder...")
        self.output_entry.pack(side="left", fill="x", expand=True, padx=8)
        ctk.CTkButton(output_frame, text="Browse", width=80, command=self._browse_output).pack(side="right")

        enable_drop(self.input_entry, self._on_input_drop)
        enable_entry_drop(self.output_entry)

        # Size info
        self.size_label = ctk.CTkLabel(left, text="", font=ctk.CTkFont(size=11))
        self.size_label.pack(anchor="w", pady=2)

        # Preview canvas â€” expands to fill remaining space
        self.preview_canvas = ctk.CTkCanvas(top, highlightthickness=0, bg="#2b2b2b")
        self.preview_canvas.pack(side="right", fill="both", expand=True, padx=(16, 0))
        self._placeholder_text = self.preview_canvas.create_text(
            0, 0, text="No image loaded", fill="#666666", font=("Segoe UI", 12))
        self.preview_canvas.bind("<Configure>", self._on_canvas_resize)
        self._preview_photo = None

        # --- Bottom: button + progress ---
        self.split_btn = ctk.CTkButton(self, text="Split Image", height=40,
                                       font=ctk.CTkFont(size=14, weight="bold"), command=self._start_split,
                                       fg_color="#ce7e4a", hover_color="#b06b3a")
        self.split_btn.pack(padx=16, pady=(8, 4))

        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.pack(fill="x", padx=16, pady=4)
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(self, text="Ready", font=ctk.CTkFont(size=12))
        self.status_label.pack(padx=16, pady=(0, 12))

    def _browse_input(self):
        path = ask_open_image()
        if path:
            self.input_entry.delete(0, "end")
            self.input_entry.insert(0, path)
            self._load_preview(path)

    def _on_input_drop(self, path_str):
        """Handle drag-drop on input entry â€” fill path and show preview."""
        self.input_entry.delete(0, "end")
        self.input_entry.insert(0, path_str)
        self._load_preview(path_str)

    def _browse_output(self):
        path = ask_open_folder()
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

    def _load_preview(self, path):
        try:
            if self._source_image is not None:
                self._source_image.close()
            with Image.open(path) as src:
                self._source_image = src.copy()
            self._update_preview()
        except Exception as e:
            self._source_image = None
            try:
                self.preview_canvas.delete("all")
                self.preview_canvas.create_text(
                    self.preview_canvas.winfo_width() // 2,
                    self.preview_canvas.winfo_height() // 2,
                    text=f"Failed to load: {e}", fill="#aa3333", font=("Segoe UI", 11))
            except Exception:
                pass

    def _update_preview(self):
        if self._source_image is None:
            return
        rows, cols = self._get_grid()
        if rows is None:
            self.status_label.configure(text="Invalid rows/cols.", text_color="red")
            return

        cw = self.preview_canvas.winfo_width()
        ch = self.preview_canvas.winfo_height()
        if cw < 10 or ch < 10:
            self.after(100, self._update_preview)
            return

        img = self._source_image.copy()
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        img.thumbnail((cw, ch), Image.BILINEAR)
        w, h = img.size
        draw = ImageDraw.Draw(img)

        cell_w = w / cols
        cell_h = h / rows
        for r in range(1, rows):
            y = int(r * cell_h)
            draw.line([(0, y), (w, y)], fill="red", width=2)
        for c in range(1, cols):
            x = int(c * cell_w)
            draw.line([(x, 0), (x, h)], fill="red", width=2)

        orig_w, orig_h = self._source_image.size
        self.size_label.configure(
            text=f"Image: {orig_w}x{orig_h}  |  Cell: {orig_w // cols}x{orig_h // rows}  |  Total: {rows * cols} cells")

        self._preview_photo = ImageTk.PhotoImage(img)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(cw // 2, ch // 2, image=self._preview_photo, anchor="center")

    def _on_canvas_resize(self, event=None):
        w = self.preview_canvas.winfo_width()
        h = self.preview_canvas.winfo_height()
        try:
            self.preview_canvas.coords(self._placeholder_text, w // 2, h // 2)
        except Exception:
            pass
        if self._source_image is not None:
            self._update_preview()

    def _start_split(self):
        input_path = self.input_entry.get().strip()
        output_path = self.output_entry.get().strip()
        rows, cols = self._get_grid()

        if not input_path or not output_path:
            self.status_label.configure(text="Please select input and output paths.", text_color="red")
            return
        if rows is None:
            self.status_label.configure(text="Invalid rows/cols values.", text_color="red")
            return

        self.split_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self.status_label.configure(text="Splitting...", text_color=("gray40", "gray60"))

        start_task(self, split_grid, (input_path, rows, cols, output_path),
                   on_progress=self._on_progress,
                   on_complete=self._on_complete,
                   on_error=self._on_error)

    def _on_progress(self, current, total):
        self.progress_bar.set(current / total)
        self.status_label.configure(text=f"Splitting {current}/{total}...")

    def _on_complete(self):
        self.progress_bar.set(1)
        self.status_label.configure(text="Done!", text_color=("green", "#4ade80"))
        self.split_btn.configure(state="normal")

    def _on_error(self, message):
        self.status_label.configure(text=f"Error: {message}", text_color="red")
        self.split_btn.configure(state="normal")
