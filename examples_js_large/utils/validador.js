function es_isbn_valido(isbn) {
    if (!isbn) return false;
    const limpio = isbn.replace(/-/g, "");
    return /^\d{10}$/.test(limpio) || /^\d{13}$/.test(limpio);
}

function es_anio_valido(anio) {
    return Number.isInteger(anio) && anio >= 1450 && anio <= new Date().getFullYear();
}

function es_email_valido(email) {
    if (!email) return false;
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function es_positivo(valor) {
    return typeof valor === "number" && valor > 0;
}

module.exports = { es_isbn_valido, es_anio_valido, es_email_valido, es_positivo };
