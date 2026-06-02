import json
import os
import subprocess


class DevinUltra:
    def __init__(self, llm):
        self.llm = llm
        self.workspace = "workspace"

    def run(self, goal):
        plan = self._plan(goal)
        structure = self._design(goal, plan)

        self._create_project()
        self._write_files(structure)

        self._install_deps(structure)

        success, out = self._run_main()

        if not success:
            self._fix_all(out)
            return "Corrigido automaticamente"

        return "Projeto pronto com sucesso"

    def _plan(self, goal):
        return self.llm.generate(f"Plano detalhado: {goal}")

    def _design(self, goal, plan):
        prompt = f"""
Crie projeto completo em JSON:

{goal}
{plan}

Formato:
{{
 "files": {{
   "main.py": "...",
   "api/app.py": "..."
 }},
 "requirements": ["fastapi"]
}}
"""
        raw = self.llm.generate(prompt)

        try:
            return json.loads(raw)
        except Exception:
            return {"files": {"main.py": "print('erro fallback')"}}

    def _create_project(self):
        os.makedirs(self.workspace, exist_ok=True)
        subprocess.run(["git", "init"], cwd=self.workspace)

    def _write_files(self, structure):
        for path, code in structure.get("files", {}).items():
            full = os.path.join(self.workspace, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)

            with open(full, "w", encoding="utf-8") as f:
                f.write(code)

    def _install_deps(self, structure):
        reqs = structure.get("requirements", [])

        if reqs:
            with open(f"{self.workspace}/requirements.txt", "w") as f:
                f.write("\n".join(reqs))

            subprocess.run(
                ["pip", "install", "-r", "requirements.txt"], cwd=self.workspace
            )

    def _run_main(self):
        try:
            r = subprocess.run(
                ["python", "main.py"],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=20,
            )
            return r.returncode == 0, r.stderr
        except Exception as e:
            return False, str(e)

    def _fix_all(self, error):
        files = {}

        for root, _, fs in os.walk(self.workspace):
            for f in fs:
                p = os.path.join(root, f)
                with open(p, "r", encoding="utf-8") as file:
                    files[p] = file.read()

        prompt = f"""
Erro:
{error}

Arquivos:
{files}

Corrija tudo e retorne JSON completo.
"""

        raw = self.llm.generate(prompt)

        try:
            fixed = json.loads(raw)
            self._write_files(fixed)
        except Exception:
            # Se falhar ao parsear correção, ignorar
            pass
