import json
import os

from med_rec.evaluate import (
    check_drift,
    render_headline,
    render_summary,
    run_evaluation,
    save_results,
    score_detection,
    score_localization,
)


def test_run_evaluation_reduced_keys():
    results = run_evaluation({"n_patients": 10})
    for key in ("config", "corpus", "localization", "detection", "interventions"):
        assert key in results
    assert results["config"]["n_patients"] == 10


def test_corpus_stats_consistent():
    results = run_evaluation({"n_patients": 10})
    corpus = results["corpus"]
    assert corpus["instances_surviving"] <= corpus["instances_appeared"]
    assert corpus["instances_appeared"] <= corpus["faults_injected"]
    total_by_type = sum(corpus["surviving_by_type"].values())
    assert total_by_type == corpus["instances_surviving"]


def test_check_drift_identical_passes():
    results = run_evaluation({"n_patients": 10})
    ok, problems = check_drift(results, results)
    assert ok
    assert problems == []


def test_check_drift_tampered_fails():
    results = run_evaluation({"n_patients": 10})
    tampered = json.loads(json.dumps(results))
    tampered["localization"]["localizer_full"]["accuracy"] = 0.5
    ok, problems = check_drift(results, tampered)
    assert not ok
    assert any(p[0] == "localization.localizer_full.accuracy" for p in problems)


def test_save_results_writes_four_files(tmp_path):
    results = run_evaluation({"n_patients": 5})
    out = str(tmp_path / "results")
    save_results(results, out)
    for name in (
        "evaluation.json",
        "evaluation.csv",
        "evaluation_summary.md",
        "HEADLINE.md",
    ):
        assert os.path.exists(os.path.join(out, name))
    with open(os.path.join(out, "evaluation.json")) as handle:
        stored = json.load(handle)
    assert stored["config"]["seed"] == 20261121


def test_score_localization_math():
    truth = {
        (0, "a", "omission"): {"birth": 1, "fault_type": "omission"},
        (0, "b", "dose_drift"): {"birth": 2, "fault_type": "dose_drift"},
    }
    found = {
        (0, "a", "omission"): {"birth": 1, "fault_type": "omission"},
        (0, "b", "dose_drift"): {"birth": 3, "fault_type": "dose_drift"},
    }
    scores = score_localization(truth, found)
    assert scores["matched"] == 2
    assert scores["birth_correct"] == 1
    assert scores["accuracy"] == 0.5
    assert scores["per_type"]["omission"]["accuracy"] == 1.0
    assert scores["per_type"]["dose_drift"]["accuracy"] == 0.0


def test_score_detection_math():
    truth = {(0, "a", "omission"): {}, (0, "b", "dose_drift"): {}}
    found = {(0, "a", "omission"): {}, (0, "c", "addition"): {}}
    scores = score_detection(truth, found)
    assert scores["tp"] == 1
    assert scores["fp"] == 1
    assert scores["fn"] == 1
    assert scores["precision"] == 0.5
    assert scores["recall"] == 0.5
    assert scores["f1"] == 0.5


def test_renderers_mention_key_numbers():
    results = run_evaluation({"n_patients": 10})
    summary = render_summary(results)
    assert "Birth-transition localisation accuracy" in summary
    assert "Intervention pricing" in summary
    headline = render_headline(results)
    assert "discharge" in headline
    assert "Caveat" in headline
