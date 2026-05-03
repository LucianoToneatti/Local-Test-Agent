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
