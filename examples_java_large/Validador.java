public class Validador {

    public boolean esLegajoValido(String legajo) {
        if (legajo == null) return false;
        return legajo.matches("^[A-Z]{1,3}\\d{4,8}$");
    }

    public boolean esEmailValido(String email) {
        if (email == null) return false;
        return email.matches("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$");
    }

    public boolean esNotaValida(double nota) {
        return nota >= 0 && nota <= 10;
    }

    public boolean esCuatrimestreValido(int cuatrimestre) {
        return cuatrimestre == 1 || cuatrimestre == 2;
    }

    public boolean esAnioValido(int anio) {
        return anio >= 1900 && anio <= 2100;
    }
}
