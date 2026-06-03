public class Conversor {

    public double celsiusAFahrenheit(double celsius) {
        return celsius * 9.0 / 5.0 + 32;
    }

    public double fahrenheitACelsius(double fahrenheit) {
        return (fahrenheit - 32) * 5.0 / 9.0;
    }

    public double kmAMillas(double km) {
        if (km < 0) {
            throw new IllegalArgumentException("La distancia no puede ser negativa");
        }
        return km * 0.621371;
    }

    public double millasAKm(double millas) {
        if (millas < 0) {
            throw new IllegalArgumentException("La distancia no puede ser negativa");
        }
        return millas / 0.621371;
    }

    public double kgALibras(double kg) {
        if (kg < 0) {
            throw new IllegalArgumentException("El peso no puede ser negativo");
        }
        return kg * 2.20462;
    }

    public double librasAKg(double libras) {
        if (libras < 0) {
            throw new IllegalArgumentException("El peso no puede ser negativo");
        }
        return libras / 2.20462;
    }
}
