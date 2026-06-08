import customtkinter as ctk
from PIL import Image, ImageTk

from core.image_tools_worker import (
    apply_blur_pil, apply_sharpen_pil, convert_format_pil, _normalise_format, _QUALITY_FORMATS,
)
from core.upscale_worker import upscale_pil, model_exists as esrgan_exists
from utils.drag_drop import enable_drop, enable_entry_drop
from utils.file_helpers import ask_open_image, ask_open_folder, ask_save_image
from utils.logger import get_logger
from utils.thread_manager import start_task

log = get_logger("image_tools_tab")

PREVIEW_MAX = 500

TOOLS = ["Blur", "Sharpen", "Upscale", "Convert"]
FORMATS = ["PNG", "JPG", "WEBP", "BMP", "TIFF"]


class ImageToolsTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._original_pil = None
        self._versions = {}          # {"blur": img, "sharpen": img, "upscale": img}
        self._active_view = "original"
        self._preview_photo = None
        self._controls_frame = None  # swapped per tool
        self._build_ui()

    # â”€â”€ UI â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(header, text="Image Tools", font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")

        # Input row
        input_row = ctk.CTkFrame(self, fg_color="transparent")
        input_row.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(input_row, text="Input:", width=50).pack(side="left")
        self.input_entry = ctk.CTkEntry(input_row, placeholder_text="Select image or drag-drop...")
        self.input_entry.pack(side="left", fill="x", expand=True, padx=8)
        ctk.CTkButton(input_row, text="Browse", width=80, command=self._browse_input).pack(side="right")
        enable_drop(self.input_entry, self._on_input_drop)

        # Tool selector
        tool_frame = ctk.CTkFrame(self, fg_color="transparent")
        tool_frame.pack(fill="x", padx=16, pady=(8, 2))

        self.tool_var = ctk.StringVar(value="Blur")
        self.tool_selector = ctk.CTkSegmentedButton(
            tool_frame, values=TOOLS, variable=self.tool_var, command=self._on_tool_change
        )
        self.tool_selector.pack(side="left")

        self.apply_btn = ctk.CTkButton(tool_frame, text="Apply", width=90, height=32,
                                       font=ctk.CTkFont(weight="bold"), command=self._on_apply,
                                       fg_color="#ce7e4a", hover_color="#b06b3a")
        self.apply_btn.pack(side="left", padx=(16, 0))

        # Dynamic controls placeholder
        self._controls_container = ctk.CTkFrame(self, fg_color="transparent", height=60)
        self._controls_container.pack(fill="x", padx=16, pady=2)
        self._build_blur_controls()

        # Preview
        self.preview_canvas = ctk.CTkCanvas(self, highlightthickness=0, bg="#2b2b2b")
        self.preview_canvas.pack(fill="both", expand=True, padx=16, pady=(4, 4))
        self._placeholder = self.preview_canvas.create_text(
            0, 0, text="Load an image to start", fill="#666666", font=("Segoe UI", 12))
        self.preview_canvas.bind("<Configure>", self._on_canvas_resize)

        # View toggle
        view_row = ctk.CTkFrame(self, fg_color="transparent")
        view_row.pack(pady=(0, 4))
        self.view_var = ctk.StringVar(value="original")
        self.view_selector = ctk.CTkSegmentedButton(
            view_row, values=["Original"], variable=self.view_var,
            command=self._on_view_change
        )
        self.view_selector.pack()

        # Output row
        output_row = ctk.CTkFrame(self, fg_color="transparent")
        output_row.pack(fill="x", padx=16, pady=2)
        ctk.CTkLabel(output_row, text="Output:", width=50).pack(side="left")
        self.output_entry = ctk.CTkEntry(output_row, placeholder_text="Select output folder...")
        self.output_entry.pack(side="left", fill="x", expand=True, padx=8)
        ctk.CTkButton(output_row, text="Browse", width=80, command=self._browse_output).pack(side="left", padx=(0, 8))
        self.save_btn = ctk.CTkButton(output_row, text="Save Current", width=110, height=32,
                                      font=ctk.CTkFont(weight="bold"), command=self._on_save,
                                      fg_color="#ce7e4a", hover_color="#b06b3a")
        self.save_btn.pack(side="right")
        enable_entry_drop(self.output_entry)

        # Progress
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.pack(fill="x", padx=16, pady=4)
        self.progress_bar.set(0)
        self.status_label = ctk.CTkLabel(self, text="Ready", font=ctk.CTkFont(size=12))
        self.status_label.pack(padx=16, pady=(0, 8))

    # â”€â”€ Tool-specific control panels â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _clear_controls(self):
        if self._controls_frame:
            self._controls_frame.destroy()
            self._controls_frame = None

    def _build_blur_controls(self):
        self._clear_controls()
        f = ctk.CTkFrame(self._controls_container, fg_color="transparent")
        f.pack(fill="x")
        self._controls_frame = f

        ctk.CTkLabel(f, text="Radius:").pack(side="left")
        self.blur_val_label = ctk.CTkLabel(f, text="3.0", width=40)
        self.blur_val_label.pack(side="left", padx=(4, 0))
        self.blur_slider = ctk.CTkSlider(f, from_=0.5, to=20, number_of_steps=39, width=200,
                                         command=lambda v: self.blur_val_label.configure(text=f"{v:.1f}"))
        self.blur_slider.set(3.0)
        self.blur_slider.pack(side="left", padx=8)

    def _build_sharpen_controls(self):
        self._clear_controls()
        f = ctk.CTkFrame(self._controls_container, fg_color="transparent")
        f.pack(fill="x")
        self._controls_frame = f

        ctk.CTkLabel(f, text="Radius:").pack(side="left")
        self.sharp_radius_label = ctk.CTkLabel(f, text="2.0", width=35)
        self.sharp_radius_label.pack(side="left")
        self.sharp_radius = ctk.CTkSlider(f, from_=0.1, to=10, number_of_steps=99, width=120,
                                          command=lambda v: self.sharp_radius_label.configure(text=f"{v:.1f}"))
        self.sharp_radius.set(2.0)
        self.sharp_radius.pack(side="left", padx=(4, 12))

        ctk.CTkLabel(f, text="Percent:").pack(side="left")
        self.sharp_percent_label = ctk.CTkLabel(f, text="150", width=35)
        self.sharp_percent_label.pack(side="left")
        self.sharp_percent = ctk.CTkSlider(f, from_=50, to=500, number_of_steps=45, width=120,
                                           command=lambda v: self.sharp_percent_label.configure(text=f"{int(v)}"))
        self.sharp_percent.set(150)
        self.sharp_percent.pack(side="left", padx=(4, 12))

        ctk.CTkLabel(f, text="Threshold:").pack(side="left")
        self.sharp_thresh_label = ctk.CTkLabel(f, text="3", width=25)
        self.sharp_thresh_label.pack(side="left")
        self.sharp_thresh = ctk.CTkSlider(f, from_=0, to=10, number_of_steps=10, width=100,
                                          command=lambda v: self.sharp_thresh_label.configure(text=f"{int(v)}"))
        self.sharp_thresh.set(3)
        self.sharp_thresh.pack(side="left", padx=4)

    def _build_upscale_controls(self):
        self._clear_controls()
        f = ctk.CTkFrame(self._controls_container, fg_color="transparent")
        f.pack(fill="x")
        self._controls_frame = f

        ctk.CTkLabel(f, text="Scale:").pack(side="left")
        self.upscale_var = ctk.StringVar(value="2x")
        ctk.CTkSegmentedButton(f, values=["2x", "4x"], variable=self.upscale_var, width=120).pack(side="left", padx=8)

        if not esrgan_exists():
            ctk.CTkLabel(f, text="âš  Model not found", text_color="red",
                         font=ctk.CTkFont(size=11)).pack(side="left", padx=8)

        self.upscale_info = ctk.CTkLabel(f, text="", font=ctk.CTkFont(size=11),
                                         text_color=("gray50", "gray60"))
        self.upscale_info.pack(side="left", padx=8)
        self._update_upscale_info()

    def _build_convert_controls(self):
        self._clear_controls()
        f = ctk.CTkFrame(self._controls_container, fg_color="transparent")
        f.pack(fill="x")
        self._controls_frame = f

        ctk.CTkLabel(f, text="Format:").pack(side="left")
        self.format_var = ctk.StringVar(value="PNG")
        self.format_menu = ctk.CTkOptionMenu(f, variable=self.format_var, values=FORMATS,
                                             width=100, command=self._on_format_change)
        self.format_menu.pack(side="left", padx=8)

        self.quality_label = ctk.CTkLabel(f, text="Quality:")
        self.quality_val_label = ctk.CTkLabel(f, text="85", width=30)
        self.quality_slider = ctk.CTkSlider(f, from_=1, to=100, number_of_steps=99, width=160,
                                            command=lambda v: self.quality_val_label.configure(text=f"{int(v)}"))
        self.quality_slider.set(85)
        # Hidden by default (PNG doesn't use quality)
        self._toggle_quality_controls(False)

    def _toggle_quality_controls(self, show):
        if show:
            self.quality_label.pack(side="left", padx=(12, 4))
            self.quality_val_label.pack(side="left")
            self.quality_slider.pack(side="left", padx=4)
        else:
            self.quality_label.pack_forget()
            self.quality_val_label.pack_forget()
            self.quality_slider.pack_forget()

    def _on_format_change(self, fmt):
        needs_quality = _normalise_format(fmt) in _QUALITY_FORMATS
        self._toggle_quality_controls(needs_quality)

    def _on_tool_change(self, tool):
        builders = {
            "Blur": self._build_blur_controls,
            "Sharpen": self._build_sharpen_controls,
            "Upscale": self._build_upscale_controls,
            "Convert": self._build_convert_controls,
        }
        builders.get(tool, self._build_blur_controls)()

    # â”€â”€ Image loading / browsing â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _browse_input(self):
        path = ask_open_image()
        if path:
            self.input_entry.delete(0, "end")
            self.input_entry.insert(0, path)
            self._load_image(path)

    def _on_input_drop(self, path_str):
        """Drag-drop on input entry â€” fill path and load image preview."""
        from pathlib import Path as _P
        if not _P(path_str).is_file():
            return
        self.input_entry.delete(0, "end")
        self.input_entry.insert(0, path_str)
        self._load_image(path_str)

    def _browse_output(self):
        path = ask_open_folder()
        if path:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, path)

    def _load_image(self, path):
        try:
            if self._original_pil:
                self._original_pil.close()
            with Image.open(path) as src:
                self._original_pil = src.copy()
            self._versions.clear()
            self._active_view = "original"
            self._update_view_buttons()
            self._render_preview()
            self._update_upscale_info()
            self.status_label.configure(
                text=f"Loaded: {self._original_pil.width}x{self._original_pil.height}",
                text_color=("gray40", "gray60"))
        except Exception as e:
            self.status_label.configure(text=f"Failed to load: {e}", text_color="red")
            self._original_pil = None

    def _update_upscale_info(self):
        if not hasattr(self, "upscale_info"):
            return
        if self._original_pil:
            w, h = self._original_pil.size
            scale = 4 if getattr(self, "upscale_var", None) and self.upscale_var.get() == "4x" else 2
            self.upscale_info.configure(text=f"Output: {w*scale}x{h*scale}")
        else:
            self.upscale_info.configure(text="")

    # â”€â”€ View toggling â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _update_view_buttons(self):
        views = ["Original"] + [k.capitalize() for k in self._versions]
        self.view_selector.configure(values=views)
        current = self._active_view.capitalize()
        if current not in views:
            current = "Original"
        self.view_var.set(current)

    def _on_view_change(self, view_name):
        self._active_view = view_name.lower()
        self._render_preview()

    def _get_current_image(self):
        if self._active_view == "original":
            return self._original_pil
        return self._versions.get(self._active_view)

    # â”€â”€ Preview rendering â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _on_canvas_resize(self, event=None):
        w = self.preview_canvas.winfo_width()
        h = self.preview_canvas.winfo_height()
        self.preview_canvas.coords(self._placeholder, w // 2, h // 2)
        if self._original_pil:
            self._render_preview()

    def _render_preview(self):
        img = self._get_current_image()
        if img is None:
            return

        cw = self.preview_canvas.winfo_width()
        ch = self.preview_canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        preview = img.copy()
        preview.thumbnail((cw, ch), Image.BILINEAR)
        self._preview_photo = ImageTk.PhotoImage(preview)

        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(cw // 2, ch // 2, image=self._preview_photo, anchor="center")

    # â”€â”€ Apply tools â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _on_apply(self):
        if self._original_pil is None:
            self.status_label.configure(text="Load an image first.", text_color="red")
            return

        tool = self.tool_var.get()
        self.apply_btn.configure(state="disabled")
        self.save_btn.configure(state="disabled")
        self.progress_bar.set(0)
        self.status_label.configure(text=f"Applying {tool}...", text_color=("gray40", "gray60"))

        source = self._get_current_image() or self._original_pil

        if tool == "Blur":
            radius = self.blur_slider.get()
            def worker(cb):
                cb(1, 2)
                self._versions["blur"] = apply_blur_pil(source, radius)
                cb(2, 2)
            start_task(self, worker, (), self._on_progress,
                       lambda: self._on_tool_complete("blur"), self._on_error)

        elif tool == "Sharpen":
            r = self.sharp_radius.get()
            p = int(self.sharp_percent.get())
            t = int(self.sharp_thresh.get())
            def worker(cb):
                cb(1, 2)
                self._versions["sharpen"] = apply_sharpen_pil(source, r, p, t)
                cb(2, 2)
            start_task(self, worker, (), self._on_progress,
                       lambda: self._on_tool_complete("sharpen"), self._on_error)

        elif tool == "Upscale":
            if not esrgan_exists():
                self.status_label.configure(text="Real-ESRGAN model not found.", text_color="red")
                self.apply_btn.configure(state="normal")
                self.save_btn.configure(state="normal")
                return
            scale = 4 if self.upscale_var.get() == "4x" else 2
            def worker(cb):
                self._versions["upscale"] = upscale_pil(source, scale, cb)
            start_task(self, worker, (), self._on_progress,
                       lambda: self._on_tool_complete("upscale"), self._on_error)

        elif tool == "Convert":
            # Convert is immediate â€” just prep the image
            fmt = self.format_var.get()
            self._versions["convert"] = convert_format_pil(source, fmt)
            self._on_tool_complete("convert")

    def _on_progress(self, current, total):
        self.progress_bar.set(current / max(total, 1))
        self.status_label.configure(text=f"Processing {current}/{total}...")

    def _on_tool_complete(self, version_key):
        self.progress_bar.set(1)
        self.apply_btn.configure(state="normal")
        self.save_btn.configure(state="normal")
        self._active_view = version_key
        self._update_view_buttons()
        self._render_preview()

        img = self._versions.get(version_key)
        size_text = f"{img.width}x{img.height}" if img else ""
        self.status_label.configure(
            text=f"{version_key.capitalize()} applied! {size_text}",
            text_color=("green", "#4ade80"))

    def _on_error(self, message):
        log.error("Image Tools error: %s", message)
        self.status_label.configure(text=f"Error: {message}", text_color="red")
        self.apply_btn.configure(state="normal")
        self.save_btn.configure(state="normal")

    # â”€â”€ Save â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _on_save(self):
        img = self._get_current_image()
        if img is None:
            self.status_label.configure(text="Nothing to save.", text_color="red")
            return

        output_dir = self.output_entry.get().strip()
        input_path = self.input_entry.get().strip()
        if not output_dir:
            self.status_label.configure(text="Select output folder first.", text_color="red")
            return

        from pathlib import Path
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        stem = Path(input_path).stem if input_path else "output"
        suffix = f"_{self._active_view}" if self._active_view != "original" else ""

        # For convert tool, use the selected format's extension
        if self._active_view == "convert":
            fmt = _normalise_format(self.format_var.get())
            ext_map = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "BMP": ".bmp", "TIFF": ".tiff"}
            ext = ext_map.get(fmt, ".png")
            out_path = out_dir / f"{stem}{suffix}{ext}"
            save_kwargs = {"format": fmt}
            if fmt in _QUALITY_FORMATS:
                save_kwargs["quality"] = int(self.quality_slider.get())
            img.save(out_path, **save_kwargs)
        else:
            out_path = out_dir / f"{stem}{suffix}.png"
            img.save(out_path)

        log.info("Saved: %s", out_path)
        self.status_label.configure(text=f"Saved: {out_path.name}", text_color=("green", "#4ade80"))
