function truncar(texto, max) {
    if (!texto) return "";
    if (max <= 0) return "";
    return texto.length <= max ? texto : texto.slice(0, max) + "...";
}

function pad_left(texto, largo, caracter) {
    const c = caracter || " ";
    const s = String(texto);
    return s.length >= largo ? s : c.repeat(largo - s.length) + s;
}

function pad_right(texto, largo, caracter) {
    const c = caracter || " ";
    const s = String(texto);
    return s.length >= largo ? s : s + c.repeat(largo - s.length);
}

function limpiar_espacios(texto) {
    if (!texto) return "";
    return texto.trim().replace(/\s+/g, " ");
}

module.exports = { truncar, pad_left, pad_right, limpiar_espacios };
