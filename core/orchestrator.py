from bootstrap.container import build_engine


class Orchestrator:
    def __init__(self, base_dir=None, config=None, logger=None):
        self.engine = build_engine()
        self.logger = logger or print

    # =========================
    # 🎯 ENTRYPOINT PRINCIPAL
    # =========================
    def handle_user_query(self, text):
        if not text:
            return "[ERRO] input vazio"

        try:
            result = self.engine.run(goal=text)
            return self._extract_output(result)

        except Exception as e:
            return f"[ERRO] {str(e)}"

    # =========================
    # 🔍 EXTRAÇÃO DE RESPOSTA
    # =========================
    def _extract_output(self, result):
        if not isinstance(result, dict):
            return str(result)

        if result.get("status") == "error":
            return result.get("error", str(result))

        if "output" in result:
            return result.get("output", "")

        history = result.get("history", [])

        if history:
            last = history[-1]
            res = last.get("result", {})

            if isinstance(res, dict):
                return res.get("output", str(res))

        return str(result)

    # =========================
    def start_watch(self):
        return "Monitor iniciado"

    def stop_watch(self):
        return "Monitor parado"
