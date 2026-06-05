"""
Tarefas executadas por workers (RQ).

Funções esportadas aqui devem ser importáveis pelo worker process.
Cada função deve receber argumentos simples (JSON-serializáveis) e
retornar um valor serializável.
"""
import os


def run_python_task(data, state=None):
    """Task wrapper para `actions.tools.python_tools.run_python_code`.

    Recebe exatamente os mesmos argumentos que o wrapper original.
    """
    try:
        from actions.tools.python_tools import run_python_code
        return run_python_code(data, state)
    except Exception as e:
        return {"status": "error", "output": None, "error": str(e)}


def engine_run_task(goal, workspace_root=None):
    """Task wrapper que cria uma instância local do engine e executa `engine.run(goal)`.

    Observação: este é um PoC — o worker constrói sua própria instância do
    engine (via `bootstrap.container.build_engine`) e não compartilha estado
    com o processo que enfileirou a tarefa.
    """
    try:
        # import dinâmico para evitar ciclos na carga inicial
        from bootstrap.container import build_engine

        engine = build_engine()
        if workspace_root:
            try:
                engine.workspace_root = workspace_root
                engine.sandbox_root = getattr(engine, "sandbox_root", workspace_root)
            except Exception:
                pass

        return engine.run(goal)
    except Exception as e:
        return {"status": "error", "output": None, "error": str(e)}
