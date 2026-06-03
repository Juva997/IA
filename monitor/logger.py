import datetime
import os
import threading


class Logger:
    def __init__(self, diag_log_path="data/logs/diagnostic_errors.log"):
        self._diag_log_path = diag_log_path
        self._lock = threading.Lock()

    def log(self, level, message):
        output = f"[{datetime.datetime.now()}] [{level}] {message}"
        try:
            print(output)
        except UnicodeEncodeError:
            print(output.encode("ascii", errors="replace").decode("ascii"))

        # Se for uma mensagem de diagnóstico (marcada por [DIAGNOSTIC]), grave em arquivo
        try:
            msg_upper = str(message).upper()
            if "[DIAGNOSTIC]" in msg_upper or "DIAGNOSTIC" in msg_upper:
                dirpath = os.path.dirname(self._diag_log_path)
                if dirpath and not os.path.exists(dirpath):
                    os.makedirs(dirpath, exist_ok=True)
                with self._lock:
                    with open(self._diag_log_path, "a", encoding="utf-8") as fh:
                        fh.write(output + "\n")
        except Exception:
            # Não interrompa a execução do logger por falha em escrita de arquivo
            pass

    def info(self, msg):
        self.log("INFO", msg)

    def error(self, msg):
        self.log("ERROR", msg)

    def debug(self, msg):
        self.log("DEBUG", msg)
