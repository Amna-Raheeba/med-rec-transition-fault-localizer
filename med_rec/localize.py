"""The discrepancy genealogist: step-level fault localisation.

The localizer sees only the charted lists and the reason ledger --
never the planted fault records. It:

1. reconstructs the expected lists by replaying the ledger onto
   the home list;
2. diffs each charted list against its expected counterpart and
   classifies the per-drug divergence (the step signature);
3. groups signatures across steps into discrepancy instances and
   assigns each instance a birth transition -- the first step at
   which its signature appears.

Two details do the real work. Substitution pairing is
genealogy-aware: a missing drug is paired with an extra drug of
the same class only if that extra drug is *new* in the chart at
this step (or was already paired with the missing drug at the
previous step). An extra drug that has been sitting in the chart
since an earlier step is an old addition, not a substitution
partner. And when an intermediate list is missing (drop_steps),
an instance first visible after the gap is attributed to the last
transition of the gap -- the localizer can certify "born by
discharge", and the benchmark prices exactly how much that
missing list costs.

Baselines: blame_last_transition keeps the localizer's detections
but assigns every birth to the discharge transition (what a
reviewer with only the final list implicitly does);
end_to_end_diff compares the home and discharge lists directly,
ignoring the ledger entirely.
"""

from .models import MedEntry, drug_class, standard_freq


def _copy_entries(entries):
    return [MedEntry(e.drug, e.dose, e.freq) for e in entries]


def _find(entries, drug):
    for entry in entries:
        if entry.drug == drug:
            return entry
    return None


def _remove(entries, drug):
    return [e for e in entries if e.drug != drug]


def _apply_change(change, entries):
    """Apply one ledger change to a single list (reconstruction)."""
    if change.action == "stop":
        entries[:] = _remove(entries, change.drug)
    elif change.action == "start":
        if _find(entries, change.drug) is None:
            entries.append(
                MedEntry(
                    change.drug, change.new_dose, standard_freq(change.drug)
                )
            )
    elif change.action == "dose_change":
        entry = _find(entries, change.drug)
        if entry is not None:
            entry.dose = change.new_dose
    elif change.action == "substitute":
        entries[:] = _remove(entries, change.drug)
        if _find(entries, change.to_drug) is None:
            entries.append(
                MedEntry(
                    change.to_drug,
                    change.to_dose,
                    standard_freq(change.to_drug),
                )
            )
        else:
            _find(entries, change.to_drug).dose = change.to_dose


def expected_lists(journey):
    """Reconstruct the intended lists from home list + ledger."""
    intended = _copy_entries(journey.lists[0])
    out = {0: _copy_entries(intended)}
    by_transition = {1: [], 2: [], 3: []}
    for entry in journey.ledger:
        by_transition[entry.transition].append(entry)
    for transition in (1, 2, 3):
        for change in by_transition[transition]:
            _apply_change(change, intended)
        out[transition] = _copy_entries(intended)
    return out


def _index(entries):
    counts = {}
    first = {}
    for entry in entries:
        counts[entry.drug] = counts.get(entry.drug, 0) + 1
        if entry.drug not in first:
            first[entry.drug] = entry
    return counts, first


def step_signatures(expected, actual, earlier_expected, prev_actual_drugs,
                    prev_pairs, prev_missing):
    """Classify per-drug divergence between one expected/actual
    list pair. Returns (signatures, substitution_pairs).

    Pairing discipline: a missing drug is paired with a new extra
    drug of the same class only at the step where the disappearance
    is itself new (the drug was present at the previous step) --
    a substitution is an event, not a state. A drug already missing
    at the previous step keeps the classification it earned then.
    """
    exp_counts, exp_first = _index(expected)
    act_counts, act_first = _index(actual)
    signatures = {}
    pairs = {}
    missing = sorted(d for d in exp_first if act_counts.get(d, 0) == 0)
    extra = sorted(d for d in act_first if d not in exp_first)
    consumed = set()
    # Sticky pairs: a substitution already identified at the
    # previous step stays identified while both sides persist.
    for out_drug, in_drug in sorted(prev_pairs.items()):
        if out_drug in missing and in_drug in extra:
            signatures[out_drug] = "substitution"
            signatures[in_drug] = "substitution"
            pairs[out_drug] = in_drug
            consumed.add(in_drug)
    for drug in missing:
        if drug in signatures:
            continue
        if drug in prev_missing:
            signatures[drug] = "omission"
            continue
        partner = None
        for cand in extra:
            if cand in consumed:
                continue
            if cand in prev_actual_drugs:
                continue  # old extra: an addition, not a partner
            if drug_class(cand) == drug_class(drug):
                partner = cand
                break
        if partner is not None:
            signatures[drug] = "substitution"
            signatures[partner] = "substitution"
            pairs[drug] = partner
            consumed.add(partner)
        else:
            signatures[drug] = "omission"
    for drug in extra:
        if drug in consumed or drug in signatures:
            continue
        if drug in earlier_expected:
            signatures[drug] = "resurrection"
        else:
            signatures[drug] = "addition"
    for drug in exp_first:
        if drug in signatures:
            continue
        if act_counts.get(drug, 0) >= 2:
            signatures[drug] = "duplication"
        elif (
            act_first[drug].dose != exp_first[drug].dose
            or act_first[drug].freq != exp_first[drug].freq
        ):
            signatures[drug] = "dose_drift"
    return signatures, pairs


