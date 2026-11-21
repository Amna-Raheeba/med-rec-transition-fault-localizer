import importlib.util
import os


def _load_reproduce():
    path = os.path.join(
        os.path.dirname(__file__), "..", "scripts", "reproduce_results.py"
    )
    spec = importlib.util.spec_from_file_location("reproduce_results", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reproduce_script_passes(capsys):
    module = _load_reproduce()
    assert module.main() == 0
    out = capsys.readouterr().out
    assert "PASS" in out


def test_stored_results_file_exists_and_matches_schema():
    import json

    path = os.path.join(
        os.path.dirname(__file__), "..", "results", "evaluation.json"
    )
    with open(os.path.normpath(path)) as handle:
        stored = json.load(handle)
    assert stored["config"]["seed"] == 20261121
    assert "localizer_full" in stored["localization"]
    assert "check_at_discharge" in stored["interventions"]
