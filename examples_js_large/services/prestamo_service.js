const { puede_pedir_prestamo } = require('../models/usuario');
const { esta_disponible, reducir_disponibles, aumentar_disponibles } = require('../models/libro');
const { crear_prestamo, marcar_devuelto, dias_de_atraso } = require('../models/prestamo');

function realizar_prestamo(usuario, libro, prestamo_id, dias_plazo) {
    if (!puede_pedir_prestamo(usuario)) throw new Error("El usuario no puede realizar más préstamos");
    if (!esta_disponible(libro)) throw new Error("No hay copias disponibles");
    const libro_actualizado = reducir_disponibles(libro);
    const usuario_actualizado = { ...usuario, prestamos_activos: usuario.prestamos_activos + 1 };
    const prestamo = crear_prestamo(prestamo_id, libro.isbn, usuario.id, new Date().toISOString(), dias_plazo);
    return { usuario: usuario_actualizado, libro: libro_actualizado, prestamo };
}

function devolver_libro(usuario, libro, prestamo, tarifa_diaria) {
    if (prestamo.devuelto) throw new Error("El préstamo ya fue devuelto");
    const atraso = dias_de_atraso(prestamo);
    const multa = atraso * tarifa_diaria;
    const prestamo_actualizado = marcar_devuelto(prestamo);
    const libro_actualizado = aumentar_disponibles(libro);
    const usuario_actualizado = {
        ...usuario,
        prestamos_activos: usuario.prestamos_activos - 1,
        multa_acumulada: usuario.multa_acumulada + multa,
    };
    return { usuario: usuario_actualizado, libro: libro_actualizado, prestamo: prestamo_actualizado, multa };
}

module.exports = { realizar_prestamo, devolver_libro };
