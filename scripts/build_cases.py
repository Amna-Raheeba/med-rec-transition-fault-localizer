"""Build the stored demo journey used by the dashboard examples.

Generates the canonical demo journey (see med_rec.generate.
demo_journey) and writes it to data/demo_journey.json in the
serialised form defined by med_rec.models.

Run: python scripts/build_cases.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from med_rec.evaluate import DEFAULT_CONFIG
from med_rec.generate import demo_journey
from med_rec.models import journey_to_dict


def main():
    root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
    journey = demo_journey(DEFAULT_CONFIG["seed"])
    path = os.path.join(root, "data", "demo_journey.json")
    with open(path, "w") as handle:
        json.dump(journey_to_dict(journey), handle, indent=2, sort_keys=True)
    print(
        "Wrote %s (patient %d, %d faults)"
        % (path, journey.patient_id, len(journey.faults))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
