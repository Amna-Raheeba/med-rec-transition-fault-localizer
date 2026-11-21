"""The headline experiment.

Seeded patient journeys are generated with planted discrepancies
at known transitions. The localizer is scored on the discrepancies
that survive to discharge:

- birth-transition accuracy, overall and per discrepancy type,
  against the blame-the-last-transition baseline;
- the same accuracy with the transfer list missing, pricing the
  lost snapshot;
- detection precision/recall against end-to-end home-vs-discharge
  diffing, which cannot see resurrections and flags intentional
  changes as errors;
- intervention pricing: survivors and exposure steps when a
  double-check (efficacy 0.8) is placed at admission, transfer,
  discharge, or nowhere.
"""

import csv
import json
import os

from .generate import generate_journeys
from .intervene import price_interventions
from .localize import (
    blame_last_transition,
    end_to_end_diff,
    ground_truth_instances,
    localize,
)
from .models import FAULT_TYPES

DEFAULT_CONFIG = {
    "seed": 20261121,
    "n_patients": 120,
    "check_efficacy": 0.8,
}

DRIFT_KEYS = [
    "localization.localizer_full.accuracy",
    "localization.localizer_missing_transfer.accuracy",
    "localization.blame_last_transition.accuracy",
    "detection.localizer.f1",
    "detection.end_to_end.f1",
    "corpus.instances_surviving",
    "interventions.no_check.mean_survivors_per_journey",
    "interventions.check_at_discharge.mean_survivors_per_journey",
    "interventions.check_at_admission.mean_exposure_steps_per_journey",
]

DRIFT_TOLERANCE = 1e-6


def _round(value, digits=4):
    if isinstance(value, float):
        return round(value, digits)
    return value


def _surviving(instances):
    return [i for i in instances if i["survives"]]


def _keyed(instances, patient_id):
    return dict(
        ((patient_id, i["drug"], i["fault_type"]), i)
        for i in _surviving(instances)
    )


def score_localization(truth_by_key, found_by_key):
    """Birth accuracy over ground-truth surviving instances
    (unmatched instances count as wrong), plus per-type detail."""
    matched = set(truth_by_key) & set(found_by_key)
    correct = sum(
        1
        for key in matched
        if truth_by_key[key]["birth"] == found_by_key[key]["birth"]
    )
    per_type = {}
    for fault_type in FAULT_TYPES:
        truth_t = dict(
            (k, v) for k, v in truth_by_key.items() if v["fault_type"] == fault_type
        )
        if not truth_t:
            continue
        correct_t = sum(
            1
            for key in set(truth_t) & set(found_by_key)
            if truth_t[key]["birth"] == found_by_key[key]["birth"]
        )
        per_type[fault_type] = {
            "n": len(truth_t),
            "birth_correct": correct_t,
            "accuracy": _round(correct_t / len(truth_t)),
        }
    n = len(truth_by_key)
    return {
        "n_truth": n,
        "n_found": len(found_by_key),
        "matched": len(matched),
        "birth_correct": correct,
        "accuracy": _round(correct / n) if n else 1.0,
        "accuracy_matched_only": (
            _round(correct / len(matched)) if matched else 0.0
        ),
        "per_type": per_type,
    }


def score_detection(truth_by_key, found_by_key):
    tp = len(set(truth_by_key) & set(found_by_key))
    precision = tp / len(found_by_key) if found_by_key else 0.0
    recall = tp / len(truth_by_key) if truth_by_key else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return {
        "tp": tp,
        "fp": len(found_by_key) - tp,
        "fn": len(truth_by_key) - tp,
        "precision": _round(precision),
        "recall": _round(recall),
        "f1": _round(f1),
    }


def evaluate_journeys(journeys):
    """Localization and detection scores pooled over journeys."""
    truth = {}
    found_full = {}
    found_missing = {}
    found_blame = {}
    found_e2e = {}
    for journey in journeys:
        pid = journey.patient_id
        truth.update(_keyed(ground_truth_instances(journey), pid))
        found_full.update(_keyed(localize(journey), pid))
        found_missing.update(_keyed(localize(journey, drop_steps=(2,)), pid))
        found_blame.update(_keyed(blame_last_transition(journey), pid))
        found_e2e.update(_keyed(end_to_end_diff(journey), pid))
    return {
        "localization": {
            "localizer_full": score_localization(truth, found_full),
            "localizer_missing_transfer": score_localization(
                truth, found_missing
            ),
            "blame_last_transition": score_localization(truth, found_blame),
        },
        "detection": {
            "localizer": score_detection(truth, found_full),
            "end_to_end": score_detection(truth, found_e2e),
        },
    }


