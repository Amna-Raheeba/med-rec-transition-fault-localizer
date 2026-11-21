"""Notebook 1 (runnable .py): one journey, genealogised.

Generates the canonical demo journey, prints its lists, ledger,
planted ground truth and the localizer's genealogy, and checks
the localizer against the truth for this journey.

Run: python notebooks/01_demo_run.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from med_rec.evaluate import DEFAULT_CONFIG
from med_rec.generate import demo_journey
from med_rec.localize import ground_truth_instances, localize
from med_rec.report import render_journey_report


def main():
    journey = demo_journey(DEFAULT_CONFIG["seed"])
    print(render_journey_report(journey))
    print("")
    truth = dict(
        ((i["drug"], i["fault_type"]), i)
        for i in ground_truth_instances(journey)
        if i["survives"]
    )
    found = dict(
        ((i["drug"], i["fault_type"]), i)
        for i in localize(journey)
        if i["survives"]
    )
    correct = sum(
        1
        for key in set(truth) & set(found)
        if truth[key]["birth"] == found[key]["birth"]
    )
    print(
        "Surviving discrepancies: %d; localizer matched %d, birth "
        "correct %d." % (len(truth), len(set(truth) & set(found)), correct)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
