public class Estadistica {

    private Calculadora calc = new Calculadora();

    public double promedio(int[] numeros) {
        if (numeros == null || numeros.length == 0) {
            throw new IllegalArgumentException("La lista no puede estar vacía");
        }
        int suma = 0;
        for (int n : numeros) {
            suma = calc.suma(suma, n);
        }
        return (double) suma / numeros.length;
    }

    public int productoTotal(int[] numeros) {
        if (numeros == null || numeros.length == 0) {
            throw new IllegalArgumentException("La lista no puede estar vacía");
        }
        int producto = 1;
        for (int n : numeros) {
            producto = calc.multiplicar(producto, n);
        }
        return producto;
    }

    public boolean todosPares(int[] numeros) {
        if (numeros == null || numeros.length == 0) {
            throw new IllegalArgumentException("La lista no puede estar vacía");
        }
        for (int n : numeros) {
            if (!calc.esParejo(n)) {
                return false;
            }
        }
        return true;
    }
}
