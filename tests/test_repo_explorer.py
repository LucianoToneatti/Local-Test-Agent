import pytest
from agent.repo_explorer import explore


def test_explore_returns_relative_paths(tmp_path):
    (tmp_path / "mod.py").write_text("x = 1")
    result = explore(str(tmp_path))
    assert all(not p.startswith("/") for p in result)


def test_explore_finds_py_files(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "module.py").write_text("pass")
    result = explore(str(tmp_path))
    assert "sub/module.py" in result


def test_explore_ignores_pycache(tmp_path):
    pycache = tmp_path / "__pycache__"
    pycache.mkdir()
    (pycache / "cached.py").write_text("pass")
    result = explore(str(tmp_path))
    assert not any("__pycache__" in p for p in result)


def test_explore_ignores_git(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "hook.py").write_text("pass")
    result = explore(str(tmp_path))
    assert not any(".git" in p for p in result)


def test_explore_ignores_venv(tmp_path):
    venv = tmp_path / "venv"
    venv_lib = venv / "lib"
    venv_lib.mkdir(parents=True)
    (venv_lib / "site.py").write_text("pass")
    result = explore(str(tmp_path))
    assert not any("venv" in p for p in result)


def test_explore_result_is_sorted(tmp_path):
    (tmp_path / "z_module.py").write_text("pass")
    (tmp_path / "a_module.py").write_text("pass")
    (tmp_path / "m_module.py").write_text("pass")
    result = explore(str(tmp_path))
    assert result == sorted(result)


def test_explore_only_py_files(tmp_path):
    (tmp_path / "module.py").write_text("pass")
    (tmp_path / "readme.txt").write_text("text")
    (tmp_path / "notes.md").write_text("# notes")
    result = explore(str(tmp_path))
    assert all(p.endswith(".py") for p in result)
    assert len(result) == 1


def test_explore_empty_repo(tmp_path):
    result = explore(str(tmp_path))
    assert result == []


def test_explore_invalid_path_raises(tmp_path):
    with pytest.raises(NotADirectoryError):
        explore(str(tmp_path / "no_existe"))


def test_explore_nested_directories(tmp_path):
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    (deep / "deep_module.py").write_text("pass")
    result = explore(str(tmp_path))
    assert "a/b/c/deep_module.py" in result
