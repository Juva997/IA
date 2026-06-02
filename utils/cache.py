import time


class Cache:
    def __init__(self, ttl=300):
        self.store = {}
        self.ttl = ttl

    def set(self, key, value):
        self.store[key] = {"value": value, "time": time.time()}

    def get(self, key):
        item = self.store.get(key)

        if not item:
            return None

        if time.time() - item["time"] > self.ttl:
            del self.store[key]
            return None

        return item["value"]

    def clear(self):
        self.store.clear()
