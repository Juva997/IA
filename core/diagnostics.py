import os


def collect_health_details(engine):
    # Allow forcing a diagnostic failure for testing via env var
    val = os.getenv("FORCE_DIAG_FAIL", "")
    if str(val).strip().lower() in ("1", "true", "yes", "y"):
        raise RuntimeError("Forced diagnostic failure for testing (FORCE_DIAG_FAIL)")

    runtime = getattr(engine, "runtime_info", {}) or {}
    llm_details = _llm_details(engine, runtime)
    memory_details = _memory_details(engine)
    tools = _tool_details(engine)

    status = "ok"
    if llm_details.get("reachable") is False:
        status = "degraded"
    if llm_details.get("missing_configured_models"):
        status = "degraded"

    return {
        "status": status,
        "workspace_root": getattr(engine, "workspace_root", os.getcwd()),
        "sandbox_root": getattr(engine, "sandbox_root", None),
        "ollama": llm_details,
        "memory": memory_details,
        "tools": tools,
    }


def _llm_details(engine, runtime):
    configured = dict((runtime.get("llm") or {}).get("configured") or {})
    resolved = dict((runtime.get("llm") or {}).get("resolved") or {})
    available = list((runtime.get("llm") or {}).get("available_models") or [])
    missing = dict((runtime.get("llm") or {}).get("missing_configured_models") or {})
    base_url = (runtime.get("llm") or {}).get("base_url")
    reachable = (runtime.get("llm") or {}).get("reachable")

    router = getattr(getattr(engine, "agent", None), "llm", None)
    clients = getattr(router, "llms", {}) if router is not None else {}
    first_client = next(iter(clients.values()), None) if clients else None

    if first_client is not None and hasattr(first_client, "health_details"):
        live = first_client.health_details()
        available = live.get("models") or available
        base_url = live.get("base_url") or base_url
        reachable = bool(live.get("reachable"))
        if configured and available:
            missing = {
                key: model
                for key, model in configured.items()
                if model not in available
            }

    router_diag = router.diagnostics() if hasattr(router, "diagnostics") else {}
    if router_diag.get("models"):
        resolved = router_diag["models"]

    return {
        "base_url": base_url,
        "reachable": reachable,
        "configured_models": configured,
        "resolved_models": resolved,
        "available_models": available,
        "missing_configured_models": missing,
    }


def _memory_details(engine):
    memory = getattr(engine, "memory", None)
    if memory is None or not hasattr(memory, "get_memory_snapshot"):
        return {"available": False}

    snapshot = memory.get_memory_snapshot()
    return {
        "available": True,
        "facts": len(snapshot.get("facts", {}) or {}),
        "episodes": len(snapshot.get("episodes", []) or []),
        "skills": len(snapshot.get("skills", {}) or {}),
        "lessons": len(snapshot.get("lessons", []) or []),
    }


def _tool_details(engine):
    registry = getattr(getattr(engine, "executor", None), "registry", None)
    if registry is None or not hasattr(registry, "list_tools"):
        return {"count": 0, "items": {}}

    items = registry.list_tools()
    return {"count": len(items), "items": items}
