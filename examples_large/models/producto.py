"""Modelo de producto (libro) del catálogo."""

from utils.validadores import validar_isbn, validar_precio
from utils.calculadora_precios import calcular_precio_con_descuento
from exceptions import ValidacionError, StockInsuficienteError


class Producto:
    def __init__(self, id: int, titulo: str, autor: str, precio: float,
                 isbn: str, categoria: str, stock: int = 0):
        self.id = id
        self.titulo = titulo
        self.autor = autor
        self.precio = precio
        self.isbn = isbn
        self.categoria = categoria
        self.stock = stock
        self._descuento: float = 0.0  # porcentaje activo (0-100)

    # ------------------------------------------------------------------
    # Validación
    # ------------------------------------------------------------------

    def validar(self) -> bool:
        """Valida los campos obligatorios del producto."""
        if not self.titulo or not self.titulo.strip():
            raise ValidacionError("El título no puede estar vacío")
        if not self.autor or not self.autor.strip():
            raise ValidacionError("El autor no puede estar vacío")
        if not validar_precio(self.precio):
            raise ValidacionError(f"Precio inválido: {self.precio}")
        if not validar_isbn(self.isbn):
            raise ValidacionError(f"ISBN inválido: '{self.isbn}'")
        return True

    # ------------------------------------------------------------------
    # Precio
    # ------------------------------------------------------------------

    def precio_final(self) -> float:
        """Devuelve el precio con el descuento activo aplicado."""
        if self._descuento > 0:
            return calcular_precio_con_descuento(self.precio, self._descuento)
        return round(self.precio, 2)

    def aplicar_descuento(self, porcentaje: float) -> None:
        """Activa un descuento porcentual sobre el precio base.

        Un porcentaje de 0 elimina el descuento activo.
        """
        if not isinstance(porcentaje, (int, float)) or not 0 <= porcentaje <= 100:
            raise ValidacionError(
                f"El porcentaje de descuento debe estar entre 0 y 100, recibido: {porcentaje}"
            )
        self._descuento = float(porcentaje)

    # ------------------------------------------------------------------
    # Disponibilidad
    # ------------------------------------------------------------------

    def esta_disponible(self) -> bool:
        """True si hay al menos una unidad en stock."""
        return self.stock > 0

    def reducir_stock(self, cantidad: int) -> None:
        """Descuenta unidades del stock. Lanza StockInsuficienteError si no alcanza."""
        if cantidad <= 0:
            raise ValidacionError("La cantidad a reducir debe ser positiva")
        if cantidad > self.stock:
            raise StockInsuficienteError(
                f"Stock insuficiente para '{self.titulo}': "
                f"disponible={self.stock}, solicitado={cantidad}"
            )
        self.stock -= cantidad

    def agregar_stock(self, cantidad: int) -> None:
        """Incrementa el stock del producto."""
        if cantidad <= 0:
            raise ValidacionError("La cantidad a agregar debe ser positiva")
        self.stock += cantidad

    # ------------------------------------------------------------------
    # Serialización
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serializa el producto a diccionario."""
        return {
            'id': self.id,
            'titulo': self.titulo,
            'autor': self.autor,
            'precio': self.precio,
            'precio_final': self.precio_final(),
            'isbn': self.isbn,
            'categoria': self.categoria,
            'stock': self.stock,
            'descuento': self._descuento,
        }
