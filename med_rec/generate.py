"""Seeded generator of synthetic medication-reconciliation journeys.

Each journey starts from a sampled home list. At every transition
the generator, in order:

1. lets a pharmacist review correct some already-active faults
   (probability CORRECTION_RATE each) -- the chart is fixed from
   that step on;
2. draws intentional changes (stops, starts, dose changes,
   formulary substitutions), applies each to the intended regimen
   and mirrors it onto the charted list, and records it in the
   reason ledger;
3. plants new faults on the charted list only, at declared rates,
   each on a drug no earlier fault has touched.

Declared simplifications (also stated in the README): intentional
changes never target a drug carrying a planted fault, so a fault
is cleared only by a review correction, never as a side effect of
a later order; and each fault type fires at most once per
transition. Both keep the ground-truth genealogy unambiguous --
the ambiguity the localizer is actually scored on lives in the
missing-list condition and in same-class pairing, not in
bookkeeping artefacts.
"""

import random

from .models import (
    DRUG_ORDER,
    FORMULARY,
    FaultRecord,
    Journey,
    LedgerEntry,
    MedEntry,
    class_alternatives,
    drug_class,
    standard_dose,
    standard_freq,
)

# Probability that each fault type is planted at a transition,
# given a valid target exists. Resurrection additionally needs a
# drug stopped at an earlier transition.
FAULT_RATES = {
    "omission": 0.30,
    "dose_drift": 0.27,
    "duplication": 0.16,
    "substitution": 0.16,
    "addition": 0.14,
    "resurrection": 0.20,
}

# Fault types are attempted in this fixed order each transition;
# addition comes last so the generator can avoid planting an
# addition that a same-class omission at the same transition
# would make indistinguishable from a substitution.
FAULT_ORDER = [
    "omission",
    "dose_drift",
    "duplication",
    "substitution",
    "resurrection",
    "addition",
]

CORRECTION_RATE = 0.15

STOP_REASONS = [
    "course complete",
    "held before procedure",
    "adverse effect suspected",
    "therapy no longer indicated",
]
START_REASONS = [
    "started -- new indication",
    "started -- guideline-directed therapy",
    "restarted -- indication returned",
]
DOSE_UP_REASONS = ["dose increased -- inadequate response"]
DOSE_DOWN_REASONS = [
    "dose reduced -- renal function",
    "dose reduced -- target now met",
]
SUBSTITUTE_REASONS = ["formulary substitution"]


def _copy_entries(entries):
    return [MedEntry(e.drug, e.dose, e.freq) for e in entries]


def _find(entries, drug):
    for entry in entries:
        if entry.drug == drug:
            return entry
    return None


def _remove(entries, drug):
    return [e for e in entries if e.drug != drug]


def _sample_home_list(rng):
    n = rng.randint(4, 8)
    drugs = rng.sample(DRUG_ORDER, n)
    entries = []
    for drug in drugs:
        dose = rng.choice(FORMULARY[drug]["doses"])
        entries.append(MedEntry(drug, dose, standard_freq(drug)))
    return entries


def _apply_intentional(change, intended, actual):
    """Apply one ledger change to the intended regimen and mirror
    it onto the charted list."""
    action = change.action
    drug = change.drug
    if action == "stop":
        intended[:] = _remove(intended, drug)
        actual[:] = _remove(actual, drug)
    elif action == "start":
        if _find(intended, drug) is None:
            intended.append(
                MedEntry(drug, change.new_dose, standard_freq(drug))
            )
        entry = _find(actual, drug)
        if entry is None:
            actual.append(MedEntry(drug, change.new_dose, standard_freq(drug)))
        else:
            entry.dose = change.new_dose
    elif action == "dose_change":
        entry = _find(intended, drug)
        if entry is not None:
            entry.dose = change.new_dose
        for entry in actual:
            if entry.drug == drug:
                entry.dose = change.new_dose
    elif action == "substitute":
        intended[:] = _remove(intended, drug)
        intended.append(
            MedEntry(change.to_drug, change.to_dose, standard_freq(change.to_drug))
        )
        actual[:] = _remove(actual, drug)
        if _find(actual, change.to_drug) is None:
            actual.append(
                MedEntry(
                    change.to_drug,
                    change.to_dose,
                    standard_freq(change.to_drug),
                )
            )
        else:
            _find(actual, change.to_drug).dose = change.to_dose


