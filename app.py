import customtkinter as ctk

from tabs.bg_removal import BgRemovalTab
from tabs.grid_split import GridSplitTab
from tabs.atlas_creator import AtlasCreatorTab
from tabs.image_tools import ImageToolsTab
from tabs.batch_convert import BatchConvertTab
from tabs.log_viewer import LogViewerTab
from utils.logger import get_logger

log = get_logger("app")

TABS = [
    ("BG Removal", BgRemovalTab),
    ("Grid Split", GridSplitTab),
    ("Atlas Creator", AtlasCreatorTab),
    ("Image Tools", ImageToolsTab),
    ("Batch Convert", BatchConvertTab),
    ("Logs", LogViewerTab),
]


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Image Utility")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # --- DPI-aware sizing ---
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        log.info("Screen resolution: %dx%d", screen_w, screen_h)

        # Scale window to ~75% of screen
        win_w = max(900, int(screen_w * 0.75))
        win_h = max(600, int(screen_h * 0.75))
        self.geometry(f"{win_w}x{win_h}")
        self.minsize(800, 500)

        # Widget scaling for high-DPI: shrink slightly on 4K so controls stay compact
        if screen_h > 2000:
            ctk.set_widget_scaling(0.85)
            log.info("4K detected — widget scaling set to 0.85")
        elif screen_h > 1440:
            ctk.set_widget_scaling(0.9)
            log.info("QHD detected — widget scaling set to 0.9")

        # Center on screen
        x = (screen_w - win_w) // 2
        y = (screen_h - win_h) // 2
        self.geometry(f"+{x}+{y}")

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=6, pady=6)

        for name, TabClass in TABS:
            tab_frame = self.tabview.add(name)
            TabClass(tab_frame).pack(fill="both", expand=True)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        log.info("App closing — releasing sessions")
        try:
            from core.bg_worker import clear_sessions
            clear_sessions()
        except Exception:
            pass
        try:
            from core.upscale_worker import clear_esrgan_sessions
            clear_esrgan_sessions()
        except Exception:
            pass
        self.destroy()
        # Force-kill process — onnxruntime native threads don't exit cleanly
        import os
        os._exit(0)
