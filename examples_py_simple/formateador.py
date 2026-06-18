def formatear_resultado(valor, unidad):
    if not isinstance(valor, (int, float)):
        raise TypeError("El valor debe ser un número")
    return f"{valor:.4f} {unidad}"


def formatear_tabla(filas):
    if not filas:
        return ""
    anchos = [max(len(str(fila[i])) for fila in filas) for i in range(len(filas[0]))]
    lineas = []
    for fila in filas:
        celdas = [str(fila[i]).ljust(anchos[i]) for i in range(len(fila))]
        lineas.append(" | ".join(celdas))
    return "\n".join(lineas)


def redondear(valor, decimales=2):
    if not isinstance(valor, (int, float)):
        raise TypeError("El valor debe ser un número")
    if not isinstance(decimales, int) or decimales < 0:
        raise ValueError("Los decimales deben ser un entero no negativo")
    return round(valor, decimales)
