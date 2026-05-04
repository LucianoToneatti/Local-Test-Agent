import pytest
from estadistica import promedio, varianza
from calculadora import sumar, restar, multiplicar, dividir, potencia

def test_promedio():
    assert promedio([1, 2, 3]) == 2.0
    with pytest.raises(ValueError):
        promedio([])

def test_varianza():
    assert varianza([1, 2, 3]) == pytest.approx(0.6666666666666666)
    with pytest.raises(ValueError):
        varianza([])
        
def test_sumar():
    assert sumar(1, 2) == 3
    
def test_restar():
    assert restar(5, 3) == 2

def test_multiplicar():
    assert multiplicar(2, 3) == 6

def test_dividir():
    assert dividir(10, 2) == 5

def test_potencia():
    assert potencia(2, 3) == 8
