"""Modelo de usuario del sistema."""

import hashlib
from datetime import datetime

from utils.validadores import validar_email, validar_nombre
from exceptions import ValidacionError


class Usuario:
    def __init__(self, id: int, nombre: str, apellido: str, email: str,
                 activo: bool = True):
        self.id = id
        self.nombre = nombre
        self.apellido = apellido
        self.email = email
        self.activo = activo
        self.fecha_registro = datetime.now()
        self._password_hash: str | None = None

    # ------------------------------------------------------------------
    # Validación
    # ------------------------------------------------------------------

    def validar(self) -> bool:
        """Valida todos los campos del usuario; lanza ValidacionError si algo falla."""
        if not validar_nombre(self.nombre):
            raise ValidacionError(f"Nombre inválido: '{self.nombre}'")
        if not validar_nombre(self.apellido):
            raise ValidacionError(f"Apellido inválido: '{self.apellido}'")
        if not validar_email(self.email):
            raise ValidacionError(f"Email inválido: '{self.email}'")
        if self.id <= 0:
            raise ValidacionError(f"ID de usuario inválido: {self.id}")
        return True

    # ------------------------------------------------------------------
    # Identidad
    # ------------------------------------------------------------------

    def nombre_completo(self) -> str:
        """Devuelve 'Nombre Apellido'."""
        return f"{self.nombre.strip()} {self.apellido.strip()}"

    # ------------------------------------------------------------------
    # Autenticación
    # ------------------------------------------------------------------

    def set_password(self, password: str) -> None:
        """Hashea y almacena la contraseña. Exige mínimo 8 caracteres."""
        if not password or len(password) < 8:
            raise ValidacionError("La contraseña debe tener al menos 8 caracteres")
        self._password_hash = hashlib.sha256(password.encode()).hexdigest()

    def verificar_password(self, password: str) -> bool:
        """Devuelve True si el password coincide con el hash almacenado."""
        if self._password_hash is None:
            return False
        return self._password_hash == hashlib.sha256(password.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------

    def desactivar(self) -> None:
        """Marca la cuenta como inactiva."""
        self.activo = False

    def activar(self) -> None:
        """Reactiva una cuenta previamente desactivada."""
        self.activo = True

    # ------------------------------------------------------------------
    # Serialización
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serializa el usuario a diccionario (sin password hash)."""
        return {
            'id': self.id,
            'nombre': self.nombre,
            'apellido': self.apellido,
            'email': self.email,
            'activo': self.activo,
            'fecha_registro': self.fecha_registro.isoformat(),
        }
