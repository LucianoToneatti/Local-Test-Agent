---
plan: HU-03
phase: 1
status: complete
completed: 2026-05-02
---

## Summary

Implementado `agent/repo_explorer.py` con la función pública `explore(repo_path)` que recorre recursivamente un directorio Python y retorna una lista ordenada de rutas relativas a todos los archivos `.py`, ignorando directorios del sistema.

## What was built

**`agent/repo_explorer.py`**
- Función `explore(repo_path: str) -> list[str]`
- Constante `IGNORED_DIRS` con 9 directorios a ignorar: `__pycache__`, `.git`, `venv`, `.venv`, `dist`, `node_modules`, `.tox`, `build`, `egg-info`
- Usa `os.walk` con pruning in-place de `dirnames` para eficiencia
- Rutas relativas via `pathlib.Path.relative_to(root)`
- Lanza `NotADirectoryError` para paths inválidos

**`tests/test_repo_explorer.py`** — 10 tests, 10 PASSED
- `test_explore_returns_relative_paths`
- `test_explore_finds_py_files`
- `test_explore_ignores_pycache`
- `test_explore_ignores_git`
- `test_explore_ignores_venv`
- `test_explore_result_is_sorted`
- `test_explore_only_py_files`
- `test_explore_empty_repo`
- `test_explore_invalid_path_raises`
- `test_explore_nested_directories`

**`context/marco_teorico_notas.md`** — sección HU-03 agregada

## Key files created

- `agent/repo_explorer.py`
- `tests/test_repo_explorer.py`

## Self-Check: PASSED

All 10 tests passed. Commit: `feat: HU-03 - Explorador de repositorio`

Requirements covered: EXPL-01, EXPL-02
