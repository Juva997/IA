import webbrowser

import requests


class BrowserController:
    def open(self, data):
        try:
            url = data.get("url")

            if not url:
                return {"status": "error", "error": "url_missing"}

            if not url.startswith("http"):
                url = "https://" + url

            webbrowser.open(url)

            return {"status": "success", "output": f"abrindo: {url}"}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def fetch(self, data):
        try:
            url = data.get("url")

            if not url:
                return {"status": "error", "error": "url_missing"}

            r = requests.get(url, timeout=10)

            return {"status": "success", "output": r.text[:1500]}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def search_google(self, data):
        query = data.get("query")
        return self.open({"url": f"https://www.google.com/search?q={query}"})


# =========================
# 🔗 STANDALONE FUNCTIONS
# =========================
def open_browser(data, state=None):
    return BrowserController().open(data)
