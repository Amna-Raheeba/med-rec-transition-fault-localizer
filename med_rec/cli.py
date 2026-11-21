"""Command line interface: python -m med_rec <command>.

Commands:
- demo: generate the canonical demo journey and print its lists,
  ledger, ground truth and localizer genealogy.
- evaluate: run the full evaluation, print the headline, and
  write the result files into results/.
- audit: score the localizer on a seeded batch of journeys and
  print localisation accuracy and detection scores.
"""

import argparse
import os

from .evaluate import DEFAULT_CONFIG, evaluate_journeys, run_evaluation, save_results
from .generate import demo_journey, generate_journeys
from .report import render_journey_report


def _demo(_args):
    journey = demo_journey(DEFAULT_CONFIG["seed"])
    print(render_journey_report(journey))
    return 0


def _evaluate(_args):
    results = run_evaluation()
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
    save_results(results, os.path.normpath(out_dir))
    loc = results["localization"]
    print(
        "Evaluated %d seeded journeys, %d surviving discrepancies."
        % (
            results["config"]["n_patients"],
            results["corpus"]["instances_surviving"],
        )
    )
    print(
        "Localisation accuracy: full %.3f, missing transfer %.3f, "
        "blame-last %.3f."
        % (
            loc["localizer_full"]["accuracy"],
            loc["localizer_missing_transfer"]["accuracy"],
            loc["blame_last_transition"]["accuracy"],
        )
    )
    return 0


def _audit(args):
    journeys = generate_journeys(args.n, DEFAULT_CONFIG["seed"])
    scores = evaluate_journeys(journeys)
    loc = scores["localization"]
    for method in (
        "localizer_full",
        "localizer_missing_transfer",
        "blame_last_transition",
    ):
        s = loc[method]
        print(
            "%s: accuracy %.3f (%d/%d)"
            % (method, s["accuracy"], s["birth_correct"], s["n_truth"])
        )
    det = scores["detection"]
    for name in sorted(det):
        s = det[name]
        print(
            "detection %s: P %.3f / R %.3f / F1 %.3f"
            % (name, s["precision"], s["recall"], s["f1"])
        )
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="med_rec")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo")
    sub.add_parser("evaluate")
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("--n", type=int, default=20)
    args = parser.parse_args(argv)
    if args.command == "demo":
        return _demo(args)
    if args.command == "evaluate":
        return _evaluate(args)
    return _audit(args)


if __name__ == "__main__":
    raise SystemExit(main())