def replay_signatures(journey, drop_steps=()):
    """Step signatures for every observed step of a journey."""
    expected = expected_lists(journey)
    signatures = {}
    pairs = {}
    earlier = set(e.drug for e in expected[0])
    prev_actual_drugs = set(e.drug for e in journey.lists[0])
    prev_missing = set()
    for step in (1, 2, 3):
        if step not in drop_steps:
            sig, pairs = step_signatures(
                expected[step],
                journey.lists[step],
                earlier,
                prev_actual_drugs,
                pairs,
                prev_missing,
            )
            signatures[step] = sig
            prev_actual_drugs = set(e.drug for e in journey.lists[step])
            prev_missing = set(
                e.drug
                for e in expected[step]
                if e.drug not in prev_actual_drugs
            )
        earlier |= set(e.drug for e in expected[step])
    return signatures


def localize(journey, drop_steps=()):
    """Localize discrepancies in one journey.

    drop_steps names chart snapshots the localizer may not see
    (e.g. (2,) = the transfer list is missing). Returns a list of
    instance dicts: drug, fault_type, birth, first_step, last_step,
    present_steps, survives.
    """
    expected = expected_lists(journey)
    signatures = replay_signatures(journey, drop_steps=drop_steps)
    observed = [s for s in (1, 2, 3) if s not in drop_steps]
    open_instances = {}
    finished = []
    prev_step = None
    for step in observed:
        sig = signatures[step]
        exp_drugs = set(e.drug for e in expected[step])
        current = {}
        for drug, fault_type in sig.items():
            if fault_type == "substitution" and drug not in exp_drugs:
                continue  # incoming side of a substitution pair
            current[drug] = fault_type
        for drug in list(open_instances):
            if current.get(drug) != open_instances[drug]["fault_type"]:
                inst = open_instances.pop(drug)
                inst["last_step"] = prev_step
                finished.append(inst)
        for drug, fault_type in current.items():
            if drug not in open_instances:
                open_instances[drug] = {
                    "drug": drug,
                    "fault_type": fault_type,
                    "birth": step,
                    "first_step": step,
                }
        prev_step = step
    for drug, inst in open_instances.items():
        inst["last_step"] = prev_step
        finished.append(inst)
    for inst in finished:
        inst["present_steps"] = [
            s
            for s in observed
            if inst["first_step"] <= s <= inst["last_step"]
        ]
        inst["survives"] = inst["last_step"] == 3
    finished.sort(key=lambda i: (i["birth"], i["drug"]))
    return finished


def ground_truth_instances(journey):
    """Scoreable ground truth: one instance per planted fault,
    with presence read off the full signature replay (so a fault
    the generator's own bookkeeping and the chart disagree about
    is scored as the chart shows it)."""
    signatures = replay_signatures(journey)
    out = []
    for fault in journey.faults:
        present = [
            step
            for step in (1, 2, 3)
            if signatures[step].get(fault.drug) == fault.fault_type
        ]
        out.append(
            {
                "drug": fault.drug,
                "fault_type": fault.fault_type,
                "birth": fault.transition,
                "other_drug": fault.other_drug,
                "present_steps": present,
                "survives": 3 in present,
                "corrected_at": fault.corrected_at,
            }
        )
    return out


def blame_last_transition(journey):
    """Baseline: the localizer's detections, every birth blamed on
    the discharge transition."""
    instances = localize(journey)
    for inst in instances:
        inst["birth"] = 3
    return instances


def end_to_end_diff(journey):
    """Baseline: diff the home list against the discharge list,
    ignoring the ledger and every intermediate list. Cannot see
    resurrections at all (the drug is on both lists) and flags
    every intentional change as a discrepancy."""
    home_counts, home_first = _index(journey.lists[0])
    dis_counts, dis_first = _index(journey.lists[3])
    instances = []
    for drug in sorted(set(home_first) | set(dis_first)):
        fault_type = None
        if home_counts.get(drug, 0) >= 1 and dis_counts.get(drug, 0) == 0:
            fault_type = "omission"
        elif home_counts.get(drug, 0) == 0 and dis_counts.get(drug, 0) >= 1:
            fault_type = "addition"
        elif dis_counts.get(drug, 0) >= 2:
            fault_type = "duplication"
        elif (
            drug in home_first
            and drug in dis_first
            and (
                home_first[drug].dose != dis_first[drug].dose
                or home_first[drug].freq != dis_first[drug].freq
            )
        ):
            fault_type = "dose_drift"
        if fault_type is not None:
            instances.append(
                {
                    "drug": drug,
                    "fault_type": fault_type,
                    "birth": 3,
                    "first_step": 3,
                    "last_step": 3,
                    "present_steps": [3],
                    "survives": True,
                }
            )
    return instances
