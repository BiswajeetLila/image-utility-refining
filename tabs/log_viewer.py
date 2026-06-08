import customtkinter as ctk

from utils.logger import get_log_file


class LogViewerTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._polling = False
        self._last_size = 0
        self._build_ui()
        self._start_polling()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(header, text="Session Log", font=ctk.CTkFont(size=20, weight="bold")).pack(side="left")

        self.log_path_label = ctk.CTkLabel(header, text=str(get_log_file()),
                                           font=ctk.CTkFont(size=11), text_color=("gray50", "gray60"))
        self.log_path_label.pack(side="left", padx=12)

        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right")

        ctk.CTkButton(btn_frame, text="Clear View", width=90, height=28,
                      command=self._clear_view).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="Copy All", width=90, height=28,
                      command=self._copy_all).pack(side="left", padx=4)

        # Filter row
        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=16, pady=(0, 4))

        ctk.CTkLabel(filter_frame, text="Filter:").pack(side="left")
        self.filter_entry = ctk.CTkEntry(filter_frame, placeholder_text="Type to filter lines...", width=200)
        self.filter_entry.pack(side="left", padx=8)
        self.filter_entry.bind("<KeyRelease>", lambda _: self._apply_filter())

        self.level_var = ctk.StringVar(value="ALL")
        for level in ("ALL", "INFO", "WARNING", "ERROR", "DEBUG"):
            ctk.CTkRadioButton(filter_frame, text=level, variable=self.level_var,
                               value=level, command=self._apply_filter,
                               font=ctk.CTkFont(size=11)).pack(side="left", padx=6)

        # Log text area
        self.textbox = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Courier New", size=12),
                                      wrap="none", state="disabled")
        self.textbox.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        self._tag_colors = {
            "ERROR":   "#f87171",
            "WARNING": "#fbbf24",
            "INFO":    "#86efac",
            "DEBUG":   "#93c5fd",
        }

    def _start_polling(self):
        self._polling = True
        self._poll()

    def _poll(self):
        if not self._polling:
            return
        try:
            size = get_log_file().stat().st_size
            if size != self._last_size:
                self._last_size = size
                self._reload()
        except OSError:
            pass
        self.after(1000, self._poll)

    def _reload(self):
        try:
            lines = get_log_file().read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        self._all_lines = lines
        self._apply_filter()

    def _apply_filter(self):
        lines = getattr(self, "_all_lines", [])
        keyword = self.filter_entry.get().strip().lower()
        level = self.level_var.get()

        filtered = []
        for line in lines:
            if level != "ALL" and f"[{level}]" not in line:
                continue
            if keyword and keyword not in line.lower():
                continue
            filtered.append(line)

        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        for line in filtered:
            tag = None
            for lvl, color in self._tag_colors.items():
                if f"[{lvl}]" in line:
                    tag = lvl
                    break
            if tag:
                self.textbox.insert("end", line + "\n", tag)
            else:
                self.textbox.insert("end", line + "\n")
        # Apply tag colors
        for lvl, color in self._tag_colors.items():
            self.textbox.tag_config(lvl, foreground=color)

        self.textbox.configure(state="disabled")
        self.textbox.see("end")

    def _clear_view(self):
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")
        self._all_lines = []

    def _copy_all(self):
        content = get_log_file().read_text(encoding="utf-8")
        self.clipboard_clear()
        self.clipboard_append(content)
