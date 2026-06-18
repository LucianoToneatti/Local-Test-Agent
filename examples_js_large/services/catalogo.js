const { crear_libro, esta_disponible } = require('../models/libro');

function agregar_libro(catalogo, isbn, titulo, autor, anio, copias) {
    if (catalogo[isbn]) throw new Error(`El libro con ISBN ${isbn} ya existe`);
    const libro = crear_libro(isbn, titulo, autor, anio, copias);
    return { ...catalogo, [isbn]: libro };
}

function buscar_por_isbn(catalogo, isbn) {
    return catalogo[isbn] || null;
}

function listar_disponibles(catalogo) {
    return Object.values(catalogo).filter(esta_disponible);
}

function contar_total(catalogo) {
    return Object.keys(catalogo).length;
}

module.exports = { agregar_libro, buscar_por_isbn, listar_disponibles, contar_total };
