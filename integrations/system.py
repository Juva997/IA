import subprocess

import psutil


class SystemController:
    def list_processes(self, data=None):
        try:
            processes = [p.info for p in psutil.process_iter(attrs=["pid", "name"])]

            return {"status": "success", "output": processes}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def kill_process(self, data):
        try:
            pid = data.get("pid")

            if not pid:
                return {"status": "error", "error": "pid_missing"}

            p = psutil.Process(pid)
            p.terminate()

            return {"status": "success", "output": f"processo {pid} encerrado"}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def system_info(self, data=None):
        try:
            return {
                "status": "success",
                "output": {
                    "cpu": psutil.cpu_percent(),
                    "memory": psutil.virtual_memory().percent,
                    "disk": psutil.disk_usage("/").percent,
                },
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def run_command(self, data):
        try:
            cmd = data.get("cmd")

            if not cmd:
                return {"status": "error", "error": "cmd_missing"}

            # Allow list/tuple of args for explicit argv execution
            timeout = 10
            if isinstance(data, dict) and data.get("timeout"):
                try:
                    timeout = max(1, int(data.get("timeout")))
                except Exception:
                    pass

            if isinstance(cmd, (list, tuple)):
                args = list(cmd)
            elif isinstance(cmd, str):
                # Block common shell metacharacters to avoid shell injection
                forbidden = ["|", "&", ";", ">", "<", "$(`", "`", "\n"]
                if any(ch in cmd for ch in ("|", "&", ";", ">", "<", "$(`", "`", "\n")):
                    return {"status": "error", "error": "forbidden_shell_characters"}
                try:
                    import shlex

                    args = shlex.split(cmd)
                except Exception:
                    return {"status": "error", "error": "invalid_cmd_format"}
            else:
                return {"status": "error", "error": "invalid_cmd_type"}

            try:
                proc = subprocess.run(args, capture_output=True, text=True, timeout=min(timeout, 60), shell=False)
                out = (proc.stdout or "") + (proc.stderr or "")
                return {"status": "success", "output": out.strip()}
            except subprocess.TimeoutExpired:
                return {"status": "error", "error": "command_timeout"}
            except Exception as e:
                return {"status": "error", "error": str(e)}

        except Exception as e:
            return {"status": "error", "error": str(e)}
