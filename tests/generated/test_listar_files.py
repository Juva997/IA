import os
import sys
sys.path.append(os.path.abspath('.'))
from bootstrap.container import build_engine

engine = build_engine()
goal = 'liste todos os arquivos na pasta atual'
result = engine.run(goal)
print('RESULT:', result)
