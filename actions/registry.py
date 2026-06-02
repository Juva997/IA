# actions/registry.py

from actions.tools.file_tools import create_folder, delete_file, write_file
from actions.tools.python_tools import run_python_code
from actions.tools.system_tools import list_files, read_file, respond
from integrations.browser import open_browser
from integrations.vision import analyze_screen


class ActionRegistry:
    def __init__(self):
        self.tools = {}

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

    # =========================
    # 🧩 REGISTRO
    # =========================
    def register(self, name, func, description=""):
        if not name or not callable(func):
            raise ValueError("invalid tool registration")

        if name in self.tools:
            # mantém comportamento: sobrescreve
            pass

        self.tools[name] = {"func": func, "description": description or ""}

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
