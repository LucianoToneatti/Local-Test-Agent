function calcular_multa(dias_atraso, tarifa_diaria) {
    if (dias_atraso < 0) throw new Error("Los días de atraso no pueden ser negativos");
    if (tarifa_diaria <= 0) throw new Error("La tarifa diaria debe ser positiva");
    return dias_atraso * tarifa_diaria;
}

function calcular_multa_con_tope(dias_atraso, tarifa_diaria, tope) {
    if (tope <= 0) throw new Error("El tope debe ser positivo");
    return Math.min(calcular_multa(dias_atraso, tarifa_diaria), tope);
}

function tiene_multa_pendiente(usuario) {
    return usuario.multa_acumulada > 0;
}

function aplicar_descuento(multa, porcentaje) {
    if (porcentaje < 0 || porcentaje > 100) throw new Error("El porcentaje debe estar entre 0 y 100");
    return multa * (1 - porcentaje / 100);
}

module.exports = { calcular_multa, calcular_multa_con_tope, tiene_multa_pendiente, aplicar_descuento };
