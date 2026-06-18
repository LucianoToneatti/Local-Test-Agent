public class Materia {
    private String codigo;
    private String nombre;
    private int creditos;

    public Materia(String codigo, String nombre, int creditos) {
        if (codigo == null || codigo.isBlank()) throw new IllegalArgumentException("El código no puede estar vacío");
        if (nombre == null || nombre.isBlank()) throw new IllegalArgumentException("El nombre no puede estar vacío");
        if (creditos <= 0) throw new IllegalArgumentException("Los créditos deben ser positivos");
        this.codigo = codigo;
        this.nombre = nombre;
        this.creditos = creditos;
    }

    public String getCodigo() { return codigo; }
    public String getNombre() { return nombre; }
    public int getCreditos() { return creditos; }

    public boolean esEquivalente(Materia otra) {
        if (otra == null) return false;
        return this.creditos == otra.creditos && this.nombre.equalsIgnoreCase(otra.nombre);
    }

    public String toString() {
        return "[" + codigo + "] " + nombre + " (" + creditos + " créditos)";
    }
}
