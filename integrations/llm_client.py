    # =========================
    # 🔥 PUBLIC API
    # =========================
import hashlib
import re
import time
import os
from urllib.parse import urljoin
import logging
import threading
import random

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils.cache import Cache

logger = logging.getLogger(__name__)


class LLMClient:
    """Client HTTP para LLMs com timeouts, retries e circuit-breaker simples.

    Config via env:
      LLM_POOL_CONNECTIONS, LLM_POOL_MAXSIZE
      LLM_CIRCUIT_THRESHOLD (default 3)
      LLM_CIRCUIT_OPEN_SECONDS (default 30)
      LLM_MAX_RETRIES (fallback to constructor)
    """

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
        self.timeout = float(timeout or 15)
        self.max_retries = int(os.environ.get("LLM_MAX_RETRIES", str(max_retries)))
        self.retry_delay = float(retry_delay or 0.2)

        self.cache = Cache(ttl=cache_ttl)
        self.session = requests.Session()

        # Configure connection pooling and retries for concurrency
        try:
            pool_conn = int(os.environ.get("LLM_POOL_CONNECTIONS", "10"))
            pool_max = int(os.environ.get("LLM_POOL_MAXSIZE", "10"))
        except Exception:
            pool_conn = 10
            pool_max = 10

        try:
            retry_strategy = Retry(
                total=max(0, int(self.max_retries)),
                backoff_factor=0.2,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "POST"],
            )
        except Exception:
            retry_strategy = None

        try:
            adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=pool_conn, pool_maxsize=pool_max)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
        except Exception:
            pass

        # circuit breaker state
        self._lock = threading.Lock()
        self._failure_count = 0
        self._circuit_open_until = 0
        self._half_open_attempts = 0

        # config
        try:
            self._circuit_threshold = int(os.environ.get("LLM_CIRCUIT_THRESHOLD", "3"))
        except Exception:
            self._circuit_threshold = 3
        try:
            self._circuit_open_seconds = int(os.environ.get("LLM_CIRCUIT_OPEN_SECONDS", "30"))
        except Exception:
            self._circuit_open_seconds = 30

    # =========================
    # 🔥 PUBLIC API
    # =========================
    def generate(self, prompt):
        """Generate text from prompt with retries, backoff and circuit-breaker."""
        if not isinstance(prompt, str):
            return self._error("invalid_prompt")

        now = time.time()
        with self._lock:
            if getattr(self, "_circuit_open_until", 0) > now:
                return self._error("circuit_open")

        cache_key = self._build_cache_key(prompt)
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        attempt = 0
        while attempt <= self.max_retries:
            try:
                resp = self._make_request(prompt)

                if resp is None:
                    # treat as failure
                    with self._lock:
                        self._failure_count += 1
                        if self._failure_count >= self._circuit_threshold:
                            self._circuit_open_until = time.time() + self._circuit_open_seconds
                            self._failure_count = 0
                            return self._error("circuit_open_after_failures")
                    return self._error("no_response")

                if resp.status_code != 200:
                    # record failure
                    with self._lock:
                        self._failure_count += 1
                        if self._failure_count >= self._circuit_threshold:
                            self._circuit_open_until = time.time() + self._circuit_open_seconds
                            self._failure_count = 0
                            return self._error("circuit_open_after_failures")

                    if attempt < self.max_retries:
                        backoff = self.retry_delay * (2 ** attempt) + random.uniform(0, self.retry_delay)
                        time.sleep(backoff)
                        attempt += 1
                        continue

                    return self._error(f"http_error: {resp.status_code}")

                text = self._extract_text(resp)
                text = self._clean_response(text)

                # success -> reset failure counters
                with self._lock:
                    self._failure_count = 0
                    self._half_open_attempts = 0

                self._save_cache(cache_key, text)
                return text

            except requests.exceptions.Timeout:
                # timeout -> retry with backoff
                if attempt < self.max_retries:
                    backoff = self.retry_delay * (2 ** attempt) + random.uniform(0, self.retry_delay)
                    time.sleep(backoff)
                    attempt += 1
                    continue

                with self._lock:
                    self._failure_count += 1
                return self._error("timeout_llm")

            except requests.exceptions.RequestException:
                # connection / other request errors
                if attempt < self.max_retries:
                    backoff = self.retry_delay * (2 ** attempt) + random.uniform(0, self.retry_delay)
                    time.sleep(backoff)
                    attempt += 1
                    continue

                with self._lock:
                    self._failure_count += 1
                    if self._failure_count >= self._circuit_threshold:
                        self._circuit_open_until = time.time() + self._circuit_open_seconds
                        self._failure_count = 0
                        return self._error("circuit_open_after_failures")

                return self._error("llm_request_error")

            except Exception as e:
                # unknown error -> retry if possible
                if attempt < self.max_retries:
                    backoff = self.retry_delay * (2 ** attempt) + random.uniform(0, self.retry_delay)
                    time.sleep(backoff)
                    attempt += 1
                    continue

                with self._lock:
                    self._failure_count += 1
                return self._error(f"erro_llm_local: {str(e)}")

    # =========================
    # 🌐 REQUEST
    # =========================
    def _make_request(self, prompt):
        try:
            return self.session.post(self.url, json=self._build_payload(prompt), timeout=self.timeout)
        except requests.exceptions.Timeout:
            raise
        except requests.exceptions.RequestException:
            # propagate to caller to handle retries / circuit
            raise

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
