import os
import sys
import time

sys.path.append(os.path.abspath(os.getcwd()))
from bootstrap.container import build_engine

engine = build_engine()

cases = [
    {
        'name': 'teste_unitario',
        'input': 'crie um teste unitário simples em python',
        'verify': ['teste', 'assert', 'unittest', 'def test'],
    },
    {
        'name': 'processamento_csv',
        'input': 'crie um arquivo de texto com dados numéricos separados por vírgula',
        'verify': ['vírgula', 'dados', 'números'],
    },
    {
        'name': 'debug_codigo',
        'input': 'crie um código python simples que funcione corretamente',
        'verify': ['print', 'def', 'codigo', 'funcione'],
    },
    {
        'name': 'refatoracao',
        'input': 'crie um código python simples e funcional',
        'verify': ['def', 'print', 'codigo', 'funcional'],
    },
    {
        'name': 'auto_modificacao',
        'input': 'crie um script python que imprime seu próprio nome quando executado',
        'verify': ['print', 'nome', 'arquivo', 'self'],
    },
    {
        'name': 'benchmark_codigo',
        'input': 'crie um exemplo simples de benchmark em python',
        'verify': ['benchmark', 'teste', 'performance', 'time'],
    },
    {
        'name': 'evolucao_codigo',
        'input': "crie uma versão melhorada deste código: print('hello')",
        'verify': ['def', 'funcao', 'melhor', 'avancado'],
    },
    {
        'name': 'resumo_documento',
        'input': 'crie um resumo simples do projeto atual',
        'verify': ['resumo', 'projeto', 'código', 'sistema'],
    },
    {
        'name': 'recuperacao_memoria',
        'input': 'recupere informações sobre algoritmos de aprendizado de máquina',
        'verify': ['recuperação', 'memória', 'ML'],
    },
]

for case in cases:
    print('='*80)
    print('TEST:', case['name'])
    print('INPUT:', case['input'])
    start = time.time()
    result = engine.run(case['input'])
    elapsed = time.time() - start
    print('STATUS:', result.get('status'))
    output = str(result.get('output', ''))
    print('OUTPUT:', output[:1200])
    print('VERIFY:')
    for fragment in case['verify']:
        print(f"  {fragment}: {fragment.lower() in output.lower()}")
    print('ELAPSED:', round(elapsed, 2), 's')
