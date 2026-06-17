"""Estimación de costos y tiempos de envío, y gestión del estado del despacho."""

from models.pedido import Pedido, EstadoPedido
from utils.validadores import validar_codigo_postal
from utils.calculadora_precios import calcular_costo_envio
from exceptions import ValidacionError, PedidoError

# Distancias aproximadas desde depósito central en km
_DISTANCIAS_KM: dict[str, float] = {
    'CABA':           0.0,
    'Buenos Aires':  50.0,
    'Córdoba':      700.0,
    'Rosario':      300.0,
    'Mendoza':     1050.0,
    'Tucumán':     1300.0,
    'Salta':       1450.0,
    'Mar del Plata': 400.0,
}

_DISTANCIA_DEFAULT = 500.0  # km para ciudades no mapeadas

# Días hábiles estimados de entrega por tramo de distancia
_DIAS_NORMAL = [(0, 2), (100, 3), (500, 5), (float('inf'), 8)]
_DIAS_EXPRESS = [(0, 1), (100, 1), (500, 2), (float('inf'), 3)]


def validar_direccion_envio(calle: str, numero: int, ciudad: str,
                             provincia: str, codigo_postal: str) -> bool:
    """Valida que todos los campos de la dirección sean correctos.

    Lanza ValidacionError con el campo problemático.
    """
    if not calle or not calle.strip():
        raise ValidacionError("La calle es obligatoria")
    if not isinstance(numero, int) or numero <= 0:
        raise ValidacionError("El número de calle debe ser un entero positivo")
    if not ciudad or not ciudad.strip():
        raise ValidacionError("La ciudad es obligatoria")
    if not provincia or not provincia.strip():
        raise ValidacionError("La provincia es obligatoria")
    if not validar_codigo_postal(codigo_postal):
        raise ValidacionError(f"Código postal inválido: '{codigo_postal}'")
    return True


def estimar_costo_envio(pedido: Pedido, ciudad_destino: str,
                         es_express: bool = False) -> float:
    """Estima el costo de envío según la cantidad de items y la ciudad destino.

    Usa 0.5 kg por libro como peso estimado.
    """
    if not pedido.items:
        raise PedidoError("No se puede estimar envío para un pedido sin items")
    peso_kg = pedido.cantidad_total_items() * 0.5
    distancia = _DISTANCIAS_KM.get(ciudad_destino, _DISTANCIA_DEFAULT)
    return calcular_costo_envio(peso_kg, distancia, es_express)


def estimar_dias_entrega(ciudad_destino: str, es_express: bool = False) -> int:
    """Estima los días hábiles de entrega según distancia y modalidad."""
    distancia = _DISTANCIAS_KM.get(ciudad_destino, _DISTANCIA_DEFAULT)
    tabla = _DIAS_EXPRESS if es_express else _DIAS_NORMAL
    for limite, dias in tabla:
        if distancia <= limite:
            return dias
    return tabla[-1][1]  # fallback al valor máximo


def crear_envio(pedido: Pedido, direccion: dict) -> dict:
    """Genera el registro de envío para un pedido confirmado.

    La dirección debe contener: calle, numero, ciudad, provincia, codigo_postal.
    Campo opcional: express (bool).
    Devuelve un dict con costo, días estimados y estado inicial 'pendiente'.
    """
    if pedido.estado != EstadoPedido.CONFIRMADO:
        raise PedidoError("El pedido debe estar confirmado para crear un envío")

    campos_requeridos = ('calle', 'numero', 'ciudad', 'provincia', 'codigo_postal')
    for campo in campos_requeridos:
        if campo not in direccion:
            raise ValidacionError(f"Campo requerido faltante en dirección: '{campo}'")

    validar_direccion_envio(
        direccion['calle'],
        direccion['numero'],
        direccion['ciudad'],
        direccion['provincia'],
        direccion['codigo_postal'],
    )

    es_express = bool(direccion.get('express', False))
    ciudad = direccion['ciudad']
    return {
        'pedido_id': pedido.id,
        'direccion': direccion,
        'costo': estimar_costo_envio(pedido, ciudad, es_express),
        'dias_estimados': estimar_dias_entrega(ciudad, es_express),
        'estado': 'pendiente',
    }


def actualizar_estado_envio(envio: dict, nuevo_estado: str) -> dict:
    """Avanza el estado del envío siguiendo la secuencia obligatoria.

    Secuencia válida: pendiente → preparando → en_camino → entregado
    Lanza ValidacionError si la transición no está permitida.
    """
    estados_validos = ('pendiente', 'preparando', 'en_camino', 'entregado')
    if nuevo_estado not in estados_validos:
        raise ValidacionError(
            f"Estado '{nuevo_estado}' no válido. Opciones: {estados_validos}"
        )
    transiciones: dict[str, tuple] = {
        'pendiente':  ('preparando',),
        'preparando': ('en_camino',),
        'en_camino':  ('entregado',),
        'entregado':  (),
    }
    estado_actual = envio.get('estado', 'pendiente')
    if nuevo_estado not in transiciones.get(estado_actual, ()):
        raise ValidacionError(
            f"Transición inválida: '{estado_actual}' → '{nuevo_estado}'"
        )
    envio['estado'] = nuevo_estado
    return envio