def _draw_intentional(rng, transition, intended, actual, ever_faulted, stopped):
    """Draw 0-2 intentional changes on distinct, unfaulted drugs."""
    changes = []
    changed = set()
    roll = rng.random()
    n_changes = 0 if roll < 0.25 else (1 if roll < 0.75 else 2)
    in_intended = [e.drug for e in intended]
    for _ in range(n_changes):
        kinds = []
        stop_candidates = [d for d in in_intended if d not in ever_faulted]
        if stop_candidates:
            kinds += ["stop"] * 3
        dose_candidates = [
            d
            for d in in_intended
            if d not in ever_faulted and len(FORMULARY[d]["doses"]) > 0
        ]
        if dose_candidates:
            kinds += ["dose_change"] * 4
        start_candidates = [
            d
            for d in DRUG_ORDER
            if d not in in_intended
            and d not in ever_faulted
            and _find(actual, d) is None
        ]
        if start_candidates:
            kinds += ["start"] * 2
        sub_candidates = []
        for d in in_intended:
            if d in ever_faulted:
                continue
            for alt in class_alternatives(d):
                if (
                    alt not in in_intended
                    and alt not in ever_faulted
                    and _find(actual, alt) is None
                ):
                    sub_candidates.append((d, alt))
        if sub_candidates:
            kinds += ["substitute"] * 2
        kinds = [k for k in kinds if True]
        if not kinds:
            break
        kind = rng.choice(kinds)
        if kind == "stop":
            pool = [d for d in stop_candidates if d not in changed]
            if not pool:
                continue
            drug = rng.choice(pool)
            changes.append(
                LedgerEntry(transition, "stop", drug, rng.choice(STOP_REASONS))
            )
            changed.add(drug)
        elif kind == "dose_change":
            pool = [d for d in dose_candidates if d not in changed]
            if not pool:
                continue
            drug = rng.choice(pool)
            current = _find(intended, drug).dose
            ladder = FORMULARY[drug]["doses"]
            options = [d for d in ladder if d != current]
            if not options:
                continue
            new_dose = rng.choice(options)
            reason = rng.choice(
                DOSE_UP_REASONS if new_dose > current else DOSE_DOWN_REASONS
            )
            changes.append(
                LedgerEntry(transition, "dose_change", drug, reason, new_dose=new_dose)
            )
            changed.add(drug)
        elif kind == "start":
            pool = [d for d in start_candidates if d not in changed]
            if not pool:
                continue
            drug = rng.choice(pool)
            changes.append(
                LedgerEntry(
                    transition,
                    "start",
                    drug,
                    rng.choice(START_REASONS),
                    new_dose=standard_dose(drug),
                )
            )
            changed.add(drug)
        else:  # substitute
            pool = [(a, b) for (a, b) in sub_candidates if a not in changed]
            if not pool:
                continue
            drug, alt = rng.choice(pool)
            changes.append(
                LedgerEntry(
                    transition,
                    "substitute",
                    drug,
                    rng.choice(SUBSTITUTE_REASONS),
                    to_drug=alt,
                    to_dose=standard_dose(alt),
                )
            )
            changed.add(drug)
            changed.add(alt)
    return changes


