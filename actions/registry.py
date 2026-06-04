# actions/registry.py

from actions.tools.file_tools import create_folder, delete_file, write_file
from actions.tools.python_tools import run_python_code
from actions.tools.system_tools import list_files, read_file, respond
from integrations.browser import open_browser
from integrations.vision import analyze_screen
from actions.tools.self_care import self_care

# ToolCatalog migration: use the MCP-style catalog as the backing store
try:
    from service.tools.mcp_catalog import ToolCatalog, LocalMCPTool
except Exception:
    ToolCatalog = None
    LocalMCPTool = None


def _doc_repair_tool(data, state=None):
    # import dinâmico para evitar import circular
    from cognition.specialists import doc_repair

    return doc_repair(data, state)


class ActionRegistry:
    def __init__(self):
        self.tools = {}
        # catalog is the MCP-compatible catalog used for migration
        self.catalog = ToolCatalog() if ToolCatalog is not None else None

    # =========================
    # 🔥 AUTO REGISTER
    # =========================
    def auto_register(self):
        self._register_default_tools()

    def _register_default_tools(self):
        # 📂 arquivos
        self.register("list_files", list_files, "Lista arquivos de um diretório")
        self.register("respond", respond, "Retorna uma resposta direta")
        self.register("read_file", read_file, "Lê conteúdo de arquivo")
        self.register("write_file", write_file, "Escreve conteúdo em arquivo")

        # 🧠 python
        self.register("run_python", run_python_code, "Executa código Python")

        # 🌐 navegador
        self.register("open_browser", open_browser, "Abre URL no navegador")

        # ⚙️ sistema
        self.register("delete_file", delete_file, "Remove arquivo")
        self.register("create_folder", create_folder, "Cria pasta")

        # 👁️ visão
        self.register("analyze_screen", analyze_screen, "Analisa tela")

        # 🛠 doc repair specialist (import dinâmico)
        self.register("doc_repair", _doc_repair_tool, "Corrige docstrings e aplica patch verificado por testes")
        # 🧘 autocuidado
        self.register("self_care", self_care, "Sugestões e tarefas de autocuidado")

    # =========================
    # 🧩 REGISTRO
    # =========================
    def register(self, name, func, description=""):
        if not name:
            raise ValueError("invalid tool registration")

        # If func is a callable local function, register it as a LocalMCPTool
        if callable(func):
            # Create a wrapper that preserves the old callable signature
            def wrapper(data, state=None):
                try:
                    # Prefer calling via catalog if available
                    if self.catalog and name in getattr(self.catalog, 'tools', {}):
                        tool = self.catalog.tools.get(name)
                        try:
                            res = tool.invoke(data)
                            return res
                        except Exception:
                            # fallthrough to direct call
                            pass

                    # direct call to original function
                    try:
                        return func(data, state)
                    except TypeError:
                        return func(data)
                except Exception as e:
                    return {"status": "error", "error": str(e)}

            # register local tool in the catalog when possible
            if self.catalog is not None and hasattr(self.catalog, 'register_local'):
                try:
                    self.catalog.register_local(name, func, description=description)
                except Exception:
                    # ignore catalog registration errors and keep wrapper
                    pass

            self.tools[name] = {"func": wrapper, "description": description or ""}
            return

        # If func is an MCP-like tool object with `invoke`, register directly
        if hasattr(func, 'invoke'):
            # store in catalog if available
            if self.catalog is not None:
                try:
                    self.catalog.tools[name] = func
                except Exception:
                    pass

            def wrapper(data, state=None):
                try:
                    res = func.invoke(data)
                    return res
                except Exception as e:
                    return {"status": "error", "error": str(e)}

            self.tools[name] = {"func": wrapper, "description": description or ""}
            return

        raise ValueError("invalid tool registration: unsupported func type")

    # =========================
    def get(self, name):
        tool = self.tools.get(name)
        if not tool:
            return None
        return tool.get("func")

    # =========================
    def list_tools(self):
        return {name: meta.get("description", "") for name, meta in self.tools.items()}

    # =========================
    def describe(self):
        return "\n".join(
            f"{name}: {meta.get('description', '')}"
            for name, meta in self.tools.items()
        )
