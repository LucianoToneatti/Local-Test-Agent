function es_palindromo(texto) {
    if (!texto) return false;
    const limpio = texto.toLowerCase().replace(/[^a-z0-9]/g, "");
    return limpio === limpio.split("").reverse().join("");
}

function es_email_valido(email) {
    if (!email) return false;
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function tiene_numeros(texto) {
    if (!texto) return false;
    return /\d/.test(texto);
}

function es_vacio(texto) {
    return !texto || texto.trim() === "";
}

module.exports = { es_palindromo, es_email_valido, tiene_numeros, es_vacio };
