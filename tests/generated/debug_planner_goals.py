import os
import sys
sys.path.append(os.path.abspath('.'))
from bootstrap.container import build_engine

engine = build_engine()
goals = [
    'liste todos os arquivos na pasta atual',
    'crie um código python simples que funcione corretamente',
    'crie um código python simples e funcional',
    'crie um arquivo de texto com dados numéricos separados por vírgula',
    'crie um teste unitário simples em python',
    'crie um arquivo de texto com dados numéricos separados por vírgula',
    'crie script python que imprime números de 1 a 5',
    'crie arquivo de texto com dados numéricos separados por vírgula'
]

for goal in goals:
    plan = engine.planner.create_plan(goal, engine.memory.build_context(goal, engine._init_state(goal).to_dict()))
    print('GOAL:', goal)
    print('PLAN:', plan)
    print('---')
