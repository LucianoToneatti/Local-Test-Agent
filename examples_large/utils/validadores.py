"""Funciones de validación reutilizables en todo el sistema."""

import re


def validar_email(email: str) -> bool:
    """Valida formato de email con regex RFC-5322 simplificado."""
    if not email or not isinstance(email, str):
        return False
    patron = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(patron, email.strip()))


def validar_isbn(isbn: str) -> bool:
    """Valida ISBN-13 con checksum (suma ponderada 1-3 alternada).

    Ejemplo válido: 978-3-16-148410-0 → dígitos 9783161484100
    """
    if not isbn or not isinstance(isbn, str):
        return False
    digitos = ''.join(c for c in isbn if c.isdigit())
    if len(digitos) != 13:
        return False
    total = sum(
        int(d) * (1 if i % 2 == 0 else 3)
        for i, d in enumerate(digitos[:12])
    )
    digito_control = (10 - (total % 10)) % 10
    return digito_control == int(digitos[12])


def validar_precio(precio: float) -> bool:
    """Valida que el precio sea un número positivo y dentro de rango razonable."""
    if not isinstance(precio, (int, float)):
        return False
    return 0 < precio <= 100_000


def validar_stock(cantidad: int) -> bool:
    """Valida que la cantidad de stock sea un entero no negativo."""
    return isinstance(cantidad, int) and cantidad >= 0


def validar_codigo_postal(codigo: str) -> bool:
    """Valida código postal argentino: 4 dígitos o formato extendido (A1234BCD)."""
    if not codigo or not isinstance(codigo, str):
        return False
    codigo = codigo.strip()
    if re.match(r'^\d{4}$', codigo):
        return True
    if re.match(r'^[A-Za-z]\d{4}[A-Za-z]{3}$', codigo):
        return True
    return False


def validar_nombre(nombre: str) -> bool:
    """Valida que el nombre tenga al menos 2 caracteres y solo letras válidas."""
    if not nombre or not isinstance(nombre, str):
        return False
    nombre = nombre.strip()
    if len(nombre) < 2:
        return False
    return all(c.isalpha() or c in " '-." for c in nombre)
