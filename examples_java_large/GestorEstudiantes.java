import java.util.ArrayList;
import java.util.List;

public class GestorEstudiantes {
    private List<Estudiante> estudiantes;

    public GestorEstudiantes() {
        this.estudiantes = new ArrayList<>();
    }

    public void registrar(Estudiante e) {
        if (buscarPorLegajo(e.getLegajo()) != null) throw new IllegalArgumentException("Ya existe un estudiante con ese legajo");
        estudiantes.add(e);
    }

    public Estudiante buscarPorLegajo(String legajo) {
        for (Estudiante e : estudiantes) {
            if (e.getLegajo().equals(legajo)) return e;
        }
        return null;
    }

    public List<Estudiante> listarActivos(int anioActual) {
        List<Estudiante> activos = new ArrayList<>();
        for (Estudiante e : estudiantes) {
            if (e.estaActivo(anioActual)) activos.add(e);
        }
        return activos;
    }

    public int contarTotal() {
        return estudiantes.size();
    }
}
