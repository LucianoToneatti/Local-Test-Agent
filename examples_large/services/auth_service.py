"""Registro, autenticación y gestión de sesiones de usuarios."""

import secrets
from datetime import datetime, timedelta

from models.usuario import Usuario
from utils.validadores import validar_email
from exceptions import AutenticacionError, ValidacionError, UsuarioNoEncontradoError

# Estado en memoria para sesiones activas: token → {usuario_id, expira}
_sesiones: dict[str, dict] = {}

_DURACION_SESION_HORAS = 8


# ------------------------------------------------------------------
# Registro
# ------------------------------------------------------------------

def registrar_usuario(id: int, nombre: str, apellido: str,
                      email: str, password: str,
                      repositorio: dict) -> Usuario:
    """Crea y persiste un nuevo Usuario en el repositorio dado.

    Verifica unicidad de email, formato válido y contraseña segura.
    """
    if not validar_email(email):
        raise ValidacionError(f"Email inválido: '{email}'")
    if any(u.email == email for u in repositorio.values()):
        raise ValidacionError(f"El email '{email}' ya está en uso")
    if len(password) < 8:
        raise ValidacionError("La contraseña debe tener al menos 8 caracteres")

    usuario = Usuario(id, nombre, apellido, email)
    usuario.validar()
    usuario.set_password(password)
    repositorio[id] = usuario
    return usuario


# ------------------------------------------------------------------
# Autenticación
# ------------------------------------------------------------------

def iniciar_sesion(email: str, password: str, repositorio: dict) -> str:
    """Autentica al usuario y retorna un token de sesión de 64 hex chars.

    Lanza AutenticacionError si las credenciales son incorrectas o la
    cuenta está inactiva.
    """
    usuario = next((u for u in repositorio.values() if u.email == email), None)
    if usuario is None:
        raise AutenticacionError("Credenciales incorrectas")
    if not usuario.activo:
        raise AutenticacionError("La cuenta está desactivada")
    if not usuario.verificar_password(password):
        raise AutenticacionError("Credenciales incorrectas")

    token = secrets.token_hex(32)
    _sesiones[token] = {
        'usuario_id': usuario.id,
        'expira': datetime.now() + timedelta(hours=_DURACION_SESION_HORAS),
    }
    return token


def cerrar_sesion(token: str) -> bool:
    """Invalida el token de sesión. Devuelve True si existía, False si no."""
    if token in _sesiones:
        del _sesiones[token]
        return True
    return False


def validar_sesion(token: str) -> int:
    """Verifica que el token sea válido y no haya expirado; retorna usuario_id."""
    if token not in _sesiones:
        raise AutenticacionError("Sesión inválida o inexistente")
    sesion = _sesiones[token]
    if datetime.now() > sesion['expira']:
        del _sesiones[token]
        raise AutenticacionError("La sesión ha expirado")
    return sesion['usuario_id']


# ------------------------------------------------------------------
# Cambio de contraseña
# ------------------------------------------------------------------

def cambiar_password(usuario: Usuario, password_actual: str,
                     password_nueva: str) -> bool:
    """Cambia la contraseña tras verificar la actual.

    Exige que la nueva contraseña sea distinta y tenga al menos 8 chars.
    """
    if not usuario.verificar_password(password_actual):
        raise AutenticacionError("La contraseña actual es incorrecta")
    if len(password_nueva) < 8:
        raise ValidacionError("La nueva contraseña debe tener al menos 8 caracteres")
    if password_actual == password_nueva:
        raise ValidacionError("La nueva contraseña debe ser diferente a la actual")
    usuario.set_password(password_nueva)
    return True


# ------------------------------------------------------------------
# Helper para tests
# ------------------------------------------------------------------

def limpiar_sesiones() -> int:
    """Elimina todas las sesiones activas. Devuelve la cantidad eliminada."""
    cantidad = len(_sesiones)
    _sesiones.clear()
    return cantidad
