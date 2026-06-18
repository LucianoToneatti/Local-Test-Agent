function crear_usuario(id, nombre, email) {
    if (!id || !nombre || !email) throw new Error("ID, nombre y email son obligatorios");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new Error("Email inválido");
    return { id, nombre, email, prestamos_activos: 0, multa_acumulada: 0 };
}

function puede_pedir_prestamo(usuario) {
    return usuario.prestamos_activos < 3 && usuario.multa_acumulada === 0;
}

function agregar_multa(usuario, monto) {
    if (monto <= 0) throw new Error("El monto de la multa debe ser positivo");
    return { ...usuario, multa_acumulada: usuario.multa_acumulada + monto };
}

function saldar_multa(usuario) {
    return { ...usuario, multa_acumulada: 0 };
}

module.exports = { crear_usuario, puede_pedir_prestamo, agregar_multa, saldar_multa };
