"""Drag & drop helper using windnd (Windows only, ctypes-based).

Strategy: hook the top-level window ONCE, then route drops to whichever
registered entry widget the cursor is nearest to (or last focused).
This avoids issues with customtkinter compound widgets where child HWNDs
swallow WM_DROPFILES before the hooked parent sees them.

Routing only considers widgets that are currently VIEWABLE (i.e., live in
the active CTkTabview tab). Inactive-tab widgets retain layout coordinates
that overlap the active tab, so without a viewable filter the wrong tab's
callback may fire.
"""

import sys
import traceback
from pathlib import Path

from utils.logger import get_logger

log = get_logger("dnd")

_HAS_WINDND = False
if sys.platform == "win32":
    try:
        import windnd
        _HAS_WINDND = True
    except ImportError:
        pass

# Registry: top-level window -> list of (widget, callback)
_hooked_windows = {}   # {toplevel_id: True}
_drop_targets = []     # [(entry_widget, callback)]


def _get_toplevel(widget):
    """Walk up to find the real Tk toplevel window."""
    try:
        return widget.winfo_toplevel()
    except Exception:
        return None


def _is_viewable(widget):
    """True only if the widget AND all ancestors are mapped/raised. Returns
    False for widgets inside an inactive CTkTabview tab."""
    try:
        return bool(widget.winfo_viewable())
    except Exception:
        return False


def _safe_invoke(widget, callback, path_str):
    """Schedule callback via after() so it runs OUTSIDE the windnd
    WM_DROPFILES handler context. Calling PIL.ImageTk / update_idletasks
    from inside the native message handler can cause silent native crashes
    due to Tk reentrancy. Deferring via after(0, ...) lets the current
    message return first.
    """
    def _run():
        try:
            callback(path_str)
        except Exception:
            log.error("Drop callback failed for widget %s on path %r:\n%s",
                      widget, path_str, traceback.format_exc())

    try:
        widget.after(10, _run)
        return True
    except Exception:
        log.error("Drop after() schedule failed for widget %s:\n%s",
                  widget, traceback.format_exc())
        return False


def _global_drop_handler(paths):
    """Called when any file is dropped on a hooked window.
    Routes to a registered, currently viewable target by focus, then mouse
    position, then first-visible fallback."""
    if not paths:
        return
    raw = paths[0]
    path_str = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
    path_str = path_str.strip('"').strip()

    if not Path(path_str).exists():
        log.warning("Dropped path does not exist: %s", path_str)
        return

    log.debug("Drop received: %s", path_str)

    # Build the viewable subset once. All routing only considers these.
    viewable = [(w, cb) for w, cb in _drop_targets if _is_viewable(w)]
    if not viewable:
        log.warning("No viewable drop targets at drop time")
        return

    log.debug("Viewable targets: %d / %d total", len(viewable), len(_drop_targets))

    # 1. Focus-based routing
    for widget, callback in viewable:
        try:
            if widget.focus_get() == widget or _is_child_focused(widget):
                log.debug("Routing by focus -> %s", widget)
                _safe_invoke(widget, callback, path_str)
                return
        except Exception:
            pass

    # 2. Mouse-over routing
    for widget, callback in viewable:
        try:
            if _mouse_over_widget(widget):
                log.debug("Routing by mouse-over -> %s", widget)
                _safe_invoke(widget, callback, path_str)
                return
        except Exception:
            pass

    # 3. Fallback: first viewable target
    widget, callback = viewable[0]
    log.debug("Routing by first-viewable fallback -> %s", widget)
    _safe_invoke(widget, callback, path_str)


def _is_child_focused(widget):
    """Check if focus is on widget or any of its children."""
    try:
        focused = widget.focus_get()
        if focused is None:
            return False
        w = focused
        while w is not None:
            if w == widget:
                return True
            try:
                w = w.master
            except AttributeError:
                break
        return False
    except Exception:
        return False


def _mouse_over_widget(widget):
    """Check if the mouse pointer is currently over the widget."""
    try:
        mx = widget.winfo_pointerx()
        my = widget.winfo_pointery()
        wx = widget.winfo_rootx()
        wy = widget.winfo_rooty()
        ww = widget.winfo_width()
        wh = widget.winfo_height()
        return wx <= mx <= wx + ww and wy <= my <= wy + wh
    except Exception:
        return False


def _ensure_toplevel_hooked(widget):
    """Hook windnd on the top-level window if not already hooked."""
    toplevel = _get_toplevel(widget)
    if toplevel is None:
        return

    tid = id(toplevel)
    if tid in _hooked_windows:
        return

    try:
        windnd.hook_dropfiles(toplevel, func=_global_drop_handler)
        _hooked_windows[tid] = True
        log.debug("Hooked drag-drop on toplevel: %s", toplevel.title())
    except Exception as e:
        log.warning("Failed to hook drag-drop on toplevel: %s", e)


def enable_drop(widget, callback, *, files_only=True):
    """Register *widget* as a drop target. *callback(path_str)* called with
    the first dropped file path when a file is dropped near this widget.

    If *files_only* is True (default), only calls back for existing files/dirs.
    """
    if not _HAS_WINDND:
        log.debug("windnd not available — drag-and-drop disabled")
        return

    def safe_callback(path_str):
        if files_only and not Path(path_str).exists():
            return
        callback(path_str)

    _drop_targets.append((widget, safe_callback))
    widget.after(200, lambda: _ensure_toplevel_hooked(widget))


def enable_entry_drop(entry_widget):
    """Convenience: dropping a file/folder onto an entry fills it."""
    def _fill(path_str):
        entry_widget.delete(0, "end")
        entry_widget.insert(0, path_str)

    enable_drop(entry_widget, _fill)

    # Give the entry focus on click so drop routing works
    entry_widget.bind("<Button-1>", lambda e: entry_widget.focus_set(), add="+")
