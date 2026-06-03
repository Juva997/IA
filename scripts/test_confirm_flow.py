import json
from core.orchestrator import Orchestrator

orchestrator = Orchestrator()
resp = orchestrator.handle_user_query("apaga o arquivo 'teste/Leia-me.txt'")
print(json.dumps(resp, ensure_ascii=False, indent=2))
resp2 = orchestrator.handle_user_query("confirmar apagar")
print(json.dumps(resp2, ensure_ascii=False, indent=2))
