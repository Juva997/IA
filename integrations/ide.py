import os
import subprocess


class IDEController:
    def __init__(self):
        self.workspace = os.getcwd()

    def open_file(self, data):
        try:
            path = data.get("path")

            if not path:
                return {"status": "error", "error": "path_missing"}

            subprocess.Popen(["code", path])

            return {"status": "success", "output": f"abrindo arquivo: {path}"}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def open_project(self, data):
        try:
            path = data.get("path") or self.workspace

            subprocess.Popen(["code", path])

            return {"status": "success", "output": f"abrindo projeto: {path}"}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def run_terminal(self, data):
        try:
            command = data.get("command")

            if not command:
                return {"status": "error", "error": "command_missing"}

            result = os.popen(command).read()

            return {"status": "success", "output": result}

        except Exception as e:
            return {"status": "error", "error": str(e)}
