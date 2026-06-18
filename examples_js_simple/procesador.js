function contar_palabras(texto) {
    if (!texto || texto.trim() === "") return 0;
    return texto.trim().split(/\s+/).length;
}

function contar_vocales(texto) {
    if (!texto) return 0;
    return (texto.match(/[aeiouáéíóúAEIOUÁÉÍÓÚ]/g) || []).length;
}

function invertir_string(texto) {
    if (!texto) return "";
    return texto.split("").reverse().join("");
}

function capitalizar(texto) {
    if (!texto) return "";
    return texto
        .split(" ")
        .map(p => p.charAt(0).toUpperCase() + p.slice(1).toLowerCase())
        .join(" ");
}

module.exports = { contar_palabras, contar_vocales, invertir_string, capitalizar };
