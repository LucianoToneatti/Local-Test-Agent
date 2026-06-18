function buscar_por_titulo(catalogo, termino) {
    if (!termino) return [];
    const t = termino.toLowerCase();
    return Object.values(catalogo).filter(l => l.titulo.toLowerCase().includes(t));
}

function buscar_por_autor(catalogo, autor) {
    if (!autor) return [];
    const a = autor.toLowerCase();
    return Object.values(catalogo).filter(l => l.autor.toLowerCase().includes(a));
}

function buscar_por_anio(catalogo, anio) {
    return Object.values(catalogo).filter(l => l.anio === anio);
}

function ordenar_por_titulo(libros) {
    return [...libros].sort((a, b) => a.titulo.localeCompare(b.titulo));
}

module.exports = { buscar_por_titulo, buscar_por_autor, buscar_por_anio, ordenar_por_titulo };
