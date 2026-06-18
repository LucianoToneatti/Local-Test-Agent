public class Inscripcion {
    private String id;
    private String legajoEstudiante;
    private String codigoMateria;
    private int anio;
    private int cuatrimestre;
    private boolean aprobada;

    public Inscripcion(String id, String legajoEstudiante, String codigoMateria, int anio, int cuatrimestre) {
        if (id == null || id.isBlank()) throw new IllegalArgumentException("El ID no puede estar vacío");
        if (cuatrimestre < 1 || cuatrimestre > 2) throw new IllegalArgumentException("El cuatrimestre debe ser 1 o 2");
        this.id = id;
        this.legajoEstudiante = legajoEstudiante;
        this.codigoMateria = codigoMateria;
        this.anio = anio;
        this.cuatrimestre = cuatrimestre;
        this.aprobada = false;
    }

    public String getId() { return id; }
    public String getLegajoEstudiante() { return legajoEstudiante; }
    public String getCodigoMateria() { return codigoMateria; }
    public int getAnio() { return anio; }
    public int getCuatrimestre() { return cuatrimestre; }
    public boolean isAprobada() { return aprobada; }

    public void aprobar() {
        if (aprobada) throw new IllegalStateException("La inscripción ya fue aprobada");
        this.aprobada = true;
    }

    public String getPeriodo() {
        return anio + "C" + cuatrimestre;
    }
}
