from calculadora import sumar, multiplicar


def promedio(lista):
    """Calcula el promedio de una lista de números usando calculadora.sumar."""
    if not lista:
        raise ValueError("La lista no puede estar vacía.")
    total = 0
    for x in lista:
        total = sumar(total, x)
    return total / len(lista)


def varianza(lista):
    """Calcula la varianza usando calculadora.sumar y calculadora.multiplicar."""
    if not lista:
        raise ValueError("La lista no puede estar vacía.")
    prom = promedio(lista)
    total_sq_diff = 0
    for x in lista:
        diff = x - prom
        total_sq_diff = sumar(total_sq_diff, multiplicar(diff, diff))
    return total_sq_diff / len(lista)
