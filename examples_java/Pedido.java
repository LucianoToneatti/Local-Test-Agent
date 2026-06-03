import java.util.ArrayList;
import java.util.List;

public class Pedido {

    private List<String> items = new ArrayList<>();
    private double descuento = 0.0;

    public void agregarItem(String nombre, double precio) {
        if (nombre == null || nombre.isBlank()) {
            throw new IllegalArgumentException("El nombre del item no puede ser vacío");
        }
        if (precio < 0) {
            throw new IllegalArgumentException("El precio no puede ser negativo");
        }
        items.add(nombre + ":" + precio);
    }

    public int cantidadItems() {
        return items.size();
    }

    public void aplicarDescuento(double porcentaje) {
        if (porcentaje < 0 || porcentaje > 100) {
            throw new IllegalArgumentException("El descuento debe estar entre 0 y 100");
        }
        this.descuento = porcentaje;
    }

    public double calcularTotal() {
        double subtotal = items.stream()
            .mapToDouble(item -> Double.parseDouble(item.split(":")[1]))
            .sum();
        return subtotal * (1 - descuento / 100.0);
    }

    public boolean estaVacio() {
        return items.isEmpty();
    }
}
