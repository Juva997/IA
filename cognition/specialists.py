from actions.registry import ActionRegistry


class SpecialistRouter:
    def __init__(self):
        self.registry = ActionRegistry()
        self.registry.auto_register()

    def route(self, step, state):
        action = step.get("action")

        # código
        if action in ["run_python", "fix_code"]:
            return self._handle_code(step)

        # web
        if action in ["open_browser", "web_search"]:
            return self._handle_web(step)

        # arquivos
        if action in ["list_files", "read_file"]:
            return self._handle_files(step)

        return self._fallback(step)

    def _handle_code(self, step):
        func = self.registry.get(step["action"])
        return func(step.get("data"))

    def _handle_web(self, step):
        func = self.registry.get(step["action"])
        return func(step.get("data"))

    def _handle_files(self, step):
        func = self.registry.get(step["action"])
        return func(step.get("data"))

    def _fallback(self, step):
        func = self.registry.get(step.get("action"))
        if func:
            return func(step.get("data"))

        return f"no_handler_for: {step}"
