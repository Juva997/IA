import random
import sys
def main():
    try:
        numero = random.randint(1, 100)
        with open('numero.txt', 'w') as file:   # Escreve o numero gerado em um arquivo.
            file.write(str(numero))
        print(f'Numero aleatorio gerado e salvo no arquivo numero.txt: {numero}')
    except IOError:
        sys.exit('Falha ao escrever no arquivo. Por favor, tente novamente mais tarde.')