"""Funciones de formateo para presentación en pantalla y reportes."""

from datetime import datetime


def formatear_precio(precio: float, moneda: str = "ARS") -> str:
    """Formatea un precio con símbolo de moneda y separador de miles.

    >>> formatear_precio(1500.5)
    'ARS 1,500.50'
    >>> formatear_precio(0.0)
    'ARS 0.00'
    """
    if precio < 0:
        raise ValueError("El precio no puede ser negativo")
    if not moneda or not isinstance(moneda, str):
        raise ValueError("La moneda debe ser una cadena no vacía")
    return f"{moneda} {precio:,.2f}"


def formatear_fecha(fecha: datetime, formato: str = "%d/%m/%Y") -> str:
    """Convierte un datetime a string con el formato dado.

    >>> from datetime import datetime
    >>> formatear_fecha(datetime(2024, 3, 15))
    '15/03/2024'
    """
    if not isinstance(fecha, datetime):
        raise TypeError("Se esperaba un objeto datetime")
    if not formato:
        raise ValueError("El formato no puede estar vacío")
    return fecha.strftime(formato)


def formatear_direccion(calle: str, numero: int, ciudad: str,
                        provincia: str, cp: str) -> str:
    """Arma una dirección completa en una sola línea.

    >>> formatear_direccion("Av. Corrientes", 1234, "CABA", "Buenos Aires", "1043")
    'Av. Corrientes 1234, CABA, Buenos Aires (1043)'
    """
    if not all([calle, ciudad, provincia, cp]):
        raise ValueError("Todos los campos de la dirección son obligatorios")
    if numero <= 0:
        raise ValueError("El número de calle debe ser positivo")
    return f"{calle.strip()} {numero}, {ciudad.strip()}, {provincia.strip()} ({cp.strip()})"


def formatear_resumen_pedido(items: list, total: float) -> str:
    """Genera un bloque de texto con los items y el total del pedido.

    Cada elemento de items debe tener 'nombre', 'cantidad' y 'precio_unitario'.
    Devuelve 'Pedido vacío' si la lista está vacía.
    """
    if not items:
        return "Pedido vacío"
    if total < 0:
        raise ValueError("El total no puede ser negativo")
    lineas = []
    for item in items:
        nombre = item.get('nombre', 'Desconocido')
        cantidad = item.get('cantidad', 0)
        precio_u = item.get('precio_unitario', 0.0)
        subtotal = cantidad * precio_u
        lineas.append(f"  - {nombre} x{cantidad}: ${subtotal:.2f}")
    lineas.append(f"  TOTAL: ${total:.2f}")
    return "\n".join(lineas)


def formatear_nombre_completo(nombre: str, apellido: str) -> str:
    """Devuelve 'Apellido, Nombre' en formato título.

    >>> formatear_nombre_completo("juan", "PÉREZ")
    'Pérez, Juan'
    """
    nombre = nombre.strip() if nombre else ""
    apellido = apellido.strip() if apellido else ""
    if not nombre or not apellido:
        raise ValueError("Nombre y apellido son requeridos")
    return f"{apellido.title()}, {nombre.title()}"
