import os
import sys
sys.path.append(os.path.abspath('.'))
from bootstrap.container import build_engine

engine = build_engine()
goals = [
    'crie uma função python que calcula o fatorial de um número (sem input)',
    'crie um teste unitário simples em python',
]

for goal in goals:
    plan = engine.planner.create_plan(goal, engine.memory.build_context(goal, engine._init_state(goal).to_dict()))
    print('GOAL:', goal)
    print('PLAN:', plan)
    if plan:
        for step in plan:
            if step.get('action') in ['write_file', 'run_python']:
                print('  Action:', step['action'])
                if step['action'] == 'write_file':
                    print('  Content preview:', step['data']['content'][:150])
                else:
                    print('  Code preview:', step['data']['code'][:150])
    print('---')
