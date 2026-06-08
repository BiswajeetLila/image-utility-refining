import threading
import queue


class TaskThread(threading.Thread):
    def __init__(self, target_fn, args, result_queue):
        super().__init__(daemon=True)
        self.target_fn = target_fn
        self.args = args
        self.result_queue = result_queue

    def run(self):
        try:
            self.target_fn(*self.args)
            self.result_queue.put({"status": "done"})
        except Exception as e:
            self.result_queue.put({"status": "error", "message": str(e)})


def make_progress_callback(result_queue):
    def callback(current, total):
        result_queue.put({"status": "progress", "current": current, "total": total})
    return callback


def start_task(widget, fn, args, on_progress, on_complete, on_error):
    result_queue = queue.Queue()
    progress_cb = make_progress_callback(result_queue)
    thread = TaskThread(fn, (*args, progress_cb), result_queue)
    thread.start()

    def poll():
        try:
            while True:
                msg = result_queue.get_nowait()
                if msg["status"] == "progress":
                    on_progress(msg["current"], msg["total"])
                elif msg["status"] == "done":
                    on_complete()
                    return
                elif msg["status"] == "error":
                    on_error(msg["message"])
                    return
        except queue.Empty:
            pass
        widget.after(50, poll)

    widget.after(50, poll)
