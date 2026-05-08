import importlib.util
import pathlib
import sys
from unittest.mock import MagicMock, patch

import pytest

# Load agent.py by path to avoid conflict with agent/ package
# `import agent` resolves to agent/__init__.py, NOT agent.py
_AGENT_PATH = pathlib.Path(__file__).parent.parent / "agent.py"
_spec = importlib.util.spec_from_file_location("agent_main", _AGENT_PATH)
_agent_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_agent_module)
# Register in sys.modules so that patch("agent_main.*") can resolve it
sys.modules["agent_main"] = _agent_module
main = _agent_module.main


def _make_mocks(tmp_path):
    """Context managers to isolate main() from external dependencies.

    Patch paths use "agent_main.*" because agent.py was loaded with
    spec_from_file_location("agent_main", ...). patch() must target the
    module name where the symbol was imported — here "agent_main".
    """
    llm_mock = MagicMock()
    llm_mock.return_value.is_available.return_value = True
    return {
        "llm": patch("agent_main.LLMClient", llm_mock),
        "explore": patch("agent_main.explore", return_value=[]),
        "extract": patch("agent_main.extract", return_value={}),
        "generate_unit": patch("agent_main.generate_unit"),
        "generate_integration": patch("agent_main.generate_integration"),
        "run_tests": patch("agent_main.run_tests", return_value={}),
        "report_generate": patch("agent_main.report_generator"),
    }


def test_main_calls_report_generator(tmp_path):
    mocks = _make_mocks(tmp_path)
    with mocks["llm"], mocks["explore"], mocks["extract"], \
         mocks["generate_unit"], mocks["generate_integration"], \
         mocks["run_tests"], mocks["report_generate"] as mock_rg:
        sys.argv = ["agent.py", "--repo", str(tmp_path)]
        main()
        mock_rg.generate.assert_called_once()


def test_main_measures_elapsed_time(tmp_path):
    mocks = _make_mocks(tmp_path)
    with mocks["llm"], mocks["explore"], mocks["extract"], \
         mocks["generate_unit"], mocks["generate_integration"], \
         mocks["run_tests"], mocks["report_generate"]:
        with patch("agent_main.time") as mock_time:
            mock_time.time.side_effect = [0.0, 10.0]
            sys.argv = ["agent.py", "--repo", str(tmp_path)]
            main()
            assert mock_time.time.call_count >= 2


def test_main_exits_on_invalid_repo(tmp_path):
    sys.argv = ["agent.py", "--repo", str(tmp_path / "no_existe")]
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


def test_main_no_process_file_function():
    assert not hasattr(_agent_module, "process_file")


def test_main_no_extract_functions_function():
    assert not hasattr(_agent_module, "extract_functions")


def test_main_report_called_with_repo_name(tmp_path):
    mocks = _make_mocks(tmp_path)
    with mocks["llm"], mocks["explore"], mocks["extract"], \
         mocks["generate_unit"], mocks["generate_integration"], \
         mocks["run_tests"], mocks["report_generate"] as mock_rg:
        sys.argv = ["agent.py", "--repo", str(tmp_path)]
        main()
        call_args = mock_rg.generate.call_args
        assert call_args[0][1] == tmp_path.name


def test_main_report_called_with_elapsed_float(tmp_path):
    mocks = _make_mocks(tmp_path)
    with mocks["llm"], mocks["explore"], mocks["extract"], \
         mocks["generate_unit"], mocks["generate_integration"], \
         mocks["run_tests"], mocks["report_generate"] as mock_rg:
        sys.argv = ["agent.py", "--repo", str(tmp_path)]
        main()
        call_args = mock_rg.generate.call_args
        assert isinstance(call_args[0][2], float)
