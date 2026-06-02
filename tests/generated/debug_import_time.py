import os
import sys
sys.path.append(os.getcwd())
from actions.tools.python_tools import _safe_import, SAFE_MODULES, _contains_forbidden
print('time in SAFE_MODULES', 'time' in SAFE_MODULES)
try:
    module = _safe_import('time')
    print('safe import time ok', module)
except Exception as e:
    print('safe import failed:', type(e).__name__, e)
print('contains forbidden time', _contains_forbidden('import time'))
