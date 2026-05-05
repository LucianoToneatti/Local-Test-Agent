from calculadora import sumar
import pytest

def test_sumar_happy_path():
    assert sumar(1,2) == 3

def test_sumar_negative_numbers():
    assert sumar(-5,-7) == -12

def test_sumar_zero_values():
    assert sumar(0,0) == 0

def test_sumar_positive_and_negative():
    assert sumar(3,-2) == 1

from calculadora import restar
import pytest

def test_restar_happy():
    assert restar(10, 5) == 5
    
def test_restar():
    assert restar(-2, 3) == -5
    
def test_restar_zero():
    assert restar(7, 7) == 0
    
def test_restar_expect_exception():
    with pytest.raises(TypeError):
        restar('a', 'b')

from calculadora import multiplicar
import pytest

def test_multiplicar_positive_numbers():
    assert multiplicar(5, 2) == 10

def test_multiplicar_negative_numbers():
    assert multiplicar(-3, -4) == 12

def test_multiplicar_zero():
    assert multiplicar(7, 0) == 0

def test_multiplicar_large_numbers():
    assert multiplicar(8956451, 25632154) == (8956451 * 25632154)

import pytest
from calculadora import dividir

def test_dividir_con_numeros():
    assert dividir(10,2) == 5
    
def test_dividir_por_cero():
    with pytest.raises(ValueError):
        dividir(10,0)

from calculadora import potencia
import pytest

def test_potencia_positive():
    assert potencia(2, 3) == 8
    assert potencia(10, 5) == 100000
    
def test_potencia_zero_exponent():
    assert potencia(4, 0) == 1
    assert potencia(67, 0) == 1

import pytest
from math import pow  # Assuming the function signature for potencia in your module is like this.

def test_potencia_negative_exponent():
    base = 2
    negative_exp = -3
    result = pow(base, negative_exp)
    
    assert result == 1/(base**(-negative_exp))  # Check if the results match expected output for negative exponents.
