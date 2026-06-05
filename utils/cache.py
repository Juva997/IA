import time
import threading


class Cache:
    def __init__(self, ttl=300, max_items=None):
        self.store = {}
        self.ttl = ttl
        self.lock = threading.Lock()
        # Optional max entries to avoid unbounded memory growth
        self.max_items = int(max_items) if max_items else None

    def set(self, key, value):
        with self.lock:
            self.store[key] = {"value": value, "time": time.time()}
            if self.max_items and len(self.store) > self.max_items:
                # evict oldest entry
                try:
                    oldest = min(self.store.items(), key=lambda kv: kv[1]["time"])[0]
                    del self.store[oldest]
                except Exception:
                    pass

    def get(self, key):
        with self.lock:
            item = self.store.get(key)

            if not item:
                return None

            if time.time() - item["time"] > self.ttl:
                try:
                    del self.store[key]
                except Exception:
                    pass
                return None

            return item["value"]

    def clear(self):
        with self.lock:
            self.store.clear()
