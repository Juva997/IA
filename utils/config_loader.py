class ConfigLoader:
    def __init__(self, path="config.json"):
        self.path = path
        self.config = self._load()

    def _load(self):
        import json
        import os

        if not os.path.exists(self.path):
            return {}

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def get(self, key, default=None):
        import os

        # ENV tem prioridade
        env = os.getenv(key.upper().replace(".", "_"))
        if env:
            return env

        return self._get_nested(key, default)

    def _get_nested(self, key, default):
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value
