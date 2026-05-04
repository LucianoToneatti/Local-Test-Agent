# Phase 3: Generación de Tests de Integración - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-03
**Phase:** 3-Generación de Tests de Integración
**Areas discussed:** Repositorio de ejemplo, Prompt de integración, conftest.py para integration/, Qué valida el test

---

## Repositorio de ejemplo

| Option | Description | Selected |
|--------|-------------|----------|
| Crear examples/estadistica.py | Un archivo pequeño (5-6 funciones) que importe de calculadora.py. Se puede usar para validar todos los criterios de éxito de Fase 3 sin salir del repo. | ✓ |
| Crear examples/repo_multi/ | Un subdirectorio con 2-3 archivos .py con imports cruzados. Más representativo de un repo real, pero agrega complejidad al ejemplo. | |
| Usar un repo externo para testear | No se toca examples/. Los criterios de éxito se validan apuntando el agente a un repo Python real del sistema. Más realista pero menos reproducible en tests del agente. | |

**User's choice:** Crear examples/estadistica.py
**Notes:** El archivo debe tener funciones como `promedio()` y `varianza()` que usen internamente funciones de `calculadora.py` (sumar, multiplicar). Relación semánticamente correcta para generar un test de integración real.

---

## Prompt de integración

### Contenido del prompt

| Option | Description | Selected |
|--------|-------------|----------|
| Código completo de ambos | El LLM ve todo el código de A y B. Genera tests más precisos pero el prompt puede ser largo si los archivos son grandes. | |
| Código de A + firmas de B | El LLM ve el módulo que importa (A) completo, y solo los nombres/parámetros de las funciones de B. Más liviano, suficiente para inferir la interacción. | ✓ |
| Solo firmas de ambos | El LLM recibe solo nombres y parámetros de las funciones de cada módulo. Más liviano pero menos contexto para generar tests útiles. | |

**User's choice:** Código de A + firmas de B
**Notes:** Balance entre contexto para el LLM y tamaño del prompt.

### Ubicación del template

| Option | Description | Selected |
|--------|-------------|----------|
| Nuevo IntegrationPromptTemplate en prompt_builder.py | Extiende PromptTemplate, se registra en _REGISTRY. Sigue el mismo patrón que PythonPromptTemplate y queda disponible para otras fases. | ✓ |
| Prompt hardcodeado en integration_generator.py | El template vive dentro del propio módulo, sin tocar prompt_builder.py. Más simple, pero rompe la coherencia del sistema de prompts. | |

**User's choice:** Nuevo IntegrationPromptTemplate en prompt_builder.py

---

## conftest.py para integration/

| Option | Description | Selected |
|--------|-------------|----------|
| Generar conftest.py en integration/ | Mismo patrón que unit/: una sola línea sys.path.insert(0, repo_path). Cada subdirectorio de tests_generados/ es autosuficiente. | ✓ |
| Reutilizar el de unit/ | No se genera conftest en integration/. Frágil si los directorios se usan por separado. | |
| Un conftest.py en tests_generados/ (raíz) | Un solo conftest.py en tests_generados/ que cubre unit/ e integration/ juntos. Requiere tocar lo que ya funciona en unit/. | |

**User's choice:** Generar conftest.py en integration/

---

## Qué valida el test

### Tipo de verificación

| Option | Description | Selected |
|--------|-------------|----------|
| Que A puede llamar B y obtener resultado esperado | El test instancia/llama una función de A que usa internamente B. Verifica la cadena completa: `estadistica.promedio([1,2,3])` devuelve `2.0`. | ✓ |
| Que la importación no falla | Solo verifica que el import no lanza ImportError. Casi no aporta valor sobre los tests unitarios. | |
| Claude decide según el contexto del par | El system prompt le da libertad al LLM para elegir el enfoque más adecuado según el código. | |

**User's choice:** Que A puede llamar B y obtener resultado esperado

### Precisión de los asserts

| Option | Description | Selected |
|--------|-------------|----------|
| Asserts con valores concretos | El prompt dice: 'assert result == valor_esperado'. El LLM infiere valores razonables del código. | ✓ |
| Flexible: tipo o no-excepción | El prompt dice: 'verificá que la función retorna el tipo correcto o no lanza excepción'. Tests más robustos pero menos informativos. | |

**User's choice:** Asserts con valores concretos
**Notes:** Si el LLM elige valores incorrectos, la Fase 4 (autocorrección) los corregirá.

---

## Claude's Discretion

- Nombre del par: `test_<stemA>_<stemB>.py` donde A es el importador
- Si A importa múltiples módulos: un archivo por par (test_A_B.py, test_A_C.py)
- Función pública principal: `generate(repo_path, ast_result)` — misma firma que test_generator

## Deferred Ideas

- Pares bidireccionales (A importa B y B importa A) → v2 puede deduplicar
- Triplas de dependencias (A → B → C): v1 genera solo pares directos
- Template por tipo de interacción (clase vs. función libre) → v2
