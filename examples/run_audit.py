"""Run the localizer on the stored demo journey and print its
genealogy report.

Run: python examples/run_audit.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from med_rec.models import journey_from_dict
from med_rec.report import render_journey_report


def main():
    path = os.path.join(os.path.dirname(__file__), "..", "data", "demo_journey.json")
    with open(os.path.normpath(path)) as handle:
        journey = journey_from_dict(json.load(handle))
    print(render_journey_report(journey))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
