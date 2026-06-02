import os
import sys
sys.path.append(os.path.abspath('.'))
from actions.tools.system_tools import list_files

result = list_files({'path': '.'})
print('LIST_FILES RESULT:', result)
print('FILES:', result.get('output', [])[:5])
