import java.util.List;

public class Calculadora {

    public double promedio(List<Double> notas) {
        if (notas == null || notas.isEmpty()) throw new IllegalArgumentException("La lista no puede estar vacía");
        double suma = 0;
        for (double n : notas) suma += n;
        return suma / notas.size();
    }

    public double notaMaxima(List<Double> notas) {
        if (notas == null || notas.isEmpty()) throw new IllegalArgumentException("La lista no puede estar vacía");
        double max = notas.get(0);
        for (double n : notas) if (n > max) max = n;
        return max;
    }

    public double notaMinima(List<Double> notas) {
        if (notas == null || notas.isEmpty()) throw new IllegalArgumentException("La lista no puede estar vacía");
        double min = notas.get(0);
        for (double n : notas) if (n < min) min = n;
        return min;
    }

    public int contarAprobados(List<Double> notas) {
        if (notas == null) return 0;
        int count = 0;
        for (double n : notas) if (n >= 6.0) count++;
        return count;
    }

    public double porcentajeAprobados(List<Double> notas) {
        if (notas == null || notas.isEmpty()) return 0.0;
        return (double) contarAprobados(notas) / notas.size() * 100;
    }
}
