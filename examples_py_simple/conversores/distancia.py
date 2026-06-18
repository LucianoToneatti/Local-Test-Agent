def km_a_millas(km):
    if not isinstance(km, (int, float)):
        raise TypeError("La distancia debe ser un número")
    if km < 0:
        raise ValueError("La distancia no puede ser negativa")
    return km * 0.621371


def millas_a_km(millas):
    if not isinstance(millas, (int, float)):
        raise TypeError("La distancia debe ser un número")
    if millas < 0:
        raise ValueError("La distancia no puede ser negativa")
    return millas / 0.621371


def metros_a_pies(metros):
    if not isinstance(metros, (int, float)):
        raise TypeError("La distancia debe ser un número")
    if metros < 0:
        raise ValueError("La distancia no puede ser negativa")
    return metros * 3.28084
