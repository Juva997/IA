import os
import re
import json
from collections import defaultdict

IMPORT_RE = re.compile(r"^\s*(from|import)\s+")
SKIP_DIRS = {".git", "__pycache__", "venv", "env", "node_modules", "build", "dist", "data"}
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

stats = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    # prune
    dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith('.')]
    for fname in filenames:
        if not fname.endswith('.py'):
            continue
        fpath = os.path.join(dirpath, fname)
        try:
            with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                lines = f.readlines()
        except Exception:
            continue
        imports = sum(1 for L in lines if IMPORT_RE.match(L))
        loc = len(lines)
        rel = os.path.relpath(fpath, ROOT).replace('\\', '/')
        stats.append({'path': rel, 'loc': loc, 'imports': imports})

# top N
TOP = 15
by_imports = sorted(stats, key=lambda x: (-x['imports'], -x['loc']))[:TOP]
by_loc = sorted(stats, key=lambda x: (-x['loc'], -x['imports']))[:TOP]

# targets
targets = [
    'core/engine.py',
    'actions/executor.py',
    'actions/registry.py',
    'bootstrap/container.py',
    'interfaces/api.py',
    'actions/tools/python_tools.py',
    'cognition/planner.py',
]

target_stats = {t: next((s for s in stats if s['path'] == t), None) for t in targets}

out = {'top_by_imports': by_imports, 'top_by_loc': by_loc, 'targets': target_stats}
print(json.dumps(out, ensure_ascii=False, indent=2))
