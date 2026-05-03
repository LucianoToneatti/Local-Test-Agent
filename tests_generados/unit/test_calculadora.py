from calculadora import sumar
import pytest

def test_sumar_happy_path():
    assert sumar(5, 7) == 12

def test_sumar_negative_numbers():
    assert sumar(-3, -4) == -7

def test_sumar_zeroes():
    assert sumar(0, 0) == 0

from calculadora import restar
import pytest

def test_restar_happy_path():
    assert restar(5, 3) == 2

def test_restar_negative_numbers():
    assert restar(-10, -7) == -3

def test_restar_zero():
    assert restar(8, 8) == 0

from calculadora import multiplicar
import pytest

def test_multiplicar_positive():
    assert multiplicar(5, 4) == 20

def test_multiplicar_zero():
    assert multiplicar(7, 0) == 0

def test_multiplicar_negative():
    assert multiplicar(-3, 10) == -30

import pytest
from calculadora import dividir

def test_dividir_con_un_numero():
    assert dividir(10,2) == 5
    
def test_dividir_por_cero():
    with pytest.raises(ValueError):
        dividir(10,0)
        
def test_dividir_dos_numeros_negativos():
    assert dividir(-10,-2) == 5
    
def test_dividir_un_numero_negativo_y_positivo():
    assert dividir(10,-2) == -5

from calculadora import potencia
import pytest

def test_potencia_happy_path():
    assert potencia(2,3) == 8
    
def test_potencia_base_negative():
    assert potencia(-2, 3) == -8
    
def test_potencia_exponente_zero():
    assert potencia(2, 0) == 1
    
def test_potencia_base_zero():
    assert potencia(0, 5) == 0
    
def test_potencia_both_negative():
    with pytest.raises(ZeroDivisionError):
        potencia(-2, -3)
