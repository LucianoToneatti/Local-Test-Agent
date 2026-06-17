"""Registro centralizado de stock para todos los productos."""

from exceptions import StockInsuficienteError, ProductoNoEncontradoError


class Inventario:
    def __init__(self):
        self._stock: dict[int, int] = {}           # producto_id → cantidad
        self._productos: dict[int, object] = {}    # producto_id → Producto

    # ------------------------------------------------------------------
    # Alta de productos
    # ------------------------------------------------------------------

    def registrar_producto(self, producto, cantidad_inicial: int = 0) -> None:
        """Incorpora un producto al inventario con stock inicial.

        Si el producto ya estaba registrado, reemplaza el stock existente.
        """
        if cantidad_inicial < 0:
            raise ValueError("La cantidad inicial no puede ser negativa")
        self._productos[producto.id] = producto
        self._stock[producto.id] = cantidad_inicial
        producto.stock = cantidad_inicial

    # ------------------------------------------------------------------
    # Movimientos de stock
    # ------------------------------------------------------------------

    def agregar_stock(self, producto_id: int, cantidad: int) -> int:
        """Suma unidades al stock; devuelve el nuevo total."""
        self._verificar_registrado(producto_id)
        if cantidad <= 0:
            raise ValueError("La cantidad a agregar debe ser positiva")
        self._stock[producto_id] += cantidad
        self._productos[producto_id].stock = self._stock[producto_id]
        return self._stock[producto_id]

    def reducir_stock(self, producto_id: int, cantidad: int) -> int:
        """Resta unidades al stock; devuelve el nuevo total.

        Lanza StockInsuficienteError si no hay suficiente stock.
        """
        self._verificar_registrado(producto_id)
        if cantidad <= 0:
            raise ValueError("La cantidad a reducir debe ser positiva")
        disponible = self._stock[producto_id]
        if disponible < cantidad:
            raise StockInsuficienteError(
                f"Stock insuficiente para producto {producto_id}: "
                f"disponible={disponible}, requerido={cantidad}"
            )
        self._stock[producto_id] -= cantidad
        self._productos[producto_id].stock = self._stock[producto_id]
        return self._stock[producto_id]

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------

    def obtener_stock(self, producto_id: int) -> int:
        """Devuelve la cantidad disponible de un producto."""
        self._verificar_registrado(producto_id)
        return self._stock[producto_id]

    def productos_bajo_stock(self, umbral: int = 5) -> list:
        """Lista los productos cuyo stock es ≤ umbral."""
        if umbral < 0:
            raise ValueError("El umbral no puede ser negativo")
        return [
            self._productos[pid]
            for pid, qty in self._stock.items()
            if qty <= umbral
        ]

    def valor_total_inventario(self) -> float:
        """Calcula el valor contable del inventario (precio × stock por producto)."""
        total = sum(
            self._productos[pid].precio * qty
            for pid, qty in self._stock.items()
        )
        return round(total, 2)

    def total_productos_registrados(self) -> int:
        """Devuelve la cantidad de SKUs distintos registrados."""
        return len(self._productos)

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    def _verificar_registrado(self, producto_id: int) -> None:
        if producto_id not in self._stock:
            raise ProductoNoEncontradoError(
                f"Producto con id={producto_id} no está registrado en el inventario"
            )
