"""Excepciones del sistema de librería online."""


class LibreriaError(Exception):
    """Excepción base del sistema."""


class StockInsuficienteError(LibreriaError):
    """Se intenta reservar más unidades de las disponibles."""


class ProductoNoEncontradoError(LibreriaError):
    """El producto no existe en el catálogo o inventario."""


class UsuarioNoEncontradoError(LibreriaError):
    """El usuario no existe en el repositorio."""


class AutenticacionError(LibreriaError):
    """Credenciales inválidas o sesión expirada."""


class PagoError(LibreriaError):
    """Error durante el procesamiento del pago."""


class ValidacionError(LibreriaError):
    """Datos de entrada no pasan las reglas de negocio."""


class PedidoError(LibreriaError):
    """Operación inválida sobre un pedido (estado incorrecto, vacío, etc.)."""
