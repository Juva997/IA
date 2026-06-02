import hashlib
import re
import time
from urllib.parse import urljoin
import logging

import requests

from utils.cache import Cache

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(
        self,
        model="llama3",
        base_url="http://localhost:11434/api/generate",
        timeout=15,
        cache_ttl=120,
        max_retries=0,
        retry_delay=0.2,
    ):
        self.model = model
        self.url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self.cache = Cache(ttl=cache_ttl)
        self.session = requests.Session()

    # =========================
    # 🔥 PUBLIC API
    # =========================
    def generate(self, prompt):
        if not isinstance(prompt, str):
            return self._error("invalid_prompt")

        cache_key = self._build_cache_key(prompt)

        cached = self._get_cached(cache_key)
        if cached:
            return cached

        attempt = 0
        while attempt <= self.max_retries:
            try:
                response = self._make_request(prompt)

                if response is None:
                    return self._error("no_response")

                if response.status_code != 200:
                    if attempt < self.max_retries:
                        attempt += 1
                        time.sleep(self.retry_delay)
                        continue
                    return self._error(f"http_error: {response.status_code}")

                text = self._extract_text(response)
                text = self._clean_response(text)

                self._save_cache(cache_key, text)

                return text

            except requests.exceptions.Timeout:
                if attempt < self.max_retries:
                    attempt += 1
                    time.sleep(self.retry_delay)
                    continue
                return self._error("timeout_llm")

            except requests.exceptions.ConnectionError:
                if attempt < self.max_retries:
                    attempt += 1
                    time.sleep(self.retry_delay)
                    continue
                return self._error("llm_offline_or_not_running")

            except Exception as e:
                if attempt < self.max_retries:
                    attempt += 1
                    time.sleep(self.retry_delay)
                    continue
                return self._error(f"erro_llm_local: {str(e)}")

    # =========================
    # 🌐 REQUEST
    # =========================
    def _make_request(self, prompt):
        return self.session.post(
            self.url, json=self._build_payload(prompt), timeout=self.timeout
        )

    def _build_payload(self, prompt):
        return {"model": self.model, "prompt": prompt, "stream": False}

    # =========================
    # 📦 RESPONSE HANDLING
    # =========================
    def _extract_text(self, response):
        try:
            data = response.json()
        except Exception:
            return response.text or ""

        if isinstance(data, dict):
            return (
                data.get("response", "")
                or data.get("output", "")
                or data.get("text", "")
            )

        return str(data)

    # =========================
    # 🧠 CACHE
    # =========================
    def _get_cached(self, key):
        try:
            return self.cache.get(key)
        except Exception:
            return None

    def _save_cache(self, key, value):
        try:
            self.cache.set(key, value)
        except Exception:
            pass

    # =========================
    # 🔑 CACHE KEY
    # =========================
    def _build_cache_key(self, prompt):
        key = f"{self.model}|{self.url}|{prompt}"
        return hashlib.md5(key.encode("utf-8")).hexdigest()

    # =========================
    # 🧹 CLEAN RESPONSE
    # =========================
    def _clean_response(self, text):
        if not text:
            return ""

        cleaned = text.strip()
        cleaned = re.sub(r"```[a-zA-Z0-9_-]*", "", cleaned)
        cleaned = cleaned.replace("```", "")
        return cleaned.strip()

    # =========================
    # ❌ ERROR FORMAT
    # =========================
    def _error(self, message):
        return f"[LLM_ERROR] {message}"

    # =========================
    # 🧰 HEALTH CHECK
    # =========================
    def health_check(self):
        # Try multiple candidate endpoints to determine reachability.
        candidates = [
            urljoin(self._get_health_url().rstrip("/") + "/", "health"),
            self._get_health_url(),
            self._get_tags_url(),
            self.url,
        ]

        for c in candidates:
            try:
                resp = self.session.get(c, timeout=self._probe_timeout())
                # 200 means healthy. 401/403 indicate reachable but auth-protected.
                if resp.status_code == 200:
                    return True
                if resp.status_code in (401, 403):
                    return True
                logger.debug("health_check: %s returned status %s", c, resp.status_code)
            except Exception as e:
                logger.debug("health_check: request to %s failed: %s", c, e)
                continue

        return False

    def list_models(self):
        # Probe several candidate endpoints and accept different response shapes
        candidates = [
            self._get_tags_url(),
            urljoin(self._get_health_url().rstrip("/") + "/", "api/models"),
            urljoin(self._get_health_url().rstrip("/") + "/", "models"),
            urljoin(self._get_health_url().rstrip("/") + "/", "tags"),
            self.url,
        ]

        names = []
        for c in candidates:
            try:
                resp = self.session.get(c, timeout=self._probe_timeout())
            except Exception as e:
                logger.debug("list_models: request to %s failed: %s", c, e)
                continue

            if resp is None:
                continue

            if resp.status_code != 200:
                logger.debug("list_models: %s returned status %s", c, resp.status_code)
                continue

            try:
                data = resp.json()
            except Exception:
                logger.debug("list_models: %s returned non-json response", c)
                continue

            # data may be {"models": [...]}, {"tags": [...]}, {"results": [...]}, or a list
            candidate_list = []
            if isinstance(data, dict):
                if "models" in data and isinstance(data["models"], list):
                    candidate_list = data["models"]
                elif "tags" in data and isinstance(data["tags"], list):
                    candidate_list = data["tags"]
                elif "results" in data and isinstance(data["results"], list):
                    candidate_list = data["results"]
            elif isinstance(data, list):
                candidate_list = data

            for item in candidate_list:
                if isinstance(item, str):
                    names.append(item)
                elif isinstance(item, dict):
                    name = item.get("name") or item.get("model") or item.get("id")
                    if name:
                        names.append(str(name))

            if names:
                return sorted(set(names))

        return []

    def health_details(self):
        models = self.list_models()
        reachable = bool(models) or self.health_check()
        return {
            "base_url": self._get_health_url(),
            "generate_url": self.url,
            "reachable": reachable,
            "model": self.model,
            "model_available": self.model in models if models else None,
            "models": models,
        }

    def _get_health_url(self):
        if self.url.endswith("/api/generate"):
            return self.url[: self.url.rfind("/api/generate")]
        return self.url

    def _get_tags_url(self):
        base = self._get_health_url().rstrip("/") + "/"
        return urljoin(base, "api/tags")

    def _probe_timeout(self):
        try:
            return max(0.5, min(float(self.timeout), 3.0))
        except (TypeError, ValueError):
            return 3.0

    # =========================
    # 🧹 CLEAR CACHE
    # =========================
    def clear_cache(self):
        try:
            self.cache.clear()
        except Exception:
            pass
