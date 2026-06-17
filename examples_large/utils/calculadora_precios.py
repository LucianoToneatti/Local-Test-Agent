"""Cálculos de precios, descuentos, impuestos y costos de envío."""


def calcular_descuento(precio: float, porcentaje: float) -> float:
    """Calcula el monto de descuento para un precio base.

    >>> calcular_descuento(1000.0, 10.0)
    100.0
    >>> calcular_descuento(250.0, 0.0)
    0.0
    """
    if precio < 0:
        raise ValueError("El precio no puede ser negativo")
    if not 0 <= porcentaje <= 100:
        raise ValueError("El porcentaje debe estar entre 0 y 100")
    return round(precio * porcentaje / 100, 2)


def calcular_precio_con_descuento(precio: float, porcentaje: float) -> float:
    """Devuelve el precio final luego de aplicar el descuento.

    >>> calcular_precio_con_descuento(1000.0, 20.0)
    800.0
    """
    descuento = calcular_descuento(precio, porcentaje)
    return round(precio - descuento, 2)


def calcular_iva(precio: float, alicuota: float = 21.0) -> float:
    """Calcula el IVA sobre un precio neto.

    >>> calcular_iva(100.0, 21.0)
    21.0
    >>> calcular_iva(0.0)
    0.0
    """
    if precio < 0:
        raise ValueError("El precio no puede ser negativo")
    if alicuota < 0:
        raise ValueError("La alícuota no puede ser negativa")
    return round(precio * alicuota / 100, 2)


def calcular_total_con_iva(precio: float, alicuota: float = 21.0) -> float:
    """Devuelve el precio con IVA incluido.

    >>> calcular_total_con_iva(100.0, 21.0)
    121.0
    """
    return round(precio + calcular_iva(precio, alicuota), 2)


def calcular_descuento_volumen(cantidad: int, precio_unitario: float) -> float:
    """Aplica descuento escalonado por volumen y devuelve el subtotal.

    Escala:
      - 1-2 unidades: sin descuento
      - 3-4 unidades: 5 %
      - 5-9 unidades: 10 %
      - 10 o más:     15 %

    >>> calcular_descuento_volumen(1, 100.0)
    100.0
    >>> calcular_descuento_volumen(5, 100.0)
    450.0
    """
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser positiva")
    if precio_unitario < 0:
        raise ValueError("El precio unitario no puede ser negativo")

    if cantidad >= 10:
        porcentaje = 15.0
    elif cantidad >= 5:
        porcentaje = 10.0
    elif cantidad >= 3:
        porcentaje = 5.0
    else:
        porcentaje = 0.0

    subtotal = precio_unitario * cantidad
    return round(subtotal * (1 - porcentaje / 100), 2)


def calcular_costo_envio(peso_kg: float, distancia_km: float,
                          es_express: bool = False) -> float:
    """Calcula el costo de envío en base al peso y la distancia.

    Fórmula: base(150) + peso*50 + distancia*0.5 ; express multiplica x1.5.

    >>> calcular_costo_envio(1.0, 0.0)
    200.0
    >>> calcular_costo_envio(1.0, 0.0, es_express=True)
    300.0
    """
    if peso_kg <= 0:
        raise ValueError("El peso debe ser positivo")
    if distancia_km < 0:
        raise ValueError("La distancia no puede ser negativa")

    base = 150.0
    costo = base + peso_kg * 50.0 + distancia_km * 0.5
    if es_express:
        costo *= 1.5
    return round(costo, 2)
