public class Validador {

    public boolean esPrimo(int n) {
        if (n < 2) return false;
        if (n == 2) return true;
        if (n % 2 == 0) return false;
        for (int i = 3; i * i <= n; i += 2) {
            if (n % i == 0) return false;
        }
        return true;
    }

    public boolean esPar(int n) {
        return n % 2 == 0;
    }

    public boolean estaEnRango(int valor, int min, int max) {
        if (min > max) throw new IllegalArgumentException("min no puede ser mayor que max");
        return valor >= min && valor <= max;
    }

    public boolean esPositivo(double valor) {
        return valor > 0;
    }
}