def _correct_fault(fault, intended, actual):
    """Fix one active fault on the charted list (review catch)."""
    drug = fault.drug
    intended_entry = _find(intended, drug)
    if fault.fault_type == "omission":
        if intended_entry is not None and _find(actual, drug) is None:
            actual.append(
                MedEntry(drug, intended_entry.dose, intended_entry.freq)
            )
    elif fault.fault_type == "dose_drift":
        if intended_entry is not None:
            for entry in actual:
                if entry.drug == drug:
                    entry.dose = intended_entry.dose
    elif fault.fault_type == "duplication":
        seen = False
        kept = []
        for entry in actual:
            if entry.drug == drug:
                if seen:
                    continue
                seen = True
            kept.append(entry)
        actual[:] = kept
    elif fault.fault_type == "substitution":
        actual[:] = _remove(actual, fault.other_drug)
        if intended_entry is not None and _find(actual, drug) is None:
            actual.append(
                MedEntry(drug, intended_entry.dose, intended_entry.freq)
            )
    elif fault.fault_type in ("addition", "resurrection"):
        actual[:] = _remove(actual, drug)


def _plant_fault(rng, fault_type, transition, intended, actual, ever_faulted,
                 changed_this_transition, stopped, planted_this_transition,
                 ever_intended):
    """Try to plant one fault; returns a FaultRecord or None."""
    in_actual = [e.drug for e in actual]
    in_intended = [e.drug for e in intended]
    # Classes of drugs that go missing at this transition (omitted,
    # or substituted away). A new extra drug in one of these classes
    # would be indistinguishable from a substitution partner for
    # the missing drug -- for the localizer and for a human
    # reviewer alike -- so the generator does not plant additions
    # or resurrections into those classes at this transition.
    omitted_classes = set(
        drug_class(f.drug)
        for f in planted_this_transition
        if f.fault_type in ("omission", "substitution")
    )

    def blocked(drug):
        return (
            drug in ever_faulted
            or drug in changed_this_transition
        )

    if fault_type in ("omission", "dose_drift", "duplication"):
        pool = [
            d
            for d in in_intended
            if d in in_actual and not blocked(d)
        ]
        if not pool:
            return None
        drug = rng.choice(pool)
        entry = _find(actual, drug)
        if fault_type == "omission":
            actual[:] = _remove(actual, drug)
            return FaultRecord("omission", drug, transition)
        if fault_type == "dose_drift":
            ladder = FORMULARY[drug]["doses"]
            options = [d for d in ladder if d != entry.dose]
            new_dose = rng.choice(options) if options else entry.dose * 2
            entry.dose = new_dose
            return FaultRecord("dose_drift", drug, transition, detail=new_dose)
        actual.append(MedEntry(drug, entry.dose, entry.freq))
        return FaultRecord("duplication", drug, transition)

    if fault_type == "substitution":
        # Avoid competing with a same-class omission planted at this
        # transition (see omitted_classes above).
        pool = []
        for drug in in_intended:
            if drug not in in_actual or blocked(drug):
                continue
            if drug_class(drug) in omitted_classes:
                continue
            for alt in class_alternatives(drug):
                if (
                    alt not in in_intended
                    and alt not in in_actual
                    and not blocked(alt)
                ):
                    pool.append((drug, alt))
        if not pool:
            return None
        drug, alt = rng.choice(pool)
        actual[:] = _remove(actual, drug)
        actual.append(MedEntry(alt, standard_dose(alt), standard_freq(alt)))
        return FaultRecord("substitution", drug, transition, other_drug=alt)

    if fault_type == "resurrection":
        pool = [
            d
            for d, (stop_transition, _dose) in stopped.items()
            if stop_transition < transition
            and d not in in_intended
            and d not in in_actual
            and not blocked(d)
            and drug_class(d) not in omitted_classes
        ]
        if not pool:
            return None
        drug = rng.choice(pool)
        _stop_transition, dose = stopped[drug]
        actual.append(MedEntry(drug, dose, standard_freq(drug)))
        return FaultRecord("resurrection", drug, transition, detail=dose)

    if fault_type == "addition":
        # A drug that was on the regimen earlier in this journey
        # and comes back is a resurrection, not an addition -- the
        # chart cannot tell the two apart, so additions are planted
        # only on drugs with no history in the journey.
        pool = [
            d
            for d in DRUG_ORDER
            if d not in in_intended
            and d not in in_actual
            and d not in ever_intended
            and not blocked(d)
            and drug_class(d) not in omitted_classes
        ]
        if not pool:
            return None
        drug = rng.choice(pool)
        actual.append(
            MedEntry(drug, standard_dose(drug), standard_freq(drug))
        )
        return FaultRecord("addition", drug, transition)

    return None


