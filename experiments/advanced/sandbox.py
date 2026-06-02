import os
import subprocess
import tempfile


class SandboxExecutor:
    def run(self, code):
        with tempfile.TemporaryDirectory() as tmp:
            file_path = os.path.join(tmp, "script.py")

            with open(file_path, "w") as f:
                f.write(code)

            cmd = [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{tmp}:/app",
                "python:3.11",
                "python",
                "/app/script.py",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            return result.stdout or result.stderr
