"""Best-effort request logging: bounded queue, isolated file/stream failures."""
import json
import logging
from pathlib import Path
from queue import Full, Queue
import threading


class RequestLog:
    def __init__(self, path=None, stdout=False, capacity=1000):
        self.path = Path(path) if path else None
        self.stdout = stdout
        self.queue = Queue(maxsize=capacity)
        self.dropped = 0
        self.errors = 0
        threading.Thread(target=self._write, daemon=True, name="request-log").start()

    def submit(self, record):
        try:
            self.queue.put_nowait(record)
        except Full:
            self.dropped += 1
            if self.dropped == 1:
                logging.warning("Request log queue full; records may be dropped")

    def _write(self):
        while True:
            record = self.queue.get()
            try:
                line = json.dumps(record)
                if self.path:
                    try:
                        self.path.parent.mkdir(parents=True, exist_ok=True)
                        with self.path.open("a") as stream:
                            stream.write(line + "\n")
                    except OSError:
                        self.errors += 1
                        if self.errors == 1:
                            logging.exception("Request log write failed; prediction continues")
                if self.stdout:
                    print("CH6_REQUEST " + line, flush=True)
            except Exception:
                self.errors += 1
                logging.exception("Request logging failed; prediction continues")
            finally:
                self.queue.task_done()
