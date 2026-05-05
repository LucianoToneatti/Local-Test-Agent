import pytest
from unittest.mock import patch
from estadistica import promedio, varianza
from calculadora import sumar, multiplicar

# Define all imports once at the top of the file

def test_promedio():
    with patch('calculadora.sumar') as mock_sumar:
        # Arrange
        lista = [1, 2, 3]
        mock_sumar.side_effect = sumar
        expected = 2.0
        
        # Act
        result = promedio(lista)
        
        # Assert
        assert result == expected

from unittest.mock import patch
import pytest

def test_varianza():
    with patch('statistics.promedio') as mock_promedio, \
            patch('calculadora.sumar'), \
            patch('calculadora.multiplicar'):
        
        # Arrange
        lista = [1, 2, 3]
        mock_promedio.return_value = 2
        expected = 0.5714285714285714
        
        # Act
        result = varianza(lista)
        
        # Assert
        assert pytest.approx(result, 0.00001) == expected
