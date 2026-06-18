public class Estudiante {
    private String legajo;
    private String nombre;
    private String email;
    private int anioIngreso;

    public Estudiante(String legajo, String nombre, String email, int anioIngreso) {
        if (legajo == null || legajo.isBlank()) throw new IllegalArgumentException("El legajo no puede estar vacío");
        if (nombre == null || nombre.isBlank()) throw new IllegalArgumentException("El nombre no puede estar vacío");
        if (anioIngreso < 1900 || anioIngreso > 2100) throw new IllegalArgumentException("Año de ingreso inválido");
        this.legajo = legajo;
        this.nombre = nombre;
        this.email = email;
        this.anioIngreso = anioIngreso;
    }

    public String getLegajo() { return legajo; }
    public String getNombre() { return nombre; }
    public String getEmail() { return email; }
    public int getAnioIngreso() { return anioIngreso; }

    public int calcularAniosEnCarrera(int anioActual) {
        if (anioActual < anioIngreso) throw new IllegalArgumentException("El año actual no puede ser menor al de ingreso");
        return anioActual - anioIngreso;
    }

    public boolean estaActivo(int anioActual) {
        return calcularAniosEnCarrera(anioActual) <= 10;
    }

    public String toString() {
        return "[" + legajo + "] " + nombre + " <" + email + ">";
    }
}
