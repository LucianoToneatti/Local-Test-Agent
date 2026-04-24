from calculadora import sumar
import pytest

def test_sumar_happy_path():
    assert sumar(2, 3) == 5
    
def test_sumar_negative_numbers():
    assert sumar(-1, -2) == -3

def test_sumar_zero():
    assert sumar(0, 0) == 0
    
def test_sumar_large_numbers():
    assert sumar(10**8, 10**9) == 10**8 + 10**9

from calculadora import restar
import pytest

def test_restar_happy():
    assert restar(5, 3) == 2

def test_restar_negative():
    assert restar(-10, -7) == -3

def test_restar_zero():
    assert restar(7, 7) == 0

from calculadora import multiplicar

def test_multiplicar_with_positive_numbers():
    assert multiplicar(2, 3) == 6
    assert multiplicar(5, 4) == 20

def test_multiplicar_with_negative_numbers():
    assert multiplicar(-1, -2) == 2
    assert multiplicar(-3, -7) == 21

def test_multiplicar_with_zero():
    assert multiplicar(5, 0) == 0
    assert multiplicar(0, 4) == 0

from calculadora import dividir
import pytest

def test_dividir_por_cero():
    with pytest.raises(ValueError) as e:
        dividir(1, 0)
    assert str(e.value) == "El divisor no puede ser cero."

def test_dividir_entre_siempre():
    resultado = dividir(10, 2)
    assert resultado == 5

from calculadora import potencia
import pytest

def test_potencia_basePositivaExponenteCero():
    assert potencia(2,0) == 1
    
def test_potencia_basePositivaExponenteUno():
    assert potencia(2,1) == 2
    
def test_potencia_basePositivaExponenteMayorQueUno():
    assert potencia(2,3) == 8
    
def test_potencia_baseCeroExponentePositivo():
    assert potencia(0,5) == 0
    
def test_potencia_baseNegativaExponentePar():
    assert potencia(-2,2) == 4
    
def test_potencia_baseNegativaExponenteImpar():
    assert potencia(-2,3) == -8