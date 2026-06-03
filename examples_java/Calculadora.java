public class Calculadora {

    public int suma(int a, int b) {
        return a + b;
    }

    public int resta(int a, int b) {
        return a - b;
    }

    public int multiplicar(int a, int b) {
        return a * b;
    }

    public double dividir(double dividendo, double divisor) {
        if (divisor == 0) {
            throw new IllegalArgumentException("El divisor no puede ser cero");
        }
        return dividendo / divisor;
    }

    public boolean esParejo(int numero) {
        return numero % 2 == 0;
    }
}
