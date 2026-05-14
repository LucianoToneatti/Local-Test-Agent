const { sumar, dividir } = require('./calculadora');

function promedio(numeros) {
  if (!numeros || numeros.length === 0) {
    throw new Error('La lista no puede estar vacía');
  }
  const suma = numeros.reduce((acc, n) => sumar(acc, n), 0);
  return dividir(suma, numeros.length);
}

function varianza(numeros) {
  if (!numeros || numeros.length === 0) {
    throw new Error('La lista no puede estar vacía');
  }
  const media = promedio(numeros);
  const suma = numeros.reduce((acc, n) => sumar(acc, (n - media) ** 2), 0);
  return dividir(suma, numeros.length);
}

module.exports = { promedio, varianza };
