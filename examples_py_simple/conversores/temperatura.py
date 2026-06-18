def celsius_a_fahrenheit(celsius):
    if not isinstance(celsius, (int, float)):
        raise TypeError("La temperatura debe ser un número")
    return celsius * 9 / 5 + 32


def fahrenheit_a_celsius(fahrenheit):
    if not isinstance(fahrenheit, (int, float)):
        raise TypeError("La temperatura debe ser un número")
    return (fahrenheit - 32) * 5 / 9


def celsius_a_kelvin(celsius):
    if not isinstance(celsius, (int, float)):
        raise TypeError("La temperatura debe ser un número")
    if celsius < -273.15:
        raise ValueError("La temperatura no puede ser menor al cero absoluto")
    return celsius + 273.15
