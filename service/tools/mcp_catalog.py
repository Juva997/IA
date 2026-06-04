"""Thin MCP catalog shim.

For compatibility with new code paths we provide a lightweight wrapper
over the existing `service.tools.mcp_adapter` prototype. New code can
import `service.tools.mcp_catalog` and progressively migrate to a
full MCP implementation.
"""
from typing import Any, Callable, Dict, Optional

from service.tools.mcp_adapter import MCPTool as _MCPTool, ToolCatalog as _ToolCatalog, load_from_config as load_from_config


class MCPTool(_MCPTool):
    """Alias para a classe protótipo existente.

    Note: external (HTTP) MCP tools continue to use the original
    MCPTool implementation from `mcp_adapter`.
    """
    pass


class LocalMCPTool:
    """Wrap a local Python callable as an MCP-compatible tool.

    The callable should accept `(data, state=None)` and return a dict
    like the existing local action functions. If the callable is
    asynchronous it may return a coroutine and the caller is expected
    to await it.
    """

    def __init__(self, id: str, func: Callable[..., Any], schema: Optional[Dict] = None, description: str = ""):
        self.id = id
        self.func = func
        self.schema = schema or {}
        self.description = description or ""

    def invoke(self, payload: Any, timeout: int = 30):
        # Expect payload to be the `data` dict; many local tools accept
        # signature (data, state=None). We call with state=None when
        # not provided by the caller.
        try:
            # If callable is coroutinefunction it will return a coroutine
            return self.func(payload, None)
        except TypeError:
            # fallback: try calling with only payload
            return self.func(payload)


class ToolCatalog(_ToolCatalog):
    """Alias/extension for prototype catalog. Adds helper to register
    local callables easily.
    """

    def register_local(self, id: str, func: Callable[..., Any], schema: Optional[Dict] = None, description: str = ""):
        lt = LocalMCPTool(id, func, schema=schema, description=description)
        # Underlying ToolCatalog expects MCPTool instances; keep a
        # separate mapping for locals to avoid breaking behaviour.
        # We'll store the local wrapper in the same `tools` dict to
        # allow lookups by id.
        self.tools[id] = lt


def create_default_catalog() -> ToolCatalog:
    return ToolCatalog()


__all__ = ["MCPTool", "LocalMCPTool", "ToolCatalog", "load_from_config", "create_default_catalog"]
