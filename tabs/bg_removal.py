import customtkinter as ctk
import numpy as np
from PIL import Image, ImageTk

from core.bg_worker import detect_providers, process_batch, process_single_to_pil, get_session, model_file_exists
from utils.drag_drop import enable_drop, enable_entry_drop
from utils.file_helpers import ask_open_folder, ask_open_image
from utils.logger import get_logger
from utils.thread_manager import start_task

log = get_logger("bg_tab")

MODELS = {
    "u2net": "General purpose — good all-rounder for people, objects, products. Balanced quality & speed.",
    "isnet-general-use": "Sharper edges than u2net — best for clean cutouts of well-defined subjects.",
}

CHECKER_SIZE = 10


def make_checker_bg(w, h):
    yy, xx = np.indices((h, w))
    mask = ((xx // CHECKER_SIZE) + (yy // CHECKER_SIZE)) % 2 == 0
    arr = np.where(mask[..., None], (200, 200, 200), (240, 240, 240)).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def composite_on_checker(rgba_img, checker=None):
    if checker is None or checker.size != rgba_img.size:
        checker = make_checker_bg(rgba_img.width, rgba_img.height)
    else:
        checker = checker.copy()
    checker.paste(rgba_img, mask=rgba_img.split()[3])
    return checker


class BgRemovalTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.providers, self.provider_label = detect_providers()
        self._before_pil = None
        self._after_pil = None
        self._after_nobg_pil = None
        self._display_before = None
        self._display_after = None
        self._quality_panel_visible = False
        self._build_ui()

    # ──────────────────────────── UI BUILD ────────────────────────────

    def _build_ui(self):
        # --- Header ---
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(header, text="Background Removal",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")
        hw_badge = ctk.CTkLabel(
            header, text=f"⚡ {self.provider_label}", font=ctk.CTkFont(size=12),
            text_color=("#2d8a4e", "#4ade80") if "GPU" in self.provider_label else ("#888", "#999"))
        hw_badge.pack(side="right")

        # --- Controls row (mode + model) ---
        controls = ctk.CTkFrame(self)
        controls.pack(fill="x", padx=16, pady=4)

        self.mode_var = ctk.StringVar(value="single")
        ctk.CTkRadioButton(controls, text="Single Image", variable=self.mode_var,
                           value="single", command=self._on_mode_change).pack(side="left", padx=(12, 16), pady=8)
        ctk.CTkRadioButton(controls, text="Batch Folder", variable=self.mode_var,
                           value="batch", command=self._on_mode_change).pack(side="left", padx=16, pady=8)

        ctk.CTkLabel(controls, text="Model:").pack(side="left", padx=(24, 4))
        self.model_var = ctk.StringVar(value="isnet-general-use")
        self.model_menu = ctk.CTkOptionMenu(
            controls, variable=self.model_var, values=list(MODELS.keys()),
            width=160, command=self._on_model_change)
        self.model_menu.pack(side="left", padx=4)

        self.model_desc = ctk.CTkLabel(
            self, text=MODELS["isnet-general-use"], font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60"), wraplength=800, justify="left")
        self.model_desc.pack(fill="x", padx=20, pady=(0, 4))

        # --- Input/output paths ---
        paths_frame = ctk.CTkFrame(self, fg_color="transparent")
        paths_frame.pack(fill="x", padx=16, pady=2)

        input_row = ctk.CTkFrame(paths_frame, fg_color="transparent")
        input_row.pack(fill="x", pady=2)
        ctk.CTkLabel(input_row, text="Input:", width=50).pack(side="left")
        self.input_entry = ctk.CTkEntry(input_row, placeholder_text="Select image or folder...")
        self.input_entry.pack(side="left", fill="x", expand=True, padx=8)
        self.input_btn = ctk.CTkButton(input_row, text="Browse", width=80, command=self._browse_input)
        self.input_btn.pack(side="right")

        output_row = ctk.CTkFrame(paths_frame, fg_color="transparent")
        output_row.pack(fill="x", pady=2)
        ctk.CTkLabel(output_row, text="Output:", width=50).pack(side="left")
        self.output_entry = ctk.CTkEntry(output_row, placeholder_text="Select output folder...")
        self.output_entry.pack(side="left", fill="x", expand=True, padx=8)
        ctk.CTkButton(output_row, text="Browse", width=80, command=self._browse_output).pack(side="right")

        enable_drop(self.input_entry, self._on_input_drop)
        enable_entry_drop(self.output_entry)

        # --- Action row: Remove BG + Quality toggle ---
        action_row = ctk.CTkFrame(paths_frame, fg_color="transparent")
        action_row.pack(fill="x", pady=(6, 0))

        self.process_btn = ctk.CTkButton(
            action_row, text="Remove Background", height=36,
            font=ctk.CTkFont(size=13, weight="bold"), command=self._start_processing,
            fg_color="#ce7e4a", hover_color="#b06b3a")
        self.process_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.quality_toggle_btn = ctk.CTkButton(
            action_row, text="⚙ Quality", width=90, height=36,
            font=ctk.CTkFont(size=12), command=self._toggle_quality_panel,
            fg_color=("gray75", "gray30"), hover_color=("gray65", "gray40"),
            text_color=("gray20", "gray90"))
        self.quality_toggle_btn.pack(side="right")

        # --- Quality panel (hidden by default) ---
        self._quality_frame = ctk.CTkFrame(self, fg_color=("gray90", "gray20"), corner_radius=8)
        # Not packed yet — toggled on demand

        self._build_quality_panel(self._quality_frame)

        # --- Progress ---
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.pack(fill="x", padx=16, pady=4)
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(self, text="Ready", font=ctk.CTkFont(size=12))
        self.status_label.pack(padx=16, pady=(0, 4))

        # --- Before/After preview with slider ---
        self.preview_frame = ctk.CTkFrame(self)
        self.preview_frame.pack(fill="both", expand=True, padx=16, pady=(4, 12))

        self.canvas = ctk.CTkCanvas(self.preview_frame, highlightthickness=0, bg="#2b2b2b")
        self.canvas.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        slider_row = ctk.CTkFrame(self.preview_frame, fg_color="transparent")
        slider_row.pack(pady=(0, 8))
        ctk.CTkLabel(slider_row, text="Before", font=ctk.CTkFont(size=10),
                     text_color=("gray50", "gray60")).pack(side="left", padx=(0, 6))
        self.slider = ctk.CTkSlider(slider_row, from_=0, to=1, number_of_steps=100,
                                    width=250, command=self._on_slider_move)
        self.slider.set(0.5)
        self.slider.pack(side="left")
        ctk.CTkLabel(slider_row, text="After", font=ctk.CTkFont(size=10),
                     text_color=("gray50", "gray60")).pack(side="left", padx=(6, 0))

        self._placeholder_text = self.canvas.create_text(
            0, 0, text="Process an image to see comparison",
            fill="#666666", font=("Segoe UI", 12))
        self.canvas.bind("<Configure>", self._on_canvas_resize)

    def _build_quality_panel(self, parent):
        """Build quality controls inside the collapsible panel."""
        pad = {"padx": 16, "pady": 3}

        ctk.CTkLabel(parent, text="Quality Settings",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=16, pady=(10, 4))

        # ── Alpha Matting ──
        mat_header = ctk.CTkFrame(parent, fg_color="transparent")
        mat_header.pack(fill="x", **pad)

        self.matting_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(mat_header, text="Alpha Matting  (sharper edges, slower ~3×)",
                        variable=self.matting_var, command=self._on_matting_toggle,
                        font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")

        self._matting_controls = ctk.CTkFrame(parent, fg_color="transparent")
        self._matting_controls.pack(fill="x", padx=32, pady=(0, 4))

        self.fg_threshold_var = ctk.DoubleVar(value=240)
        self._add_slider_row(self._matting_controls, "Foreground threshold",
                             self.fg_threshold_var, 0, 255, 255,
                             "Higher = less of image treated as foreground edge")

        self.bg_threshold_var = ctk.DoubleVar(value=10)
        self._add_slider_row(self._matting_controls, "Background threshold",
                             self.bg_threshold_var, 0, 100, 100,
                             "Lower = stricter background separation")

        self.erode_size_var = ctk.DoubleVar(value=10)
        self._add_slider_row(self._matting_controls, "Erode size",
                             self.erode_size_var, 0, 40, 40,
                             "Larger = more aggressive edge tightening")

        # disable sliders initially
        self._set_matting_sliders_state("disabled")

        # separator
        ctk.CTkFrame(parent, height=1, fg_color=("gray70", "gray40")).pack(
            fill="x", padx=16, pady=6)

        # ── Post-process Cleanup ──
        self.postprocess_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(parent, text="Alpha Cleanup  (remove speckles, fill edge gaps)",
                        variable=self.postprocess_var, command=self._on_postprocess_toggle,
                        font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", **pad)

        self._cleanup_controls = ctk.CTkFrame(parent, fg_color="transparent")
        self._cleanup_controls.pack(fill="x", padx=32, pady=(0, 8))

        self.alpha_min_var = ctk.DoubleVar(value=10)
        self._add_slider_row(self._cleanup_controls, "Min alpha (speckle cutoff)",
                             self.alpha_min_var, 0, 80, 80,
                             "Pixels below this alpha → fully transparent (kills residuals)")

        self.alpha_max_var = ctk.DoubleVar(value=230)
        self._add_slider_row(self._cleanup_controls, "Max alpha (solidify threshold)",
                             self.alpha_max_var, 150, 255, 105,
                             "Pixels above this alpha → fully opaque (fills edge gaps)")

        self._set_cleanup_sliders_state("disabled")

    def _add_slider_row(self, parent, label, var, from_, to, steps, tooltip=""):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)

        ctk.CTkLabel(row, text=label, width=200, anchor="w",
                     font=ctk.CTkFont(size=11),
                     text_color=("gray40", "gray70")).pack(side="left")

        val_label = ctk.CTkLabel(row, text=str(int(var.get())), width=36,
                                 font=ctk.CTkFont(size=11))
        val_label.pack(side="right")

        slider = ctk.CTkSlider(row, from_=from_, to=to, number_of_steps=steps,
                               variable=var, width=160,
                               command=lambda v, lbl=val_label: lbl.configure(text=str(int(float(v)))))
        slider.pack(side="right", padx=(4, 4))

        if tooltip:
            ctk.CTkLabel(row, text=tooltip, font=ctk.CTkFont(size=9),
                         text_color=("gray55", "gray55")).pack(side="left", padx=(8, 0))

        # store slider ref on the var object for enable/disable
        var._slider_widget = slider

    def _set_matting_sliders_state(self, state):
        for var in (self.fg_threshold_var, self.bg_threshold_var, self.erode_size_var):
            if hasattr(var, "_slider_widget"):
                var._slider_widget.configure(state=state)

    def _set_cleanup_sliders_state(self, state):
        for var in (self.alpha_min_var, self.alpha_max_var):
            if hasattr(var, "_slider_widget"):
                var._slider_widget.configure(state=state)

    # ──────────────────────────── TOGGLE ────────────────────────────

    def _toggle_quality_panel(self):
        if self._quality_panel_visible:
            self._quality_frame.pack_forget()
            self._quality_panel_visible = False
            self.quality_toggle_btn.configure(text="⚙ Quality")
        else:
            self._quality_frame.pack(fill="x", padx=16, pady=(0, 4),
                                     before=self.progress_bar)
            self._quality_panel_visible = True
            self.quality_toggle_btn.configure(text="⚙ Quality ▲")

    def _on_matting_toggle(self):
        state = "normal" if self.matting_var.get() else "disabled"
        self._set_matting_sliders_state(state)

    def _on_postprocess_toggle(self):
        state = "normal" if self.postprocess_var.get() else "disabled"
        self._set_cleanup_sliders_state(state)

    def _get_quality_params(self):
        return {
            "alpha_matting": self.matting_var.get(),
            "fg_threshold": int(self.fg_threshold_var.get()),
            "bg_threshold": int(self.bg_threshold_var.get()),
            "erode_size": int(self.erode_size_var.get()),
            "post_process": self.postprocess_var.get(),
            "alpha_min": int(self.alpha_min_var.get()),
            "alpha_max": int(self.alpha_max_var.get()),
        }

    # ──────────────────────────── EVENTS ────────────────────────────

    def _on_canvas_resize(self, event=None):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        try:
            self.canvas.coords(self._placeholder_text, w // 2, h // 2)
        except Exception:
            pass
        if self._before_pil and self._after_pil:
            self._render_comparison()
        elif self._before_pil:
            self._render_before_only()

    def _render_before_only(self):
        if self._before_pil is None:
            return
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            self.after(100, self._render_before_only)
            return
        try:
            preview = self._before_pil.copy()
            preview.thumbnail((cw, ch), Image.BILINEAR)
            self.slider.configure(width=max(150, preview.width))
            self._tk_photo = ImageTk.PhotoImage(preview.convert("RGB"))
            self.canvas.delete("all")
            self.canvas.create_image(cw // 2, ch // 2, image=self._tk_photo, anchor="center")
        except Exception as e:
            log.warning("Failed to render before preview: %s", e)

    def _on_model_change(self, model_name):
        self.model_desc.configure(text=MODELS.get(model_name, ""))

    def _on_mode_change(self):
        self.input_entry.delete(0, "end")
        if self.mode_var.get() == "single":
            self.input_entry.configure(placeholder_text="Select image...")
        else:
            self.input_entry.configure(placeholder_text="Select folder...")

    def _on_input_drop(self, path_str):
        self.input_entry.delete(0, "end")
        self.input_entry.insert(0, path_str)
        if self.mode_var.get() == "single":
            self._load_input_preview(path_str)

    def _browse_input(self):
        if self.mode_var.get() == "single":
            path = ask_open_image()
        else:
            path = ask_open_folder()
        if path:
            self.input_entry.delete(0, "end")
            self.input_entry.insert(0, path)
            if self.mode_var.get() == "single":
                self._load_input_preview(path)

    def _load_input_preview(self, path):
        from pathlib import Path as _P
        if not _P(path).is_file():
            return
        try:
            self._before_pil = Image.open(path).convert("RGBA")
            self._after_pil = None
            self._after_nobg_pil = None
            self.status_label.configure(
                text=f"Loaded: {self._before_pil.width}x{self._before_pil.height}",
                text_color=("gray40", "gray60"))
        except Exception as e:
            log.warning("Failed to open image: %s", e)
            return
        self._render_before_only()

    def _browse_output(self):
        path = ask_open_folder()
        if path:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, path)

    # ──────────────────────────── PROCESSING ────────────────────────────

    def _start_processing(self):
        input_path = self.input_entry.get().strip()
        output_path = self.output_entry.get().strip()
        if not input_path or not output_path:
            self.status_label.configure(text="Please select input and output paths.", text_color="red")
            return

        model = self.model_var.get()
        quality_params = self._get_quality_params()
        self.process_btn.configure(state="disabled")
        self.progress_bar.set(0)

        if not model_file_exists(model):
            self.status_label.configure(
                text=f"Downloading {model} model (~170MB) — one-time, please wait...",
                text_color=("#d97706", "#fbbf24"))
            log.info("Model %s not cached locally — downloading on first use", model)
        else:
            status_parts = ["Processing..."]
            if quality_params.get("alpha_matting"):
                status_parts.append("alpha matting ON")
            if quality_params.get("post_process"):
                status_parts.append("cleanup ON")
            self.status_label.configure(text="  |  ".join(status_parts),
                                        text_color=("gray40", "gray60"))

        if self.mode_var.get() == "single":
            self._start_single(input_path, output_path, model, quality_params)
        else:
            self._start_batch(input_path, output_path, model, quality_params)

    def _start_batch(self, input_path, output_path, model, quality_params):
        providers = self.providers

        def worker(progress_cb):
            process_batch(input_path, output_path, model, providers,
                          progress_cb, quality_params=quality_params)

        start_task(self, worker, (),
                   on_progress=self._on_progress,
                   on_complete=self._on_batch_complete,
                   on_error=self._on_error)

    def _start_single(self, input_path, output_path, model, quality_params):
        from pathlib import Path
        self._before_pil = Image.open(input_path).convert("RGBA")

        def worker(progress_cb):
            session = get_session(model, self.providers)
            self._after_nobg_pil = process_single_to_pil(
                input_path, session, quality_params=quality_params)
            out_dir = Path(output_path)
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"{Path(input_path).stem}_nobg.png"
            self._after_nobg_pil.save(out_file)
            log.info("Saved: %s", out_file)
            progress_cb(1, 1)

        start_task(self, worker, (),
                   on_progress=self._on_progress,
                   on_complete=self._on_single_complete,
                   on_error=self._on_error)

    def _on_progress(self, current, total):
        self.progress_bar.set(current / total)
        self.status_label.configure(text=f"Processing {current}/{total}...")

    def _on_single_complete(self):
        self.progress_bar.set(1)
        self.status_label.configure(text="Done! Use slider to compare.",
                                    text_color=("green", "#4ade80"))
        self.process_btn.configure(state="normal")
        self._after_pil = self._after_nobg_pil
        self._render_comparison()

    def _on_batch_complete(self):
        self.progress_bar.set(1)
        self.status_label.configure(text="Batch complete! Files saved to subfolder.",
                                    text_color=("green", "#4ade80"))
        self.process_btn.configure(state="normal")

    def _on_error(self, message):
        log.error("Processing error: %s", message)
        self.status_label.configure(text=f"Error: {message}", text_color="red")
        self.process_btn.configure(state="normal")

    # ──────────────────────────── RENDERING ────────────────────────────

    def _render_comparison(self):
        if self._before_pil is None or self._after_pil is None:
            return

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        before = self._before_pil.copy()
        before.thumbnail((cw, ch), Image.BILINEAR)
        pw, ph = before.size
        self.slider.configure(width=max(150, pw))

        after = self._after_pil.copy()
        after = after.resize((pw, ph), Image.BILINEAR)
        after_display = composite_on_checker(after)

        self._display_before = before.convert("RGB")
        self._display_after = after_display
        self._preview_size = (pw, ph)

        self.canvas.delete("all")
        self._on_slider_move(self.slider.get())

    def _on_slider_move(self, value):
        if self._display_before is None or self._display_after is None:
            return

        pw, ph = self._preview_size
        split_x = int(float(value) * pw)

        left = self._display_before.crop((0, 0, split_x, ph))
        right = self._display_after.crop((split_x, 0, pw, ph))

        combined = Image.new("RGB", (pw, ph))
        combined.paste(left, (0, 0))
        combined.paste(right, (split_x, 0))

        self._tk_photo = ImageTk.PhotoImage(combined)
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, image=self._tk_photo, anchor="center")
        # Divider line
        canvas_x = (cw - pw) // 2 + split_x
        canvas_y_top = (ch - ph) // 2
        self.canvas.create_line(canvas_x, canvas_y_top, canvas_x, canvas_y_top + ph,
                                fill="#ffffff", width=2)
