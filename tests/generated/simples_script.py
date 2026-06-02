import random
numero = random.randint(1, 100)
saida = f'Numero aleatorio gerado: {numero}'
with open('resultado.txt', 'w') as f:
    f.write(saida)