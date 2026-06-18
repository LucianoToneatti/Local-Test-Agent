import java.util.ArrayList;
import java.util.List;

public class GestorMaterias {
    private List<Materia> materias;

    public GestorMaterias() {
        this.materias = new ArrayList<>();
    }

    public void agregar(Materia m) {
        if (buscarPorCodigo(m.getCodigo()) != null) throw new IllegalArgumentException("Ya existe una materia con ese código");
        materias.add(m);
    }

    public Materia buscarPorCodigo(String codigo) {
        for (Materia m : materias) {
            if (m.getCodigo().equals(codigo)) return m;
        }
        return null;
    }

    public List<Materia> buscarPorCreditos(int creditos) {
        List<Materia> resultado = new ArrayList<>();
        for (Materia m : materias) {
            if (m.getCreditos() == creditos) resultado.add(m);
        }
        return resultado;
    }

    public int totalCreditos() {
        int total = 0;
        for (Materia m : materias) total += m.getCreditos();
        return total;
    }
}
