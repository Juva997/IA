import hashlib
import os
import re
import tempfile
from typing import Any

from actions.executor import Executor
from actions.registry import ActionRegistry
from cognition.agent import Agent
from cognition.critic import Critic
from cognition.planner import Planner
from cognition.reasoning import Reasoning
from core.engine import AutonomousEngine
from core.llm_router import LLMRouter
from core.router import create_default_router
from integrations.llm_client import LLMClient
from memory.memory import Memory
from memory.retriever import Retriever
from memory.vector_store import VectorStore
from utils.config_loader import ConfigLoader


_SecurityManager: Any = None
try:
    from security.security import SecurityManager as _ImportedSecurityManager

    _SecurityManager = _ImportedSecurityManager
except Exception:
    pass


# Se o módulo de segurança não estiver disponível, fornecer um fallback
if _SecurityManager is None:
    import os as _os

    class _FallbackGuard:
        def __init__(self, safe_root, allow_delete=False):
            self.safe_root = _os.path.abspath(safe_root or _os.getcwd())
            self.allow_delete = allow_delete
            self.blocked_actions = {"run_command", "shell", "system"}
            self.destructive_actions = {"delete_file"}

        def validate(self, step):
            if not isinstance(step, dict):
                return False, "invalid_step"

            action = step.get("action")
            data = step.get("data", {})

            if not isinstance(action, str) or not action.strip():
                return False, "missing_action"

            if action in self.blocked_actions:
                return False, f"blocked_action:{action}"

            confirmed = isinstance(data, dict) and data.get("confirm_delete") is True
            if action in self.destructive_actions and not self.allow_delete and not confirmed:
                return False, f"destructive_action_blocked:{action}"

            for key in ("path", "file_path", "filename", "directory", "folder"):
                path = data.get(key)
                if path is not None:
                    try:
                        full_path = _os.path.abspath(_os.path.join(self.safe_root, path))
                        if _os.path.commonpath([self.safe_root, full_path]) != self.safe_root:
                            return False, f"path_outside_safe_root:{key}"
                    except Exception:
                        return False, f"path_outside_safe_root:{key}"

            return True, None


    class _FallbackSelfModifySafe:
        def __init__(self, safe_root=None):
            self.safe_root = _os.path.abspath(safe_root or _os.getcwd())
            self.allowed_paths = ["sandbox", "outputs", "temp"]
            self.blocked_paths = ["core", "security", "memory"]

        def can_modify(self, path):
            normalized = self._normalize(path)
            if normalized is None:
                return False
            return any(self._is_relative_to(normalized, allowed) for allowed in self.allowed_paths)

        def validate_write(self, path, content=None):
            normalized = self._normalize(path)
            if normalized is None:
                return False

            if any(self._is_relative_to(normalized, blocked) for blocked in self.blocked_paths):
                return False

            return self.can_modify(path)

        def _normalize(self, path):
            if not isinstance(path, str) or not path.strip():
                return None
            try:
                full_path = _os.path.abspath(_os.path.join(self.safe_root, path))
                if _os.path.commonpath([self.safe_root, full_path]) != self.safe_root:
                    return None
                return _os.path.relpath(full_path, self.safe_root).replace("\\", "/")
            except (OSError, ValueError):
                return None

        def _is_relative_to(self, path, root):
            return path == root or path.startswith(root.rstrip("/") + "/")


    class _FallbackSecurityManager:
        def __init__(self, safe_root=None, allow_delete=False):
            self.safe_root = _os.path.abspath(safe_root or _os.getcwd())
            self.guard = _FallbackGuard(self.safe_root, allow_delete=allow_delete)
            self.modify_guard = _FallbackSelfModifySafe(self.safe_root)

        def validate_action(self, step):
            return self.guard.validate(step)

        def validate_write(self, path, content=None):
            return self.modify_guard.validate_write(path, content)

        def can_modify(self, path):
            return self.modify_guard.can_modify(path)

    _SecurityManager = _FallbackSecurityManager


_EventBus: Any = None
_Logger: Any = None
_SystemObserver: Any = None
try:
    from monitor.event_bus import EventBus as _ImportedEventBus
    from monitor.logger import Logger as _ImportedLogger
    from monitor.observer import SystemObserver as _ImportedSystemObserver

    _EventBus = _ImportedEventBus
    _Logger = _ImportedLogger
    _SystemObserver = _ImportedSystemObserver
except Exception:
    pass


def offline_embedding(text, size=384):
    text = str(text or "")
    vec = [0.0] * size
    tokens = re.findall(r"\w+", text.lower(), flags=re.UNICODE)

    if not tokens:
        vec[0] = 1.0
        return vec

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % size
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign

    return vec


def _workspace_root(config, safe_root=None):
    configured = ""
    try:
        configured = config.get("workspace_path", "") or config.get("project_path", "")
    except Exception:
        configured = ""
    return os.path.abspath(safe_root or configured or os.getcwd())


