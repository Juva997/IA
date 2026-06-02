import os
import sys
sys.path.append(os.path.abspath('.'))
from bootstrap.container import build_engine

engine = build_engine()
goal = 'liste todos os arquivos na pasta atual'
context = engine.memory.build_context(goal, engine._init_state(goal).to_dict())

plan = engine.planner.create_plan(goal, context)
print('PLAN:', plan)
print('IS_INVALID_PLAN:', engine._is_invalid_plan(plan))

# Also check the planner classify
print('CLASSIFY_GOAL:', engine.planner.classify_goal(goal))
