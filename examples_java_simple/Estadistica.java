import java.util.Arrays;

public class Estadistica {

    public double media(double[] valores) {
        if (valores == null || valores.length == 0) throw new IllegalArgumentException("El arreglo no puede estar vacío");
        double suma = 0;
        for (double v : valores) suma += v;
        return suma / valores.length;
    }

    public double mediana(double[] valores) {
        if (valores == null || valores.length == 0) throw new IllegalArgumentException("El arreglo no puede estar vacío");
        double[] copia = Arrays.copyOf(valores, valores.length);
        Arrays.sort(copia);
        int n = copia.length;
        return n % 2 == 0 ? (copia[n / 2 - 1] + copia[n / 2]) / 2.0 : copia[n / 2];
    }

    public double moda(double[] valores) {
        if (valores == null || valores.length == 0) throw new IllegalArgumentException("El arreglo no puede estar vacío");
        double moda = valores[0];
        int maxConteo = 0;
        for (double v : valores) {
            int conteo = 0;
            for (double w : valores) if (w == v) conteo++;
            if (conteo > maxConteo) { maxConteo = conteo; moda = v; }
        }
        return moda;
    }

    public double desviacionEstandar(double[] valores) {
        if (valores == null || valores.length == 0) throw new IllegalArgumentException("El arreglo no puede estar vacío");
        double m = media(valores);
        double suma = 0;
        for (double v : valores) suma += (v - m) * (v - m);
        return Math.sqrt(suma / valores.length);
    }
}
