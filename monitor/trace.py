class Trace:
    def __init__(self):
        self.events = []

    def add(self, event, data):
        self.events.append({"event": event, "data": data})

    def get(self):
        return self.events
