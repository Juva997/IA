import os
import subprocess
import shlex


class IDEController:
    def __init__(self):
        # Store an absolute workspace root to validate file operations
        try:
            self.workspace = os.path.abspath(os.getcwd())
        except Exception:
            self.workspace = os.path.abspath(".")

    def _is_within_workspace(self, path):
        try:
            full = os.path.abspath(path)
            return os.path.commonpath([self.workspace, full]) == self.workspace
        except Exception:
            return False

    def open_file(self, data):
        try:
            path = data.get("path")

            if not path:
                return {"status": "error", "error": "path_missing"}

            # Resolve relative to workspace
            full_path = os.path.abspath(os.path.join(self.workspace, path))
            if not self._is_within_workspace(full_path):
                return {"status": "error", "error": "path_outside_workspace"}

            subprocess.Popen(["code", full_path])

            return {"status": "success", "output": f"abrindo arquivo: {full_path}"}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def open_project(self, data):
        try:
            path = data.get("path") or self.workspace

            full_path = os.path.abspath(os.path.join(self.workspace, path))
            if not self._is_within_workspace(full_path):
                return {"status": "error", "error": "path_outside_workspace"}

            subprocess.Popen(["code", full_path])

            return {"status": "success", "output": f"abrindo projeto: {full_path}"}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def run_terminal(self, data):
        try:
            command = data.get("command")

            if not command:
                return {"status": "error", "error": "command_missing"}

            # Allow list/tuple for argv style execution, otherwise parse safely
            if isinstance(command, (list, tuple)):
                args = list(command)
            elif isinstance(command, str):
                # Block shell metacharacters to avoid injection
                if any(ch in command for ch in [";", "&", "|", ">", "<", "$(`", "`", "\n"]):
                    return {"status": "error", "error": "forbidden_shell_characters"}
                try:
                    args = shlex.split(command)
                except Exception:
                    return {"status": "error", "error": "invalid_cmd_format"}
            else:
                return {"status": "error", "error": "invalid_cmd_type"}

            if not args:
                return {"status": "error", "error": "empty_command"}

            # Whitelist common dev tooling to reduce blast radius
            allowed_cmds = {"git", "pytest", "python", "pip", "pip3", "code"}
            cmd0 = os.path.basename(args[0])
            if cmd0 not in allowed_cmds:
                return {"status": "error", "error": "command_not_allowed"}

            timeout = int(data.get("timeout") or 15)

            proc = subprocess.run(args, capture_output=True, text=True, timeout=min(timeout, 60), cwd=self.workspace)
            out = (proc.stdout or "") + (proc.stderr or "")
            return {"status": "success", "output": out.strip()}

        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "command_timeout"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
