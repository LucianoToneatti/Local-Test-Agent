"""Modelo de pedido con máquina de estados."""

from datetime import datetime
from enum import Enum

from exceptions import PedidoError, StockInsuficienteError


class EstadoPedido(Enum):
    PENDIENTE = "pendiente"
    CONFIRMADO = "confirmado"
    ENVIADO = "enviado"
    ENTREGADO = "entregado"
    CANCELADO = "cancelado"


class Pedido:
    def __init__(self, id: int, usuario_id: int):
        self.id = id
        self.usuario_id = usuario_id
        self.items: list[dict] = []   # [{'producto': Producto, 'cantidad': int}]
        self.estado = EstadoPedido.PENDIENTE
        self.fecha_creacion = datetime.now()
        self.fecha_actualizacion = datetime.now()
        self.descuento_global: float = 0.0   # porcentaje aplicado al total

    # ------------------------------------------------------------------
    # Gestión de items
    # ------------------------------------------------------------------

    def agregar_item(self, producto, cantidad: int) -> None:
        """Agrega o incrementa un producto en el pedido.

        Verifica disponibilidad antes de agregar. Si el producto ya estaba,
        suma la cantidad respetando el stock disponible.
        """
        if self.estado != EstadoPedido.PENDIENTE:
            raise PedidoError("Solo se pueden agregar items a pedidos pendientes")
        if cantidad <= 0:
            raise PedidoError("La cantidad debe ser positiva")
        if not producto.esta_disponible():
            raise StockInsuficienteError(f"'{producto.titulo}' no está disponible")

        for item in self.items:
            if item['producto'].id == producto.id:
                nueva = item['cantidad'] + cantidad
                if nueva > producto.stock:
                    raise StockInsuficienteError(
                        f"Stock insuficiente para '{producto.titulo}'"
                    )
                item['cantidad'] = nueva
                self.fecha_actualizacion = datetime.now()
                return

        if cantidad > producto.stock:
            raise StockInsuficienteError(
                f"Stock insuficiente para '{producto.titulo}'"
            )
        self.items.append({'producto': producto, 'cantidad': cantidad})
        self.fecha_actualizacion = datetime.now()

    def remover_item(self, producto_id: int) -> None:
        """Elimina un producto del pedido por su ID."""
        for i, item in enumerate(self.items):
            if item['producto'].id == producto_id:
                self.items.pop(i)
                self.fecha_actualizacion = datetime.now()
                return
        raise PedidoError(f"Producto con id={producto_id} no encontrado en el pedido")

    # ------------------------------------------------------------------
    # Totales
    # ------------------------------------------------------------------

    def calcular_subtotal(self) -> float:
        """Suma precio_final × cantidad de cada item (sin descuento global)."""
        return round(
            sum(item['producto'].precio_final() * item['cantidad'] for item in self.items),
            2,
        )

    def calcular_total(self) -> float:
        """Aplica el descuento global sobre el subtotal."""
        subtotal = self.calcular_subtotal()
        if self.descuento_global > 0:
            factor = 1 - self.descuento_global / 100
            subtotal = round(subtotal * factor, 2)
        return subtotal

    def cantidad_total_items(self) -> int:
        """Suma de todas las cantidades de los items."""
        return sum(item['cantidad'] for item in self.items)

    # ------------------------------------------------------------------
    # Transiciones de estado
    # ------------------------------------------------------------------

    def confirmar(self) -> None:
        """Confirma el pedido. Solo válido desde PENDIENTE y con al menos un item."""
        if self.estado != EstadoPedido.PENDIENTE:
            raise PedidoError(
                f"No se puede confirmar un pedido en estado '{self.estado.value}'"
            )
        if not self.items:
            raise PedidoError("No se puede confirmar un pedido vacío")
        self.estado = EstadoPedido.CONFIRMADO
        self.fecha_actualizacion = datetime.now()

    def cancelar(self) -> None:
        """Cancela el pedido. Inválido si ya fue entregado o ya estaba cancelado."""
        if self.estado in (EstadoPedido.ENTREGADO, EstadoPedido.CANCELADO):
            raise PedidoError(
                f"No se puede cancelar un pedido '{self.estado.value}'"
            )
        self.estado = EstadoPedido.CANCELADO
        self.fecha_actualizacion = datetime.now()

    def marcar_enviado(self) -> None:
        """Avanza el estado a ENVIADO desde CONFIRMADO."""
        if self.estado != EstadoPedido.CONFIRMADO:
            raise PedidoError(
                f"No se puede marcar como enviado un pedido '{self.estado.value}'"
            )
        self.estado = EstadoPedido.ENVIADO
        self.fecha_actualizacion = datetime.now()
