function formatear_libro(libro) {
    return `[${libro.isbn}] "${libro.titulo}" — ${libro.autor} (${libro.anio}) | Disponibles: ${libro.disponibles}/${libro.copias}`;
}

function formatear_usuario(usuario) {
    const multa = usuario.multa_acumulada > 0 ? ` | Multa: $${usuario.multa_acumulada.toFixed(2)}` : "";
    return `[${usuario.id}] ${usuario.nombre} <${usuario.email}> | Préstamos activos: ${usuario.prestamos_activos}${multa}`;
}

function formatear_fecha(isoString) {
    if (!isoString) return "—";
    const d = new Date(isoString);
    return `${d.getDate().toString().padStart(2, "0")}/${(d.getMonth() + 1).toString().padStart(2, "0")}/${d.getFullYear()}`;
}

function formatear_multa(monto) {
    if (monto === 0) return "Sin multa";
    return `$${monto.toFixed(2)}`;
}

module.exports = { formatear_libro, formatear_usuario, formatear_fecha, formatear_multa };
