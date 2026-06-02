import os


class SecurityManager:
    def __init__(self, safe_root=None, allow_delete=False):
        self.safe_root = os.path.abspath(safe_root or os.getcwd())
        self.guard = Guard(self.safe_root, allow_delete=allow_delete)
        self.modify_guard = SelfModifySafe(self.safe_root)

    def validate_action(self, step):
        return self.guard.validate(step)

    def validate_write(self, path, content=None):
        return self.modify_guard.validate_write(path, content)

    def can_modify(self, path):
        return self.modify_guard.can_modify(path)


class Guard:
    def __init__(self, safe_root, allow_delete=False):
        self.safe_root = os.path.abspath(safe_root)
        self.allow_delete = allow_delete
        self.blocked_actions = {"run_command", "shell", "system"}
        self.destructive_actions = {"delete_file"}

    def validate(self, step):
        if not isinstance(step, dict):
            return False, "invalid_step"

        action = step.get("action")
        data = step.get("data", {})

        allowed, reason = self._is_action_allowed(action, data)
        if not allowed:
            return False, reason

        allowed, reason = self._is_data_safe(data)
        if not allowed:
            return False, reason

        return True, None

    def _is_action_allowed(self, action, data=None):
        if not isinstance(action, str) or not action.strip():
            return False, "missing_action"

        if action in self.blocked_actions:
            return False, f"blocked_action:{action}"

        confirmed = isinstance(data, dict) and data.get("confirm_delete") is True
        if action in self.destructive_actions and not self.allow_delete and not confirmed:
            return False, f"destructive_action_blocked:{action}"

        return True, None

    def _is_data_safe(self, data):
        if data is None:
            return True, None

        if not isinstance(data, dict):
            return False, "invalid_data"

        for key in ("path", "file_path", "filename", "directory", "folder"):
            path = data.get(key)
            if path is not None and not self._is_safe_path(path):
                return False, f"path_outside_safe_root:{key}"

        return True, None

    def _is_safe_path(self, path):
        if isinstance(path, (list, tuple)):
            return all(self._is_safe_path(item) for item in path)

        if not isinstance(path, str) or not path.strip():
            return False

        try:
            full_path = os.path.abspath(os.path.join(self.safe_root, path))
            return os.path.commonpath([self.safe_root, full_path]) == self.safe_root
        except (OSError, ValueError):
            return False


class SelfModifySafe:
    def __init__(self, safe_root=None):
        self.safe_root = os.path.abspath(safe_root or os.getcwd())
        self.allowed_paths = ["sandbox", "outputs", "temp"]
        self.blocked_paths = ["core", "security", "memory"]

    def can_modify(self, path):
        normalized = self._normalize(path)
        if normalized is None:
            return False

        return any(self._is_relative_to(normalized, allowed) for allowed in self.allowed_paths)

    def validate_write(self, path, content=None):
        normalized = self._normalize(path)
        if normalized is None:
            return False

        if any(self._is_relative_to(normalized, blocked) for blocked in self.blocked_paths):
            return False

        return self.can_modify(path)

    def _normalize(self, path):
        if not isinstance(path, str) or not path.strip():
            return None

        try:
            full_path = os.path.abspath(os.path.join(self.safe_root, path))
            if os.path.commonpath([self.safe_root, full_path]) != self.safe_root:
                return None
            return os.path.relpath(full_path, self.safe_root).replace("\\", "/")
        except (OSError, ValueError):
            return None

    def _is_relative_to(self, path, root):
        return path == root or path.startswith(root.rstrip("/") + "/")
