def sumar(a, b):
    return a + b


def restar(a, b):
    return a - b


def multiplicar(a, b):
    return a * b


def dividir(dividendo, divisor):
    if divisor == 0:
        raise ValueError("El divisor no puede ser cero.")
    return dividendo / divisor


def potencia(base, exponente):
    return base ** exponente
