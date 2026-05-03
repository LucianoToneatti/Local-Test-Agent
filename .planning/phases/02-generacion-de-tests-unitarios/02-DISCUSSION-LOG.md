# Phase 2: Generación de Tests Unitarios - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 2-Generación de Tests Unitarios
**Areas discussed:** Granularidad del LLM, Clases y métodos, Validación del output, conftest.py

---

## Granularidad del LLM

| Option | Description | Selected |
|--------|-------------|----------|
| Función por función | N llamadas al LLM, una por función. Compatible con PromptBuilder actual. | ✓ |
| Archivo completo | 1 llamada por archivo/fragmento. Requiere refactorizar PromptBuilder. | |

**User's choice:** Función por función
**Notes:** Reutilizar el PromptBuilder existente sin cambios de interfaz. Para obtener el source code de cada función, releer el archivo y slicear por `_lineno`.._end_lineno` (no modificar ast_extractor.py).

---

## Obtención del código fuente de funciones

| Option | Description | Selected |
|--------|-------------|----------|
| Releer archivo + slicear por lineno | Sin cambios al ast_extractor. | ✓ |
| Agregar 'source' al ast_extractor | Requiere modificar HU-04. | |

**User's choice:** Releer archivo + slicear
**Notes:** Snippet confirmado: `'\n'.join(lines[func['_lineno']-1:func['_end_lineno']])`

---

## Clases y métodos

| Option | Description | Selected |
|--------|-------------|----------|
| Solo funciones top-level | Más simple. Ignora clases en esta fase. | |
| Funciones + métodos de clases | Completo desde el inicio. | ✓ |

**User's choice:** Funciones + métodos de clases
**Notes:** Incluir `entry['classes'][*]['methods']` además de `entry['functions']`.

---

## Adaptación del prompt para métodos de clases

| Option | Description | Selected |
|--------|-------------|----------|
| Nuevo template PythonClassMethodPrompt | Más limpio y extensible. | |
| Param extra `class_name` en template existente | Mínimo cambio al código existente. | ✓ |

**User's choice:** Parámetro `class_name` opcional en `PythonPromptTemplate`
**Notes:** Si `class_name` presente → import dice `from module import ClassName`.

---

## Validación del output

| Option | Description | Selected |
|--------|-------------|----------|
| Guardar igual, el runner lo detecta | Más simple. No repite llamadas al LLM. | |
| Validar con ast.parse(), omitir si falla | Sin reintentos. | |
| Validar y reintentar | Balance entre calidad y simplicidad. | ✓ |

**User's choice:** Validar con `ast.parse()` y reintentar
**Notes:** 1 reintento máximo. Si el segundo intento también falla → escribe comentario de error y continúa.

---

## conftest.py

| Option | Description | Selected |
|--------|-------------|----------|
| Dinámico con ruta absoluta del repo | Se regenera en cada ejecución. | ✓ |
| Estático con ruta relativa | Más portable pero puede fallar desde otros directorios. | |

**User's choice:** Dinámico con ruta absoluta
**Notes:** `sys.path.insert(0, '/ruta/absoluta/al/repo/analizado')`

---

| Option (conftest scope) | Description | Selected |
|-------------------------|-------------|----------|
| Uno global en tests_generados/unit/ | Simple, suficiente para v1. | ✓ |
| Uno por subdirectorio de repo | Más limpio para multi-repo. | |

**User's choice:** Uno global en tests_generados/unit/
**Notes:** Si se analizan múltiples repos en secuencia, el último sobrescribe (aceptable para v1).

---

## Claude's Discretion

- Nombre de la función pública en `test_generator.py` (sugerido: `generate(repo_path, ast_result)`)
- Orden de funciones/métodos en el archivo de tests
- Separadores entre bloques de tests por función

## Deferred Ideas

- Multi-repo con conftest.py por subdirectorio → v2
- Template separado `PythonClassMethodPrompt` → v2
- Más de 1 reintento para syntax errors → v2 (QUAL-03)
