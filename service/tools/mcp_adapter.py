"""MCP adapter protótipo: definições simples de ferramenta e catálogo.

Objetivo: padronizar invocação de ferramentas externas via HTTP/MCP.
"""
from typing import Any, Dict, Optional
import requests


class MCPTool:
    def __init__(self, id: str, endpoint: str, schema: Optional[Dict] = None, headers: Optional[Dict] = None):
        self.id = id
        self.endpoint = endpoint
        self.schema = schema or {}
        self.headers = headers or {}

    def invoke(self, payload: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
        resp = requests.post(self.endpoint, json=payload, headers=self.headers, timeout=timeout)
        try:
            return resp.json()
        except Exception:
            return {"status": "error", "error": "invalid_response", "raw": resp.text}


class ToolCatalog:
    def __init__(self):
        self.tools: Dict[str, MCPTool] = {}

    def register(self, tool: MCPTool):
        self.tools[tool.id] = tool

    def get(self, id: str) -> Optional[MCPTool]:
        return self.tools.get(id)

    def list(self):
        return list(self.tools.keys())


def load_from_config(cfg: Dict[str, Any]) -> ToolCatalog:
    catalog = ToolCatalog()
    for entry in cfg.get("tools", []):
        t = MCPTool(entry.get("id"), entry.get("endpoint"), schema=entry.get("schema"))
        catalog.register(t)
    return catalog


__all__ = ["MCPTool", "ToolCatalog", "load_from_config"]
