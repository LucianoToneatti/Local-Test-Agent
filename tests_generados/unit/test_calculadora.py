import pytest
from mymodule import sumar

def test_sumar():
    assert sumar(10, 2) == 12
    
def test_negative_numbers():
    assert sumar(-5, -7) == -12
    
def test_zero_values():
    assert sumar(3, 0) == 3

import pytest

def restar(a, b):
    return a - b

def test_restar():
    assert restar(5,3) == 2
    assert restar(-1,-2) == -1
    assert restar(0, 89) == -89

import pytest
from unittest import mock

def test_multiplicar():
    # Happy path scenario
    assert multiplicar(2, 3) == 6
    
    # Edge case where both numbers are zero
    assert multiplicar(0, 0) == 0
    
    # Checking negative number handling
    assert multiplicar(-1, -1) == 1
    assert multiplicar(5, -2) == -10
    
    # Expected exception
    with pytest.raises(TypeError):
        multiplicar('a', 3)

import pytest
from main import dividir

def test_dividir_cuando_el_divisor_es_cero():
    with pytest.raises(ValueError) as e:
        dividir(10, 0)
    assert str(e.value) == "El divisor no puede ser cero."

def test_dividir_con_valores_positivos():
    resultado = dividir(20, 4)
    assert resultado == 5

def test_dividir_con_valores_negativos():
    resultado = dividir(-10, -2)
    assert resultado == 5

import pytest

def potencia(base, exponente):
    return base ** exponente

# Testing the happy path scenario
def test_potencia():
    assert potencia(2, 3) == 8
    assert potencia(5, 2) == 25
    assert potencia(10, 1) == 10

# Testing a edge case where exponent is zero
def test_potencia_zero_exponent():
    assert potencia(2, 0) == 1
    assert potencia(9, 0) == 1

# Testing for negative exponent
def test_potencia_negative_exponent():
    assert potencia(2, -3) == 1/(2**3)
    assert potencia(5, -2) == 1/25