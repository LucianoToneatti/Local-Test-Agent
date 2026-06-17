"""Procesamiento de pagos, validación de tarjetas y reembolsos."""

from datetime import datetime

from models.pedido import Pedido, EstadoPedido
from utils.calculadora_precios import calcular_iva
from exceptions import PagoError, PedidoError

# Alícuotas de IVA por provincia (Argentina)
_IVA_PROVINCIAL: dict[str, float] = {
    'CABA':          21.0,
    'Buenos Aires':  21.0,
    'Córdoba':       21.0,
    'Santa Fe':      21.0,
    'Mendoza':       21.0,
    'Tucumán':       21.0,
    'Salta':         21.0,
}
_IVA_DEFAULT = 21.0


def validar_tarjeta(numero: str, cvv: str, mes: int, anio: int) -> bool:
    """Valida datos de tarjeta de crédito/débito usando el algoritmo de Luhn.

    Número de prueba válido (Luhn): 4111111111111111
    Lanza PagoError con mensaje específico para cada tipo de error.
    """
    numero_limpio = numero.replace(' ', '').replace('-', '')
    if not numero_limpio.isdigit() or len(numero_limpio) not in (13, 15, 16):
        raise PagoError("Número de tarjeta inválido: debe tener 13, 15 o 16 dígitos")
    if not cvv.isdigit() or len(cvv) not in (3, 4):
        raise PagoError("CVV inválido: debe tener 3 o 4 dígitos")
    if not 1 <= mes <= 12:
        raise PagoError(f"Mes de vencimiento inválido: {mes}")

    ahora = datetime.now()
    if anio < ahora.year or (anio == ahora.year and mes < ahora.month):
        raise PagoError("La tarjeta está vencida")

    # Algoritmo de Luhn
    total = 0
    for i, d in enumerate(reversed(numero_limpio)):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    if total % 10 != 0:
        raise PagoError("Número de tarjeta inválido (falla Luhn)")
    return True


def procesar_pago(pedido: Pedido, metodo: str, monto: float) -> dict:
    """Procesa el pago de un pedido confirmado.

    Métodos aceptados: 'tarjeta', 'transferencia', 'efectivo'.
    Verifica que el monto coincida con el total del pedido (±0.01).
    Devuelve un comprobante de pago.
    """
    if pedido.estado != EstadoPedido.CONFIRMADO:
        raise PedidoError(
            "El pedido debe estar confirmado para procesar el pago"
        )
    metodos_validos = ('tarjeta', 'transferencia', 'efectivo')
    if metodo not in metodos_validos:
        raise PagoError(
            f"Método de pago '{metodo}' no soportado. "
            f"Opciones: {metodos_validos}"
        )
    total_pedido = pedido.calcular_total()
    if abs(monto - total_pedido) > 0.01:
        raise PagoError(
            f"Monto incorrecto: esperado={total_pedido:.2f}, recibido={monto:.2f}"
        )
    return {
        'pedido_id': pedido.id,
        'metodo': metodo,
        'monto': monto,
        'estado': 'aprobado',
        'timestamp': datetime.now().isoformat(),
    }


def calcular_total_con_impuestos(monto: float, provincia: str) -> float:
    """Agrega IVA provincial al monto base.

    Si la provincia no está en el mapa usa alícuota general del 21 %.
    """
    if monto < 0:
        raise PagoError("El monto no puede ser negativo")
    alicuota = _IVA_PROVINCIAL.get(provincia, _IVA_DEFAULT)
    iva = calcular_iva(monto, alicuota)
    return round(monto + iva, 2)


def reembolsar_pago(comprobante: dict, motivo: str) -> dict:
    """Genera un comprobante de reembolso a partir de un pago aprobado.

    Lanza PagoError si el comprobante no está en estado 'aprobado' o
    el motivo es vacío.
    """
    if comprobante.get('estado') != 'aprobado':
        raise PagoError("Solo se pueden reembolsar pagos con estado 'aprobado'")
    if not motivo or not motivo.strip():
        raise PagoError("El motivo del reembolso es obligatorio")
    return {
        'pedido_id': comprobante['pedido_id'],
        'monto_reembolsado': comprobante['monto'],
        'motivo': motivo.strip(),
        'estado': 'reembolsado',
        'timestamp': datetime.now().isoformat(),
    }