def _discover_ollama_models(base_url, timeout, probe_model):
    client = LLMClient(model=probe_model, base_url=base_url, timeout=min(timeout, 3.0))
    return client.list_models()


def _resolve_model(preferred, available, fallbacks):
    if not available or preferred in available:
        return preferred

    for candidate in fallbacks:
        if candidate in available:
            return candidate

    return sorted(available)[0]


def _model_setup(config, base_url, timeout):
    configured = {
        "fast": config.get("llm.fast_model", "phi3:mini"),
        "balanced": config.get("llm.default_model", "qwen2.5:3b"),
        "power": config.get("llm.power_model", "qwen2.5-coder:7b"),
    }
    available = _discover_ollama_models(base_url, timeout, configured["balanced"])

    def _model_size_score(name: str):
        # heuristic: parse trailing ":<size>b" or ":mini" tokens
        try:
            token = name.split(":")[-1].lower()
            if "mini" in token:
                return 0.25
            m = re.search(r"(\d+)(?:\.\d+)?\s*[bB]", token)
            if m:
                return float(m.group(1))
            # fallback: try to find digits anywhere
            m2 = re.search(r"(\d+)(?:\.\d+)?\s*[bB]", name)
            if m2:
                return float(m2.group(1))
        except Exception:
            pass
        # unknown size -> give medium-high priority
        return 10.0

    def _select_auto_models(avail):
        if not avail:
            return {"fast": configured["fast"], "balanced": configured["balanced"], "power": configured["power"]}
        scored = [(n, _model_size_score(n)) for n in avail]
        scored_sorted = sorted(scored, key=lambda x: x[1])
        fast_choice = scored_sorted[0][0]
        balanced_choice = scored_sorted[len(scored_sorted) // 2][0]
        power_choice = scored_sorted[-1][0]
        return {"fast": fast_choice, "balanced": balanced_choice, "power": power_choice}

    auto = _select_auto_models(available)

    resolved = {}
    for role in ("fast", "balanced", "power"):
        pref = configured.get(role)
        if available and pref in available:
            resolved[role] = pref
        elif available:
            # prefer auto-chosen model from discovered models
            resolved[role] = auto.get(role)
        else:
            # no models discovered: keep configured
            resolved[role] = pref

    missing = {key: model for key, model in configured.items() if available and model not in available}

    return {
        "base_url": base_url,
        "configured": configured,
        "resolved": resolved,
        "available_models": available,
        "missing_configured_models": missing,
        "reachable": bool(available),
    }


def build_engine(
    config=None,
    llm_router=None,
    memory=None,
    registry=None,
    executor=None,
    planner=None,
    agent=None,
    critic=None,
    router=None,
    event_bus=None,
    guard=None,
    persist_path=None,
    safe_root=None,
    debug=True,
    enable_router=True,
    state_manager=None,
):
    config = config or ConfigLoader()
    llm_base_url = config.get("llm.base_url", "http://localhost:11434/api/generate")
    # Allow forcing a local mock LLM for offline testing via env or config
    try:
        force_mock_env = os.environ.get("FORCE_MOCK_LLM", "").strip().lower()
    except Exception:
        force_mock_env = ""

    force_mock_cfg = str(config.get("llm.force_mock", "")).strip().lower()
    if force_mock_env in ("1", "true", "yes", "y") or force_mock_cfg in (
        "1",
        "true",
        "yes",
        "y",
    ):
        llm_base_url = config.get("llm.mock_base_url", "http://127.0.0.1:11435/api/generate")
    llm_timeout = float(config.get("llm.timeout", 15))
    llm_cache_ttl = int(config.get("llm.cache_ttl", 120))
    llm_max_retries = int(config.get("llm.max_retries", 0))
    llm_retry_delay = float(config.get("llm.retry_delay", 0.2))
    vector_size = int(config.get("embeddings.vector_size", 384))
    workspace_root = _workspace_root(config, safe_root=safe_root)
    # Ensure a StateManager instance is available and optionally configure it
    # Support a feature-flag / config to use a Redis-backed adapter when desired.
    try:
        use_redis_state = False
        try:
            use_redis_state = str(config.get("state.use_redis", "")).strip().lower() in ("1", "true", "yes", "y")
        except Exception:
            use_redis_state = os.environ.get("USE_REDIS_STATE", "").strip().lower() in ("1", "true", "yes", "y")

        if state_manager is None and use_redis_state:
            try:
                from core.state_redis_adapter import StateRedisAdapter

                redis_url = config.get("state.redis_url", os.environ.get("REDIS_URL", None))
                state_manager = StateRedisAdapter(redis_url=redis_url)
            except Exception:
                # If Redis adapter instantiation fails, fall through to existing behavior
                state_manager = None

        if state_manager is None:
            # prefer the global singleton from core.state when available
            import core.state as _core_state

            state_manager = _core_state.state_manager
    except Exception:
        # fallback: create a local StateManager
        try:
            from core.state_manager import StateManager as _StateManagerClass

            if state_manager is None:
                state_manager = _StateManagerClass()
        except Exception:
            state_manager = None

    # apply optional configuration from config
    try:
        if state_manager is not None:
            budget_val = config.get("state.session_token_budget", None)
            if budget_val is not None and str(budget_val).strip() != "":
                state_manager.set_session_budget(int(budget_val))
    except Exception:
        pass

    # If a StateManager instance was provided, inject it into core.state so
    # the rest of the system (e.g. AutonomousEngine) can import the same
    # singleton reference and remain compatible.
    if state_manager is not None:
        try:
            import core.state as _core_state

            _core_state.state_manager = state_manager
        except Exception:
            pass
    if llm_router is None:
        model_info = _model_setup(config, llm_base_url, llm_timeout)
    else:
        configured_models = {
            "fast": config.get("llm.fast_model", "phi3:mini"),
            "balanced": config.get("llm.default_model", "qwen2.5:3b"),
            "power": config.get("llm.power_model", "qwen2.5-coder:7b"),
        }
        model_info = {
            "base_url": llm_base_url,
            "configured": configured_models,
            "resolved": configured_models,
            "available_models": [],
            "missing_configured_models": {},
            "reachable": None,
        }
    fast_model = model_info["resolved"]["fast"]
    default_model = model_info["resolved"]["balanced"]
    power_model = model_info["resolved"]["power"]

    if llm_router is None:
        llm_fast = LLMClient(
            model=fast_model,
            base_url=llm_base_url,
            timeout=llm_timeout,
            cache_ttl=llm_cache_ttl,
            max_retries=llm_max_retries,
            retry_delay=llm_retry_delay,
        )
        llm_balanced = LLMClient(
            model=default_model,
            base_url=llm_base_url,
            timeout=llm_timeout,
            cache_ttl=llm_cache_ttl,
            max_retries=llm_max_retries,
            retry_delay=llm_retry_delay,
        )
        llm_power = LLMClient(
            model=power_model,
            base_url=llm_base_url,
            timeout=llm_timeout,
            cache_ttl=llm_cache_ttl,
            max_retries=llm_max_retries,
            retry_delay=llm_retry_delay,
        )
        llm_router = LLMRouter(
            {"fast": llm_fast, "balanced": llm_balanced, "power": llm_power}
        )

    if memory is None:
        vector_store = VectorStore(lambda text: offline_embedding(text, size=vector_size))
        retriever = Retriever(vector_store)
        memory = Memory(
            vector_store,
            retriever,
            persist_path=persist_path or "data/vectors/memory",
        )
        # ativar confirmação por padrão para extrações automáticas (ex.: nomes)
        try:
            memory.require_confirmation = True
        except Exception:
            pass

    if registry is None:
        registry = ActionRegistry()
        registry.auto_register()

    if executor is None:
        executor = Executor(registry)

    if planner is None:
        planner = Planner(llm_router, registry)

    reasoning = Reasoning()
    if agent is None:
        agent = Agent(llm_router, reasoning, memory)

    if critic is None:
        critic = Critic()

    if router is None and enable_router:
        router = create_default_router()

    logger = None
    if event_bus is None and _EventBus:
        event_bus = _EventBus()

    if _Logger:
        logger = _Logger()

    if event_bus and logger and _SystemObserver:
        _SystemObserver(event_bus, logger, None)

    if guard is None and _SecurityManager:
        guard = _SecurityManager(safe_root=workspace_root)

    engine = AutonomousEngine(
        agent=agent,
        planner=planner,
        memory=memory,
        executor=executor,
        critic=critic,
        router=router,
        event_bus=event_bus,
        guard=guard,
        max_iterations=30,
        debug=debug,
    )
    engine.workspace_root = workspace_root

    # Criar sandbox isolado por padrão para evitar executar código diretamente
    # no workspace do repositório. Em caso de falha, cair para o workspace.
    try:
        sandbox_dir = tempfile.mkdtemp(prefix="assistente_local_sandbox_")
        engine.sandbox_root = sandbox_dir
    except Exception:
        engine.sandbox_root = workspace_root

    # Configurar política de exigência de API Key (reforçar auth global)
    try:
        require_api_key = bool(str(config.get("server.require_api_key", "1")).strip().lower() in ("1", "true", "yes"))
    except Exception:
        require_api_key = True

    try:
        api_key_cfg = config.get("server.api_key", "") or os.environ.get("ASSISTENTE_API_KEY", "")
        if api_key_cfg:
            os.environ["ASSISTENTE_API_KEY"] = str(api_key_cfg)
        os.environ["ASSISTENTE_REQUIRE_API_KEY"] = "1" if require_api_key else "0"
    except Exception:
        pass

    engine.require_api_key = require_api_key

    engine.runtime_info = {
        "workspace_root": workspace_root,
        "sandbox_root": engine.sandbox_root,
        "llm": model_info,
        "require_api_key": require_api_key,
    }
    return engine
