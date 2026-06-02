import datetime


class Logger:
    def log(self, level, message):
        output = f"[{datetime.datetime.now()}] [{level}] {message}"
        try:
            print(output)
        except UnicodeEncodeError:
            print(output.encode("ascii", errors="replace").decode("ascii"))

    def info(self, msg):
        self.log("INFO", msg)

    def error(self, msg):
        self.log("ERROR", msg)

    def debug(self, msg):
        self.log("DEBUG", msg)
