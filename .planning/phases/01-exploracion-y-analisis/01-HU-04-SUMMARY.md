---
plan: HU-04
phase: 1
status: complete
completed: 2026-05-02
---

## Summary

Implementado `agent/ast_extractor.py` con la función pública `extract(files, repo_path)` que analiza archivos `.py` con el módulo `ast` de stdlib. Produce un dict unificado `{ruta: {functions, classes, imports}}` por archivo. Incluye fragmentación inteligente (`fragment()`) para archivos >200 líneas sin cortar unidades sintácticas.

## What was built

**`agent/ast_extractor.py`**
- `FRAGMENT_THRESHOLD = 200`
- `extract(files, repo_path)` → dict unificado por archivo
- `fragment(file_info, source_lines)` → lista de fragmentos ≤200 líneas
- `_parse_file()` — con manejo de SyntaxError via `parse_error` key
- `_extract_functions()` — funciones top-level con name, type, params, docstring
- `_extract_classes()` — clases con name, type, docstring, methods[]
- `_extract_repo_imports()` — imports filtrados al mismo repo
- Sin dependencias externas: solo `ast`, `os`, `pathlib`

**`tests/test_ast_extractor.py`** — 13 tests, 13 PASSED
- test_extract_functions_from_calculadora
- test_extract_function_params
- test_extract_function_docstring
- test_extract_class_with_methods
- test_extract_returns_empty_for_empty_file
- test_extract_syntax_error_handled
- test_extract_same_repo_imports
- test_extract_stdlib_imports_excluded
- test_extract_third_party_imports_excluded
- test_fragment_small_file_returns_one_fragment
- test_fragment_large_file_returns_multiple_fragments
- test_fragment_never_splits_single_large_function
- test_fragment_each_fragment_parseable

**`context/marco_teorico_notas.md`** — sección HU-04 agregada

## Roadmap success criteria

- Criterio #1: explore('.') encuentra calculadora.py, excluye __pycache__ ✓
- Criterio #2: extract() retorna dict con 5 funciones de calculadora.py ✓
- Criterio #3: archivo 250 líneas → 2 fragmentos sin error ✓

## Key files created

- `agent/ast_extractor.py`
- `tests/test_ast_extractor.py`

## Self-Check: PASSED

All 13 tests passed. Full suite: 23/23 passed. Commit: `feat: HU-04 - Extractor AST`

Requirements covered: ANLS-01, ANLS-02, ANLS-03, EXPL-03
