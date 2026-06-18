public class Geometria {

    public double areaCirculo(double radio) {
        if (radio < 0) throw new IllegalArgumentException("El radio no puede ser negativo");
        return Math.PI * radio * radio;
    }

    public double areaRectangulo(double base, double altura) {
        if (base < 0 || altura < 0) throw new IllegalArgumentException("Las dimensiones no pueden ser negativas");
        return base * altura;
    }

    public double perimetroCirculo(double radio) {
        if (radio < 0) throw new IllegalArgumentException("El radio no puede ser negativo");
        return 2 * Math.PI * radio;
    }

    public double hipotenusa(double cateto1, double cateto2) {
        if (cateto1 <= 0 || cateto2 <= 0) throw new IllegalArgumentException("Los catetos deben ser positivos");
        return Math.sqrt(cateto1 * cateto1 + cateto2 * cateto2);
    }
}
