public class Formateador {

    public String formatearEstudiante(String legajo, String nombre, int anioIngreso) {
        if (legajo == null || nombre == null) throw new IllegalArgumentException("Legajo y nombre son obligatorios");
        return String.format("[%s] %s (ingreso: %d)", legajo, nombre, anioIngreso);
    }

    public String formatearNota(double nota) {
        if (nota < 0 || nota > 10) throw new IllegalArgumentException("La nota debe estar entre 0 y 10");
        return String.format("%.2f", nota);
    }

    public String formatearPeriodo(int anio, int cuatrimestre) {
        if (cuatrimestre < 1 || cuatrimestre > 2) throw new IllegalArgumentException("El cuatrimestre debe ser 1 o 2");
        return anio + "C" + cuatrimestre;
    }

    public String formatearPorcentaje(double valor) {
        if (valor < 0 || valor > 100) throw new IllegalArgumentException("El porcentaje debe estar entre 0 y 100");
        return String.format("%.1f%%", valor);
    }
}
