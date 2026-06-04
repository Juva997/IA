"""Thin MCP catalog shim.

For compatibility with new code paths we provide a lightweight wrapper
over the existing `service.tools.mcp_adapter` prototype. New code can
import `service.tools.mcp_catalog` and progressively migrate to a
full MCP implementation.
"""
from typing import Any, Dict, Optional

from service.tools.mcp_adapter import MCPTool as _MCPTool, ToolCatalog as _ToolCatalog, load_from_config as load_from_config


class MCPTool(_MCPTool):
    """Alias para a classe protótipo existente."""
    pass


class ToolCatalog(_ToolCatalog):
    """Alias/placeholder para catálogo MCP."""
    pass


def create_default_catalog() -> ToolCatalog:
    return ToolCatalog()


__all__ = ["MCPTool", "ToolCatalog", "load_from_config", "create_default_catalog"]
