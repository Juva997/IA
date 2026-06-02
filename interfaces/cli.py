from bootstrap.container import build_engine
from core.diagnostics import collect_health_details


def run_cli():
    engine = build_engine()

    print("\nIA autonoma iniciada\n")

    while True:
        try:
            goal = input("Objetivo (ou 'sair'): ")

            if goal.lower() in ["sair", "exit", "quit"]:
                break

            result = engine.run(goal)

            if isinstance(result, dict) and "output" in result:
                output = result.get("output")
            else:
                output = result

            print("\nResultado final:")
            print(output)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print("[ERRO CLI]", e)


def run_doctor():
    engine = build_engine()
    details = collect_health_details(engine)
    ollama = details.get("ollama", {})
    memory = details.get("memory", {})
    tools = details.get("tools", {})

    print("Assistente Local - diagnostico")
    print(f"status: {details.get('status')}")
    print(f"workspace: {details.get('workspace_root')}")
    print(f"sandbox: {details.get('sandbox_root')}")
    print(f"ollama: {'online' if ollama.get('reachable') else 'offline'}")
    print(f"modelos configurados: {ollama.get('configured_models')}")
    print(f"modelos resolvidos: {ollama.get('resolved_models')}")
    missing = ollama.get("missing_configured_models") or {}
    if missing:
        print(f"modelos configurados ausentes: {missing}")
    print(f"modelos disponiveis: {', '.join(ollama.get('available_models') or [])}")
    print(
        "memoria: "
        f"facts={memory.get('facts', 0)} "
        f"episodes={memory.get('episodes', 0)} "
        f"skills={memory.get('skills', 0)} "
        f"lessons={memory.get('lessons', 0)}"
    )
    print(f"ferramentas registradas: {tools.get('count', 0)}")