def corpus_stats(journeys):
    injected = sum(len(j.faults) for j in journeys)
    appeared = 0
    surviving = 0
    by_type = dict((t, 0) for t in FAULT_TYPES)
    for journey in journeys:
        for inst in ground_truth_instances(journey):
            if inst["present_steps"]:
                appeared += 1
            if inst["survives"]:
                surviving += 1
                by_type[inst["fault_type"]] += 1
    n = max(1, len(journeys))
    return {
        "n_journeys": len(journeys),
        "faults_injected": injected,
        "instances_appeared": appeared,
        "instances_surviving": surviving,
        "mean_surviving_per_journey": _round(surviving / n),
        "surviving_by_type": by_type,
    }


def run_evaluation(config=None):
    config = dict(DEFAULT_CONFIG, **(config or {}))
    journeys = generate_journeys(config["n_patients"], config["seed"])
    scores = evaluate_journeys(journeys)
    results = {
        "config": config,
        "corpus": corpus_stats(journeys),
        "localization": scores["localization"],
        "detection": scores["detection"],
        "interventions": price_interventions(
            journeys, config["check_efficacy"], config["seed"]
        ),
    }
    return results


def _flatten(results):
    return {
        "localization.localizer_full.accuracy": results["localization"][
            "localizer_full"
        ]["accuracy"],
        "localization.localizer_missing_transfer.accuracy": results[
            "localization"
        ]["localizer_missing_transfer"]["accuracy"],
        "localization.blame_last_transition.accuracy": results["localization"][
            "blame_last_transition"
        ]["accuracy"],
        "detection.localizer.f1": results["detection"]["localizer"]["f1"],
        "detection.end_to_end.f1": results["detection"]["end_to_end"]["f1"],
        "corpus.instances_surviving": results["corpus"]["instances_surviving"],
        "interventions.no_check.mean_survivors_per_journey": results[
            "interventions"
        ]["no_check"]["mean_survivors_per_journey"],
        "interventions.check_at_discharge.mean_survivors_per_journey": results[
            "interventions"
        ]["check_at_discharge"]["mean_survivors_per_journey"],
        "interventions.check_at_admission.mean_exposure_steps_per_journey": results[
            "interventions"
        ]["check_at_admission"]["mean_exposure_steps_per_journey"],
    }


def check_drift(stored, fresh):
    """Compare stored vs fresh headline aggregates; (ok, problems)."""
    stored_flat = _flatten(stored)
    fresh_flat = _flatten(fresh)
    problems = []
    for key in DRIFT_KEYS:
        sv = stored_flat.get(key)
        fv = fresh_flat.get(key)
        if sv is None or fv is None:
            if sv != fv:
                problems.append((key, sv, fv, None))
            continue
        diff = abs(sv - fv)
        if diff > DRIFT_TOLERANCE:
            problems.append((key, sv, fv, diff))
    return (len(problems) == 0, problems)


