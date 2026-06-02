import os
import sys
sys.path.append(os.path.abspath('.'))
from cognition.planner import Planner

p = Planner(None, None)
goal = 'liste todos os arquivos na pasta atual'
classification = p._classify_goal(goal)
print('CLASSIFICATION:', classification)

# Also check the router
from core.router import create_default_router, is_file_task, is_code_task
router = create_default_router()
print('IS_FILE_TASK:', is_file_task(goal))
print('IS_CODE_TASK:', is_code_task(goal))
