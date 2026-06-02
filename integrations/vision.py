import time


class VisionSystem:
    def __init__(self):
        self.last_capture = None

    def capture_screen(self, data=None):
        try:
            from PIL import ImageGrab

            img = ImageGrab.grab()
            self.last_capture = img

            return {"status": "success", "output": {"size": img.size}}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def analyze(self, data=None):
        if self.last_capture is None:
            return {"status": "error", "error": "no_image"}

        return {"status": "success", "output": {"size": self.last_capture.size}}

    def watch_loop(self, interval=2):
        while True:
            self.capture_screen()
            print("[VISION] frame capturado")
            time.sleep(interval)


# =========================
# 👁️ STANDALONE FUNCTIONS
# =========================
def analyze_screen(data=None, state=None):
    return VisionSystem().capture_screen(data)