def save_results(results, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "evaluation.json"), "w") as handle:
        json.dump(results, handle, indent=2, sort_keys=True)
    with open(os.path.join(out_dir, "evaluation.csv"), "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["key", "value"])
        for key, value in sorted(_flatten(results).items()):
            writer.writerow([key, value])
        for method, scores in sorted(results["localization"].items()):
            writer.writerow(
                ["localization.%s.accuracy" % method, scores["accuracy"]]
            )
        for name, det in sorted(results["detection"].items()):
            writer.writerow(["detection.%s.f1" % name, det["f1"]])
            writer.writerow(["detection.%s.precision" % name, det["precision"]])
            writer.writerow(["detection.%s.recall" % name, det["recall"]])
    with open(os.path.join(out_dir, "evaluation_summary.md"), "w") as handle:
        handle.write(render_summary(results))
    with open(os.path.join(out_dir, "HEADLINE.md"), "w") as handle:
        handle.write(render_headline(results))


def render_summary(results):
    corpus = results["corpus"]
    loc = results["localization"]
    det = results["detection"]
    lines = []
    lines.append("# Evaluation summary")
    lines.append("")
    lines.append(
        "Seed %d, %d seeded patient journeys."
        % (results["config"]["seed"], results["config"]["n_patients"])
    )
    lines.append("")
    lines.append("## Corpus")
    lines.append("")
    lines.append(
        "- Faults injected: %d; instances appearing in the chart: %d; "
        "surviving to discharge: %d (%.2f per journey)"
        % (
            corpus["faults_injected"],
            corpus["instances_appeared"],
            corpus["instances_surviving"],
            corpus["mean_surviving_per_journey"],
        )
    )
    lines.append(
        "- Surviving by type: "
        + ", ".join(
            "%s %d" % (t, corpus["surviving_by_type"][t])
            for t in sorted(corpus["surviving_by_type"])
        )
    )
    lines.append("")
    lines.append("## Birth-transition localisation accuracy")
    lines.append("")
    for method in (
        "localizer_full",
        "localizer_missing_transfer",
        "blame_last_transition",
    ):
        s = loc[method]
        lines.append(
            "- %s: %.3f (%d/%d correct, %d matched)"
            % (method, s["accuracy"], s["birth_correct"], s["n_truth"], s["matched"])
        )
    lines.append("")
    lines.append("## Per-type accuracy (localizer, full lists)")
    lines.append("")
    for fault_type in sorted(loc["localizer_full"]["per_type"]):
        s = loc["localizer_full"]["per_type"][fault_type]
        lines.append(
            "- %s: %.3f (n=%d)" % (fault_type, s["accuracy"], s["n"])
        )
    lines.append("")
    lines.append("## Detection at discharge (surviving discrepancies)")
    lines.append("")
    for name in sorted(det):
        s = det[name]
        lines.append(
            "- %s: P %.3f / R %.3f / F1 %.3f"
            % (name, s["precision"], s["recall"], s["f1"])
        )
    lines.append("")
    lines.append(
        "## Intervention pricing (double-check efficacy %.2f)"
        % results["config"]["check_efficacy"]
    )
    lines.append("")
    for name in (
        "no_check",
        "check_at_admission",
        "check_at_transfer",
        "check_at_discharge",
    ):
        s = results["interventions"][name]
        lines.append(
            "- %s: %.2f survivors/journey, %.2f exposure steps/journey"
            % (
                name,
                s["mean_survivors_per_journey"],
                s["mean_exposure_steps_per_journey"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_headline(results):
    corpus = results["corpus"]
    loc = results["localization"]
    det = results["detection"]
    inv = results["interventions"]
    lines = []
    lines.append("# Headline results")
    lines.append("")
    lines.append(
        "Discrepancy genealogy for medication reconciliation, measured "
        "on %d seeded synthetic patient journeys (seed %d; reproduce "
        "with `python scripts/reproduce_results.py`)."
        % (results["config"]["n_patients"], results["config"]["seed"])
    )
    lines.append("")
    lines.append(
        "- Of %d planted discrepancies, **%d survive to the discharge "
        "list** (%.2f per journey) -- those are the errors the patient "
        "takes home."
        % (
            corpus["faults_injected"],
            corpus["instances_surviving"],
            corpus["mean_surviving_per_journey"],
        )
    )
    lines.append(
        "- The localizer names the birth transition of a surviving "
        "discrepancy with accuracy **%.3f**, vs **%.3f** for blaming "
        "the last transition. With the transfer list missing, "
        "accuracy falls to **%.3f** -- the price of one lost "
        "snapshot."
        % (
            loc["localizer_full"]["accuracy"],
            loc["blame_last_transition"]["accuracy"],
            loc["localizer_missing_transfer"]["accuracy"],
        )
    )
    lines.append(
        "- Detection at discharge: localizer F1 **%.3f** vs end-to-end "
        "home-vs-discharge diffing F1 **%.3f** -- the end-to-end diff "
        "cannot see resurrections at all and flags intentional, "
        "documented changes as errors."
        % (det["localizer"]["f1"], det["end_to_end"]["f1"])
    )
    lines.append(
        "- A double-check (efficacy %.2f) at discharge leaves the "
        "fewest errors in the discharge list (**%.2f** survivors per "
        "journey vs %.2f unchecked) but the most chart exposure; a "
        "check at admission cuts exposure to **%.2f** steps per "
        "journey (vs %.2f unchecked) while missing everything born "
        "later."
        % (
            results["config"]["check_efficacy"],
            inv["check_at_discharge"]["mean_survivors_per_journey"],
            inv["no_check"]["mean_survivors_per_journey"],
            inv["check_at_admission"]["mean_exposure_steps_per_journey"],
            inv["no_check"]["mean_exposure_steps_per_journey"],
        )
    )
    lines.append("")
    lines.append(
        "Caveat: all journeys are synthetic and seeded. Fault rates, "
        "correction rates and check efficacy are declared parameters, "
        "not measurements of any real ward; the benchmark measures "
        "localisation and pricing machinery against known ground "
        "truth that observational reconciliation studies do not have."
    )
    lines.append("")
    return "\n".join(lines)
