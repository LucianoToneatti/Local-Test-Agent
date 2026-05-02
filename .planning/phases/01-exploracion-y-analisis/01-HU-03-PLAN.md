---
phase: 1
plan: HU-03
type: execute
wave: 1
depends_on: []
files_modified:
  - agent/repo_explorer.py
  - tests/test_repo_explorer.py
  - context/marco_teorico_notas.md
autonomous: true
requirements:
  - EXPL-01
  - EXPL-02
---

<objective>
Implementar `agent/repo_explorer.py` con la función `explore(repo_path)` que recorre recursivamente un
directorio Python y devuelve una lista de rutas relativas a todos los archivos `.py`, ignorando
`__pycache__`, `.git`, `venv`, `dist` y otros directorios del sistema. Este módulo es puramente filesystem:
no lee el contenido de los archivos. Su output es el contrato de entrada para `ast_extractor.py` (HU-04).
</objective>

<tasks>

<task id="1">
  <title>Crear agent/repo_explorer.py</title>
  <read_first>
    - agent/llm_client.py (patrón de módulo: docstring, constantes, clase/función pública, sin deps externas)
    - CLAUDE.md (convenciones del stack: stdlib solo, pathlib, typing)
    - examples/calculadora.py (archivo de referencia para validación manual)
  </read_first>
  <action>
    Crear `agent/repo_explorer.py` con el siguiente contenido:

    ```python
    """
    Explorador de repositorios Python.

    Recorre recursivamente un directorio y devuelve la lista de rutas relativas
    de todos los archivos .py, ignorando directorios del sistema.
    """

    import os
    from pathlib import Path

    IGNORED_DIRS = {'__pycache__', '.git', 'venv', '.venv', 'dist', 'node_modules', '.tox', 'build', 'egg-info'}


    def explore(repo_path: str) -> list[str]:
        """
        Lista recursivamente todos los archivos .py de un repositorio.

        Args:
            repo_path: Ruta al directorio raíz del repositorio.

        Returns:
            Lista ordenada de rutas relativas al repo_path para cada archivo .py
            encontrado, ignorando directorios en IGNORED_DIRS y sus subdirectorios.

        Raises:
            NotADirectoryError: Si repo_path no es un directorio existente.
        """
        root = Path(repo_path).resolve()
        if not root.is_dir():
            raise NotADirectoryError(f"No es un directorio: {repo_path}")

        result = []
        for dirpath, dirnames, filenames in os.walk(root):
            # Modificar dirnames in-place para que os.walk no descienda a los dirs ignorados
            dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS)
            for filename in filenames:
                if filename.endswith('.py'):
                    abs_path = Path(dirpath) / filename
                    rel_path = abs_path.relative_to(root)
                    result.append(str(rel_path))

        return sorted(result)
    ```

    Notas de implementación:
    - Usar `dirnames[:] = [...]` (in-place) para que `os.walk` no descienda a dirs ignorados.
    - Rutas relativas con `pathlib.Path.relative_to(root)` — no con string manipulation.
    - Ordenar el resultado y también los dirnames para que el orden sea determinístico.
    - Sin dependencias externas: solo `os` y `pathlib`.
  </action>
  <acceptance_criteria>
    - `grep -n "def explore" agent/repo_explorer.py` encuentra la función
    - `grep -n "IGNORED_DIRS" agent/repo_explorer.py` encuentra la constante con al menos `__pycache__`, `.git`, `venv`
    - `python3 -c "from agent.repo_explorer import explore; r = explore('examples'); assert 'calculadora.py' in r or 'examples/calculadora.py' in r, r"` exits 0
    - `python3 -c "from agent.repo_explorer import explore; r = explore('.'); assert not any('__pycache__' in p for p in r), r"` exits 0
    - `python3 -c "from agent.repo_explorer import explore; r = explore('.'); assert all(p.endswith('.py') for p in r), r"` exits 0
    - `python3 -c "from agent.repo_explorer import explore; r = explore('.'); assert r == sorted(r), 'resultado no ordenado'"` exits 0
    - `python3 -c "from agent.repo_explorer import explore; r = explore('no_existe')"` lanza `NotADirectoryError`
  </acceptance_criteria>
</task>

<task id="2">
  <title>Crear tests/test_repo_explorer.py</title>
  <read_first>
    - agent/repo_explorer.py (funciones a testear)
    - agent/llm_client.py (referencia del patrón de estructura de módulo)
  </read_first>
  <action>
    Crear `tests/test_repo_explorer.py` con los siguientes tests pytest. Usar `tmp_path` (fixture
    nativa de pytest) para crear repos temporales sin tocar el sistema de archivos real.

    Tests requeridos:
    1. `test_explore_returns_relative_paths` — verifica que las rutas son relativas (no empiezan con `/`)
    2. `test_explore_finds_py_files` — verifica que encuentra archivos .py en subdirectorios
    3. `test_explore_ignores_pycache` — crea `__pycache__/cached.py`, verifica que no aparece
    4. `test_explore_ignores_git` — crea `.git/hook.py`, verifica que no aparece
    5. `test_explore_ignores_venv` — crea `venv/lib/site.py`, verifica que no aparece
    6. `test_explore_result_is_sorted` — verifica que `result == sorted(result)`
    7. `test_explore_only_py_files` — crea mix de .py y .txt, verifica que solo devuelve .py
    8. `test_explore_empty_repo` — directorio sin .py devuelve lista vacía
    9. `test_explore_invalid_path_raises` — path inexistente lanza NotADirectoryError
    10. `test_explore_nested_directories` — archivos en subdirectorios anidados aparecen en resultado

    Estructura de cada test:
    ```python
    def test_explore_returns_relative_paths(tmp_path):
        (tmp_path / "mod.py").write_text("x = 1")
        result = explore(str(tmp_path))
        assert all(not p.startswith("/") for p in result)
    ```
  </action>
  <acceptance_criteria>
    - `python3 -m pytest tests/test_repo_explorer.py -v` exits 0
    - Todos los 10 tests pasan (10 PASSED en el output de pytest)
    - `grep -c "def test_" tests/test_repo_explorer.py` imprime al menos 10
    - `grep "tmp_path" tests/test_repo_explorer.py` confirma uso de fixture nativa (no fixtures manuales)
  </acceptance_criteria>
