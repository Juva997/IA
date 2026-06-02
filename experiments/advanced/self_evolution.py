import os


class SelfEvolution:
    def __init__(self, llm):
        self.llm = llm

    def evolve_file(self, path):
        if not os.path.exists(path):
            return "Arquivo não encontrado"

        try:
            with open(path, "r", encoding="utf-8") as f:
                code = f.read()

            prompt = f"""
Melhore este código:

{code}

Regras:
- não quebrar funcionalidade
- melhorar performance
- melhorar legibilidade
- retornar código completo
"""

            new_code = self.llm.generate(prompt)

            if not new_code or len(new_code) < 20:
                return "Ignorado (resposta inválida)"

            # validações básicas
            if "import" in new_code or "def " in new_code or "class " in new_code:
                backup_path = path + ".bak"

                # cria backup antes de sobrescrever
                with open(backup_path, "w", encoding="utf-8") as f:
                    f.write(code)

                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_code)

                return "Evoluído com backup"

            return "Ignorado (não passou validação)"

        except Exception as e:
            return f"Erro: {e}"
