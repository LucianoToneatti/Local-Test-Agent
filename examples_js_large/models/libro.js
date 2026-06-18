function crear_libro(isbn, titulo, autor, anio, copias) {
    if (!isbn || !titulo || !autor) throw new Error("ISBN, título y autor son obligatorios");
    if (anio < 1450 || anio > new Date().getFullYear()) throw new Error("Año inválido");
    if (copias < 0) throw new Error("Las copias no pueden ser negativas");
    return { isbn, titulo, autor, anio, copias, disponibles: copias };
}

function esta_disponible(libro) {
    return libro.disponibles > 0;
}

function reducir_disponibles(libro) {
    if (libro.disponibles <= 0) throw new Error("No hay copias disponibles");
    return { ...libro, disponibles: libro.disponibles - 1 };
}

function aumentar_disponibles(libro) {
    if (libro.disponibles >= libro.copias) throw new Error("Todas las copias ya están en stock");
    return { ...libro, disponibles: libro.disponibles + 1 };
}

module.exports = { crear_libro, esta_disponible, reducir_disponibles, aumentar_disponibles };
