import os
import time


def self_care(data=None, state=None):
    """Ferramenta simples de autocuidado.

    - Sem parâmetros: retorna opções sugeridas.
    - {'action': 'create_task', 'task': 'Pausa 5min'} cria um arquivo de tarefa em ./autocuidado_tasks/.
    - {'action': 'exercise_breathing'} retorna um exercício de respiração guiada.
    """
    try:
        if not data:
            output = (
                "Sugestões de autocuidado:\n"
                "1) Pausa curtas com respiração guiada.\n"
                "2) Alongamento leve por 5 minutos.\n"
                "3) Criar lembrete/tarefa de autocuidado.\n"
                "Para criar uma tarefa, chame esta ação com {'action':'create_task','task':'Pausa 5min'}."
            )
            return {"status": "success", "output": output}

        if isinstance(data, dict):
            action = data.get("action")
            if action == "create_task":
                task = data.get("task", "Pausa de autocuidado")
                # determina root do workspace a partir do state se possível
                root = None
                if isinstance(state, dict):
                    root = state.get("workspace_root") or (state.get("metadata") or {}).get("workspace_root")
                if not root:
                    root = os.path.abspath(os.getcwd())
                folder = os.path.join(root, "autocuidado_tasks")
                os.makedirs(folder, exist_ok=True)
                filename = f"autocuidado_{int(time.time())}.txt"
                path = os.path.join(folder, filename)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"Tarefa de autocuidado: {task}\ncriada_em: {time.ctime()}\n")
                return {"status": "success", "output": f"Tarefa criada: {path}"}

            if action == "exercise_breathing":
                steps = (
                    "Exercício rápido de respiração:\n1) Inspire contando até 4.\n2) Segure por 4.\n3) Expire contando até 4.\n4) Repita 4 vezes."
                )
                return {"status": "success", "output": steps}

        return {"status": "error", "error": "unsupported_action"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
