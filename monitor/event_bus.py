class EventBus:
    def __init__(self):
        self.listeners = {}

    def on(self, event, callback):
        if event not in self.listeners:
            self.listeners[event] = []

        self.listeners[event].append(callback)

    def emit(self, event, data):
        if event in self.listeners:
            for cb in self.listeners[event]:
                try:
                    cb(data)
                except Exception:
                    pass
