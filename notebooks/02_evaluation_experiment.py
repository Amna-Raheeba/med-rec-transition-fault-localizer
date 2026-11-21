"""Notebook 2 (runnable .py): the headline experiment, reduced.

Runs the full evaluation pipeline on a reduced patient count so
it finishes quickly in CI, and prints the summary. The canonical
headline numbers in results/ come from the full configuration in
med_rec.evaluate.DEFAULT_CONFIG.

Run: python notebooks/02_evaluation_experiment.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from med_rec.evaluate import render_summary, run_evaluation


def main():
    results = run_evaluation({"n_patients": 25})
    print(render_summary(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
