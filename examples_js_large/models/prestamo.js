function crear_prestamo(id, isbn, usuario_id, fecha_inicio, dias_plazo) {
    if (!id || !isbn || !usuario_id) throw new Error("ID, ISBN y usuario_id son obligatorios");
    if (dias_plazo <= 0) throw new Error("El plazo debe ser mayor a cero");
    const inicio = new Date(fecha_inicio);
    const vencimiento = new Date(inicio);
    vencimiento.setDate(vencimiento.getDate() + dias_plazo);
    return { id, isbn, usuario_id, fecha_inicio: inicio.toISOString(), fecha_vencimiento: vencimiento.toISOString(), devuelto: false };
}

function esta_vencido(prestamo) {
    if (prestamo.devuelto) return false;
    return new Date() > new Date(prestamo.fecha_vencimiento);
}

function marcar_devuelto(prestamo) {
    if (prestamo.devuelto) throw new Error("El préstamo ya fue devuelto");
    return { ...prestamo, devuelto: true };
}

function dias_de_atraso(prestamo) {
    if (prestamo.devuelto || !esta_vencido(prestamo)) return 0;
    const diff = new Date() - new Date(prestamo.fecha_vencimiento);
    return Math.ceil(diff / (1000 * 60 * 60 * 24));
}

module.exports = { crear_prestamo, esta_vencido, marcar_devuelto, dias_de_atraso };
