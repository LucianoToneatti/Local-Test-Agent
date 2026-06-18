public class Calificacion {
    private String inscripcionId;
    private double nota;
    private String observaciones;

    public Calificacion(String inscripcionId, double nota) {
        if (inscripcionId == null || inscripcionId.isBlank()) throw new IllegalArgumentException("El ID de inscripción no puede estar vacío");
        if (nota < 0 || nota > 10) throw new IllegalArgumentException("La nota debe estar entre 0 y 10");
        this.inscripcionId = inscripcionId;
        this.nota = nota;
        this.observaciones = "";
    }

    public String getInscripcionId() { return inscripcionId; }
    public double getNota() { return nota; }
    public String getObservaciones() { return observaciones; }

    public boolean estaAprobada() {
        return nota >= 6.0;
    }

    public String obtenerLetra() {
        if (nota >= 9) return "A";
        if (nota >= 7) return "B";
        if (nota >= 6) return "C";
        if (nota >= 4) return "D";
        return "F";
    }

    public void agregarObservacion(String obs) {
        if (obs == null || obs.isBlank()) throw new IllegalArgumentException("La observación no puede estar vacía");
        this.observaciones = obs;
    }
}
