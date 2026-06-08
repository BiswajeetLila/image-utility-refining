import os
import sys
import threading
import time
from pathlib import Path

# PyInstaller --windowed builds have sys.stdout / sys.stderr == None.
# Anything that calls .write() on them (tqdm, pooch downloaders, print()) will crash.
# Replace them with devnull writers before importing anything that might write.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))

import customtkinter as ctk


def _build_splash():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    splash = ctk.CTk()
    splash.title("Image Utility — Starting up")
    splash.geometry("620x440")
    splash.resizable(False, False)

    ctk.CTkLabel(splash, text="Image Utility", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(20, 2))
    status = ctk.CTkLabel(splash, text="Initializing...", font=ctk.CTkFont(size=13))
    status.pack(pady=(0, 6))

    progress = ctk.CTkProgressBar(splash, mode="indeterminate")
    progress.pack(padx=40, pady=(0, 8), fill="x")
    progress.start()

    term = ctk.CTkTextbox(splash, font=ctk.CTkFont(family="Courier New", size=11),
                          fg_color="#0d0d0d", text_color="#d4d4d4", wrap="none", state="disabled")
    term.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    return splash, status, progress, term


def _make_logger(splash, status, term):
    def set_status(msg):
        splash.after(0, lambda: status.configure(text=msg))

    def log_line(line):
        def _append():
            term.configure(state="normal")
            term.insert("end", line + "\n")
            term.configure(state="disabled")
            term.see("end")
        splash.after(0, _append)

    return set_status, log_line


def _do_startup(splash, status, progress, term, on_done):
    set_status, log_line = _make_logger(splash, status, term)

    def task():
        from utils.logger import get_logger, get_log_file
        log = get_logger("startup")
        log_line(f"[init] log file: {get_log_file()}")
        log_line(f"[init] Python {sys.version.split()[0]} on {sys.platform}")

        set_status("Loading image processing modules...")
        log_line("[init] importing onnxruntime (CPU)...")
        import onnxruntime as ort
        log_line(f"[init] ONNX providers: {', '.join(ort.get_available_providers())}")

        log_line("[init] importing rembg, PIL, numpy...")
        import rembg  # noqa: F401
        import PIL  # noqa: F401
        import numpy  # noqa: F401

        set_status("Seeding model cache...")
        log_line("[init] copying bundled models to user cache (one-time)...")
        from core.bg_worker import seed_model_cache, prewarm
        seed_model_cache()

        set_status("Pre-warming background removal model...")
        log_line("[init] pre-warming isnet-general-use session...")
        prewarm("isnet-general-use")

        set_status("Checking AI upscale model...")
        log_line("[init] checking Real-ESRGAN model...")
        from core.upscale_worker import model_exists as esrgan_exists, prewarm_esrgan
        if esrgan_exists():
            log_line("[init] Real-ESRGAN model found, pre-warming...")
            prewarm_esrgan()
        else:
            log_line("[init] Real-ESRGAN model not found — upscale disabled")

        set_status("Ready!")
        log_line("[init] startup complete")
        time.sleep(0.3)
        splash.after(0, on_done)

    threading.Thread(target=task, daemon=True).start()


def main():
    splash, status, progress, term = _build_splash()

    def on_done():
        progress.stop()
        splash.quit()

    _do_startup(splash, status, progress, term, on_done=on_done)
    splash.mainloop()
    splash.destroy()

    from app import App
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
