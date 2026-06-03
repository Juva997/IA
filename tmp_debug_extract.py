import os
import tempfile
import textwrap

from cognition.refactor_operations import build_extended_refactor_index

p = tempfile.mkdtemp()
open(os.path.join(p, 'module_a.py'), 'w', encoding='utf-8').write(textwrap.dedent('''\
MAX_RETRIES = 3

def helper(x):
    return x * MAX_RETRIES

def duplicate_func(a, b):
    return a + b
'''))
engine = build_extended_refactor_index(p)
res = engine.extract_function(
    source_file='module_a.py',
    start_line=3,
    end_line=4,
    new_function_name='extracted_helper',
    dry_run=True,
)
print('TYPE:', type(res))
try:
    print('STATUS:', res.status)
    print('MESSAGE:', res.message)
    print('DATA KEYS:', list(res.data.keys()))
    print('DATA NEW_FUNC (snippet):', res.data.get('new_function', '')[:200])
except Exception:
    print('RES REPR:', res)
    import traceback

    traceback.print_exc()
