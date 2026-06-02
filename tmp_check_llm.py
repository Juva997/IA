import json
from bootstrap.container import build_engine
engine = build_engine(debug=False)
print(json.dumps(engine.runtime_info['llm'], indent=2))