def generate_journey(patient_id, seed, fault_scale=1.0, correction_rate=None):
    """Generate one deterministic journey.

    fault_scale multiplies every fault rate (0.0 = a clean journey
    with intentional changes only). correction_rate overrides the
    review-correction probability.
    """
    if correction_rate is None:
        correction_rate = CORRECTION_RATE
    rng = random.Random(seed * 1000003 + patient_id * 7919)
    home = _sample_home_list(rng)
    intended = _copy_entries(home)
    actual = _copy_entries(home)
    journey = Journey(patient_id=patient_id)
    journey.lists[0] = _copy_entries(actual)
    journey.intended_lists[0] = _copy_entries(intended)
    stopped = {}  # drug -> (transition stopped, dose at stop)
    ever_faulted = set()
    ever_intended = set(e.drug for e in home)

    for transition in (1, 2, 3):
        # 1. Review corrections of faults born at earlier steps.
        for fault in journey.faults:
            if fault.corrected_at is None and fault.transition < transition:
                if rng.random() < correction_rate:
                    _correct_fault(fault, intended, actual)
                    fault.corrected_at = transition
        # 2. Intentional changes (ledger).
        changes = _draw_intentional(
            rng, transition, intended, actual, ever_faulted, stopped
        )
        changed_drugs = set()
        for change in changes:
            if change.action == "stop":
                entry = _find(intended, change.drug)
                if entry is not None:
                    stopped[change.drug] = (transition, entry.dose)
            if change.action == "start" and change.drug in stopped:
                del stopped[change.drug]
            if change.action == "substitute":
                entry = _find(intended, change.drug)
                if entry is not None:
                    stopped[change.drug] = (transition, entry.dose)
                if change.to_drug in stopped:
                    del stopped[change.to_drug]
                changed_drugs.add(change.to_drug)
            _apply_intentional(change, intended, actual)
            journey.ledger.append(change)
            changed_drugs.add(change.drug)
            if change.action == "start":
                ever_intended.add(change.drug)
            if change.action == "substitute":
                ever_intended.add(change.to_drug)
        # 3. Planted faults.
        planted = []
        for fault_type in FAULT_ORDER:
            rate = FAULT_RATES[fault_type] * fault_scale
            if rng.random() >= rate:
                continue
            fault = _plant_fault(
                rng,
                fault_type,
                transition,
                intended,
                actual,
                ever_faulted,
                changed_drugs,
                stopped,
                planted,
                ever_intended,
            )
            if fault is not None:
                journey.faults.append(fault)
                planted.append(fault)
                ever_faulted.add(fault.drug)
                if fault.other_drug is not None:
                    ever_faulted.add(fault.other_drug)
        journey.lists[transition] = _copy_entries(actual)
        journey.intended_lists[transition] = _copy_entries(intended)
    return journey


def generate_journeys(n, seed, **kwargs):
    return [generate_journey(i, seed, **kwargs) for i in range(n)]


def demo_journey(seed):
    """The canonical demo journey: the first seeded journey with at
    least three faults, a resurrection among them, and at least two
    faults surviving to discharge. Deterministic in the seed."""
    from .localize import ground_truth_instances

    for patient_id in range(200):
        journey = generate_journey(patient_id, seed)
        types = set(f.fault_type for f in journey.faults)
        surviving = [
            inst for inst in ground_truth_instances(journey) if inst["survives"]
        ]
        if (
            len(journey.faults) >= 3
            and "resurrection" in types
            and len(surviving) >= 2
        ):
            return journey
    return generate_journey(0, seed)
