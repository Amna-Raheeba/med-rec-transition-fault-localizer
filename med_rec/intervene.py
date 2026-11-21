"""Pricing a double-check: intervention placement simulation.

A double-check is a pharmacist review of the outgoing list at one
chosen transition, before that list is finalised. It catches each
discrepancy present in that list with probability `efficacy`
(seeded per instance) and fixes it from that step on. Discrepancies
born later are untouched; discrepancies already corrected by the
journey's own review process are untouched.

Two prices are reported per placement:

- survivors: discrepancies still present in the final discharge
  list -- what reaches the patient at home;
- exposure steps: the number of charted lists (admission,
  transfer, discharge) in which a discrepancy appears before it
  is caught -- how long the wrong list was the working list.

The trade-off is the finding: checking at discharge minimises
survivors but lets every error live in the chart for the whole
stay; checking at admission minimises exposure but cannot see
anything born later.
"""

import random

from .localize import ground_truth_instances

PLACEMENTS = [None, 1, 2, 3]
PLACEMENT_NAMES = {
    None: "no_check",
    1: "check_at_admission",
    2: "check_at_transfer",
    3: "check_at_discharge",
}


def simulate_check(journey, placement, efficacy, seed):
    """Counterfactual outcome of one journey under one placement.

    Returns survivors (count), exposure_steps (count) and the
    number of discrepancy instances that ever appeared.
    """
    instances = ground_truth_instances(journey)
    rng = random.Random(
        seed * 31337
        + journey.patient_id * 131
        + (placement or 0) * 17
        + int(efficacy * 1000)
    )
    survivors = 0
    exposure = 0
    appeared = 0
    for inst in sorted(instances, key=lambda i: i["drug"]):
        present = inst["present_steps"]
        if not present:
            continue
        appeared += 1
        caught = False
        if placement is not None and placement in present:
            caught = rng.random() < efficacy
        if caught:
            exposure += len([s for s in present if s < placement])
        else:
            exposure += len(present)
            if inst["survives"]:
                survivors += 1
    return {
        "survivors": survivors,
        "exposure_steps": exposure,
        "instances": appeared,
    }


def price_interventions(journeys, efficacy, seed):
    """Mean survivors and exposure per journey, per placement."""
    out = {}
    for placement in PLACEMENTS:
        total_survivors = 0
        total_exposure = 0
        for journey in journeys:
            result = simulate_check(journey, placement, efficacy, seed)
            total_survivors += result["survivors"]
            total_exposure += result["exposure_steps"]
        n = max(1, len(journeys))
        out[PLACEMENT_NAMES[placement]] = {
            "placement": placement,
            "efficacy": efficacy,
            "mean_survivors_per_journey": round(total_survivors / n, 4),
            "mean_exposure_steps_per_journey": round(total_exposure / n, 4),
        }
    return out
