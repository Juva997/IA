class Router:
    def __init__(self):
        self.routes = []

    def register(self, name, condition_fn):
        self.routes.append((name, condition_fn))

    def route(self, goal, context, state):
        for name, condition in self.routes:
            try:
                if condition(goal, context, state):
                    return name
            except Exception:
                continue

        return "default"


# =========================
# 🔥 REGRAS INTELIGENTES
# =========================


def is_memory_question(goal, context, *_):
    goal = goal.lower()
    return "meu nome" in goal or "quem sou eu" in goal


def is_file_task(goal, *_):
    g = goal.lower()
    # Não é file task se é claramente código/script
    if any(k in g for k in ["python", "código", "script", "função", "def ", "class "]):
        return False
    # Reconhecer operações de listagem como file tasks
    if any(k in g for k in ["listar", "lista", "arquivo", "pasta", "salvar", "criar", "deletar", "apagar"]):
        return True
    return False


def is_code_task(goal, *_):
    g = goal.lower()
    return any(k in g for k in ["python", "código", "script"])


def is_web_task(goal, *_):
    g = goal.lower()
    return any(k in g for k in ["site", "web"])


# =========================
def create_default_router():
    router = Router()

    router.register("memory", is_memory_question)
    router.register("code", is_code_task)  # ANTES de filesystem para priorizar código
    router.register("filesystem", is_file_task)
    router.register("web", is_web_task)

    return router
