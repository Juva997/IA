def add(a, b):
    return a + b

def sub(a, b):
    return a - b

def mul(a, b):
    return a * b

def div(a, b):
    if b == 0:

        raise ValueError('Divisão por zero não permitida')
    return a / b

if __name__ == '__main__':
    print(add(5,3))
    print(sub(10,4))
    print(mul(6,7))
    try:

        print(div(8,0))
    except Exception as e:

        print('Erro:', e)