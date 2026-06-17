"""Operaciones sobre el carrito de compras."""

from models.inventario import Inventario
from utils.calculadora_precios import (
    calcular_precio_con_descuento,
    calcular_descuento_volumen,
)
from exceptions import ValidacionError, StockInsuficienteError, ProductoNoEncontradoError

# Cupones válidos: código → porcentaje de descuento
_CUPONES: dict[str, float] = {
    'DESCUENTO10': 10.0,
    'VERANO20':    20.0,
    'PROMO5':       5.0,
    'BIENVENIDA15': 15.0,
}


def agregar_al_carrito(carrito: dict, producto, cantidad: int,
                        inventario: Inventario) -> dict:
    """Agrega o incrementa un producto en el carrito verificando stock disponible.

    El carrito es un dict: {producto_id: {'producto': Producto, 'cantidad': int}}.
    Lanza StockInsuficienteError si la suma (en carrito + nueva) supera el stock.
    """
    if cantidad <= 0:
        raise ValidacionError("La cantidad debe ser positiva")

    stock_disponible = inventario.obtener_stock(producto.id)
    en_carrito = carrito.get(producto.id, {}).get('cantidad', 0)
    if en_carrito + cantidad > stock_disponible:
        raise StockInsuficienteError(
            f"No hay suficiente stock de '{producto.titulo}': "
            f"disponible={stock_disponible}, en carrito={en_carrito}, "
            f"solicitado={cantidad}"
        )

    if producto.id in carrito:
        carrito[producto.id]['cantidad'] += cantidad
    else:
        carrito[producto.id] = {'producto': producto, 'cantidad': cantidad}
    return carrito


def remover_del_carrito(carrito: dict, producto_id: int) -> dict:
    """Elimina completamente un producto del carrito.

    Lanza ProductoNoEncontradoError si el producto no estaba en el carrito.
    """
    if producto_id not in carrito:
        raise ProductoNoEncontradoError(
            f"Producto con id={producto_id} no está en el carrito"
        )
    del carrito[producto_id]
    return carrito


def calcular_total_carrito(carrito: dict,
                            usar_descuento_volumen: bool = False) -> float:
    """Suma el total del carrito.

    Si usar_descuento_volumen=True aplica la escala por cantidad por item.
    Devuelve 0.0 para carrito vacío.
    """
    if not carrito:
        return 0.0
    total = 0.0
    for item in carrito.values():
        producto = item['producto']
        cantidad = item['cantidad']
        if usar_descuento_volumen:
            total += calcular_descuento_volumen(cantidad, producto.precio_final())
        else:
            total += producto.precio_final() * cantidad
    return round(total, 2)


def aplicar_cupon(carrito: dict, codigo: str) -> tuple[float, float]:
    """Aplica un cupón de descuento al carrito.

    Devuelve (total_original, total_con_descuento).
    Lanza ValidacionError si el carrito está vacío o el cupón es inválido.
    """
    if not carrito:
        raise ValidacionError("No se puede aplicar un cupón a un carrito vacío")
    codigo_norm = codigo.strip().upper()
    if codigo_norm not in _CUPONES:
        raise ValidacionError(f"El cupón '{codigo}' no es válido")

    total_original = calcular_total_carrito(carrito)
    porcentaje = _CUPONES[codigo_norm]
    total_final = calcular_precio_con_descuento(total_original, porcentaje)
    return total_original, total_final


def vaciar_carrito(carrito: dict) -> dict:
    """Elimina todos los items del carrito y lo devuelve vacío."""
    carrito.clear()
    return carrito
