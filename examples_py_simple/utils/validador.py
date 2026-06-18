def validar_numero(valor):
    if not isinstance(valor, (int, float)):
        raise TypeError(f"Se esperaba un número, se recibió {type(valor).__name__}")
    return True


def validar_rango(valor, minimo, maximo):
    if not isinstance(valor, (int, float)):
        raise TypeError("El valor debe ser un número")
    if minimo > maximo:
        raise ValueError("El mínimo no puede ser mayor que el máximo")
    if valor < minimo or valor > maximo:
        raise ValueError(f"{valor} está fuera del rango [{minimo}, {maximo}]")
    return True


def validar_positivo(valor):
    if not isinstance(valor, (int, float)):
        raise TypeError("El valor debe ser un número")
    if valor <= 0:
        raise ValueError(f"{valor} no es positivo")
    return True