</task>

<task id="3">
  <title>Actualizar context/marco_teorico_notas.md con HU-03</title>
  <read_first>
    - context/marco_teorico_notas.md (ver formato de secciones HU-01 y HU-02 para replicar)
    - agent/repo_explorer.py (módulo recién implementado)
  </read_first>
  <action>
    Agregar una sección `### HU-03: Explorador de repositorio` al final de
    `context/marco_teorico_notas.md` siguiendo el formato de las secciones anteriores.

    Contenido a agregar:
    ```markdown
    ### HU-03: Explorador de repositorio

    - **Qué se hizo:** se creó `agent/repo_explorer.py` con la función `explore(repo_path)` que
      recorre recursivamente un directorio Python usando `os.walk`, ignora directorios del sistema
      (`__pycache__`, `.git`, `venv`, `dist`, etc.) modificando `dirnames` in-place, y devuelve
      una lista ordenada de rutas relativas a archivos `.py`.

    - **Por qué esta solución:** separación clara de responsabilidades — `repo_explorer.py` es
      puramente filesystem, sin leer contenido de archivos. La modificación in-place de `dirnames`
      en `os.walk` es el mecanismo estándar de Python para podar el árbol de recursión sin necesidad
      de filtrado posterior. Las rutas relativas (no absolutas) son el contrato esperado por
      `ast_extractor.py` y evitan acoplamiento a rutas absolutas del sistema.

    - **Conceptos teóricos que aplican:** `os.walk` con pruning de directorios (modificación
      in-place de `dirnames`), `pathlib.Path.relative_to()` para normalización de rutas,
      principio de responsabilidad única (SRP).

    - **Deuda técnica / pendientes:** soporte para estructura `src/` (v2 QUAL-02), opción para
      incluir/excluir dirs adicionales por parámetro.
    ```
  </action>
  <acceptance_criteria>
    - `grep "HU-03" context/marco_teorico_notas.md` encuentra la sección
    - `grep "os.walk" context/marco_teorico_notas.md` menciona el mecanismo central
    - `grep "dirnames" context/marco_teorico_notas.md` explica la técnica de pruning
  </acceptance_criteria>
</task>

<task id="4">
  <title>Commit HU-03</title>
  <read_first>
    - agent/repo_explorer.py
    - tests/test_repo_explorer.py
    - context/marco_teorico_notas.md
  </read_first>
  <action>
    Verificar que `pytest tests/test_repo_explorer.py` pasa al 100%, luego commitear los tres archivos:
    ```bash
    git add agent/repo_explorer.py tests/test_repo_explorer.py context/marco_teorico_notas.md
    git commit -m "feat: HU-03 - Explorador de repositorio"
    ```
    El mensaje de commit DEBE seguir exactamente el formato `feat: HU-0X - <descripción breve>`
    definido en CLAUDE.md.
  </action>
  <acceptance_criteria>
    - `git log --oneline -1` muestra `feat: HU-03 - Explorador de repositorio`
    - `git show --name-only HEAD` lista los tres archivos modificados
    - `python3 -m pytest tests/test_repo_explorer.py` exits 0 en el estado del commit
  </acceptance_criteria>
</task>

</tasks>

<verification>
Pasos de verificación end-to-end:

```bash
# 1. Verificar módulo importable
python3 -c "from agent.repo_explorer import explore; print('OK')"

# 2. Verificar con repositorio real
python3 -c "
from agent.repo_explorer import explore
result = explore('examples')
print('Archivos encontrados:', result)
assert 'calculadora.py' in result
print('EXPL-01 OK: archivos .py encontrados')
"

# 3. Verificar exclusión de dirs del sistema
python3 -c "
from agent.repo_explorer import explore
result = explore('.')
forbidden = ['__pycache__', '.git', 'venv']
for f in forbidden:
    assert not any(f in p for p in result), f'Encontrado {f} en resultado'
print('EXPL-01 OK: dirs del sistema excluidos')
"

# 4. Verificar rutas relativas
python3 -c "
from agent.repo_explorer import explore
result = explore('.')
assert all(not p.startswith('/') for p in result)
print('EXPL-02 OK: rutas relativas')
"

# 5. Correr tests
python3 -m pytest tests/test_repo_explorer.py -v

# 6. Verificar commit
git log --oneline -3
```
</verification>

<must_haves>
<truths>
  - explore() devuelve rutas relativas al repo_path, nunca absolutas
  - __pycache__, .git, venv y dist nunca aparecen en el resultado
  - El resultado está ordenado (result == sorted(result))
  - Solo archivos .py aparecen en el resultado (no .txt, .md, etc.)
  - Path inexistente lanza NotADirectoryError, no devuelve lista vacía
  - Sin dependencias externas: solo os y pathlib de stdlib
</truths>
</must_haves>

<success_criteria>
1. `python3 -c "from agent.repo_explorer import explore; r = explore('examples'); assert 'calculadora.py' in r"` exits 0
2. `python3 -m pytest tests/test_repo_explorer.py` — 10 tests PASSED, 0 failed
3. `git log --oneline -1` muestra `feat: HU-03 - Explorador de repositorio`
4. `grep "HU-03" context/marco_teorico_notas.md` encuentra la sección
</success_criteria>
