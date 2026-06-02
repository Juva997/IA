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

            result = subprocess.getoutput(cmd)

            return {"status": "success", "output": result}

        except Exception as e:
            return {"status": "error", "error": str(e)}
