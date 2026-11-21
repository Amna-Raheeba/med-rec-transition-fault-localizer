from med_rec.cli import main


def test_cli_demo(capsys):
    assert main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "Ground truth" in out
    assert "Localizer genealogy" in out


def test_cli_audit(capsys):
    assert main(["audit", "--n", "5"]) == 0
    out = capsys.readouterr().out
    assert "localizer_full" in out
    assert "blame_last_transition" in out
    assert "detection end_to_end" in out


def test_cli_evaluate(capsys):
    assert main(["evaluate"]) == 0
    out = capsys.readouterr().out
    assert "Localisation accuracy" in out
