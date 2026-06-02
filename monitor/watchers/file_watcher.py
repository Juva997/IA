import os
import time


class FileWatcher:
    def watch(self, path, callback, interval=2):
        last_state = set(os.listdir(path))

        while True:
            time.sleep(interval)
            current = set(os.listdir(path))

            added = current - last_state
            removed = last_state - current

            if added or removed:
                callback({"added": list(added), "removed": list(removed)})

            last_state = current
