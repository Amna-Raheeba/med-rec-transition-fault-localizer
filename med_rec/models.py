"""Data model for the medication-reconciliation fault localizer.

A patient journey is four medication lists -- home, admission,
transfer, discharge -- produced by three transitions. Two forces
change the list at each transition:

- intentional changes, which are documented in a reason ledger
  (a stop with a reason, a dose adjustment, a formulary swap);
- planted unintentional discrepancies (faults): omission, dose
  drift, duplication, substitution, addition, and resurrection of
  a drug that was intentionally stopped earlier.

Every fault is injected at a known transition, so each discrepancy
has a ground-truth genealogy: the transition where it was born,
the steps whose lists it appears in, and whether it survives to
the discharge list. The localizer never sees the fault records --
it works from the lists and the ledger alone -- which is what
makes the benchmark honest.
"""

from dataclasses import dataclass, field

# The four chart snapshots, in order. Step 0 is the home list;
# transition t (1..3) produces the list at step t.
STEP_NAMES = ["home", "admission", "transfer", "discharge"]
TRANSITION_NAMES = {
    1: "home -> admission",
    2: "admission -> transfer",
    3: "transfer -> discharge",
}

# Fault types the generator can plant and the localizer can name.
FAULT_TYPES = [
    "omission",
    "dose_drift",
    "duplication",
    "substitution",
    "addition",
    "resurrection",
]

# Formulary: drug -> therapeutic class, standard dose ladder,
# standard frequency per day. Doses are charted amounts (mg, units
# or mcg depending on the drug); the number is what the chart says.
FORMULARY = {
    "metformin": {"class": "antidiabetic", "doses": [500, 850, 1000], "freq": 2},
    "gliclazide": {"class": "antidiabetic", "doses": [40, 80], "freq": 1},
    "insulin_glargine": {"class": "antidiabetic", "doses": [10, 20, 30], "freq": 1},
    "amlodipine": {"class": "antihypertensive", "doses": [5, 10], "freq": 1},
    "lisinopril": {"class": "antihypertensive", "doses": [5, 10, 20], "freq": 1},
    "losartan": {"class": "antihypertensive", "doses": [25, 50, 100], "freq": 1},
    "atenolol": {"class": "antihypertensive", "doses": [25, 50, 100], "freq": 1},
    "atorvastatin": {"class": "lipid_lowering", "doses": [10, 20, 40], "freq": 1},
    "simvastatin": {"class": "lipid_lowering", "doses": [20, 40], "freq": 1},
    "omeprazole": {"class": "acid_suppression", "doses": [20, 40], "freq": 1},
    "pantoprazole": {"class": "acid_suppression", "doses": [40], "freq": 1},
    "paracetamol": {"class": "analgesic", "doses": [500, 1000], "freq": 3},
    "ibuprofen": {"class": "analgesic", "doses": [200, 400], "freq": 3},
    "warfarin": {"class": "anticoagulant", "doses": [1, 2, 5], "freq": 1},
    "apixaban": {"class": "anticoagulant", "doses": [2.5, 5], "freq": 2},
    "sertraline": {"class": "antidepressant", "doses": [50, 100], "freq": 1},
    "citalopram": {"class": "antidepressant", "doses": [10, 20], "freq": 1},
    "furosemide": {"class": "diuretic", "doses": [20, 40], "freq": 2},
    "spironolactone": {"class": "diuretic", "doses": [25, 50], "freq": 1},
    "salbutamol": {"class": "bronchodilator", "doses": [100, 200], "freq": 3},
    "tiotropium": {"class": "bronchodilator", "doses": [18], "freq": 1},
}

DRUG_ORDER = sorted(FORMULARY.keys())


def drug_class(drug):
    return FORMULARY[drug]["class"]


def class_alternatives(drug):
    """Other formulary drugs in the same therapeutic class."""
    cls = drug_class(drug)
    return [d for d in DRUG_ORDER if d != drug and drug_class(d) == cls]


def standard_dose(drug):
    """The middle (most commonly charted) dose on the ladder."""
    doses = FORMULARY[drug]["doses"]
    return doses[len(doses) // 2]


def standard_freq(drug):
    return FORMULARY[drug]["freq"]


def dose_text(dose):
    value = float(dose)
    if value == int(value):
        return "%d" % int(value)
    return "%s" % value


@dataclass
class MedEntry:
    """One line on one medication list."""

    drug: str
    dose: float
    freq: int

    def text(self):
        return "%s %s, %dx/day" % (self.drug, dose_text(self.dose), self.freq)


@dataclass
class LedgerEntry:
    """One documented, intentional change at one transition."""

    transition: int
    action: str  # "stop" | "start" | "dose_change" | "substitute"
    drug: str
    reason: str
    new_dose: object = None  # for start / dose_change
    to_drug: object = None  # for substitute
    to_dose: object = None  # for substitute


@dataclass
class FaultRecord:
    """Ground truth for one planted discrepancy."""

    fault_type: str
    drug: str  # primary drug (the outgoing drug for a substitution)
    transition: int  # birth transition
    other_drug: object = None  # incoming drug for a substitution
    detail: object = None  # e.g. the drifted dose for dose_drift
    corrected_at: object = None  # step at which a review fixed it


@dataclass
class Journey:
    """One synthetic patient journey: lists, ledger, ground truth."""

    patient_id: int
    # step (0..3) -> list of MedEntry, as actually charted.
    lists: dict = field(default_factory=dict)
    # step (0..3) -> list of MedEntry, as the ledger says they
    # should be. Ground truth for tests and scoring; the localizer
    # reconstructs this from the home list + ledger and never
    # reads it.
    intended_lists: dict = field(default_factory=dict)
    ledger: list = field(default_factory=list)
    faults: list = field(default_factory=list)

    def list_at(self, step):
        return self.lists[step]

    def drugs_at(self, step):
        return [entry.drug for entry in self.lists[step]]


def entry_to_dict(entry):
    return {"drug": entry.drug, "dose": entry.dose, "freq": entry.freq}


def entry_from_dict(data):
    return MedEntry(drug=data["drug"], dose=data["dose"], freq=data["freq"])


def ledger_to_dict(entry):
    return {
        "transition": entry.transition,
        "action": entry.action,
        "drug": entry.drug,
        "reason": entry.reason,
        "new_dose": entry.new_dose,
        "to_drug": entry.to_drug,
        "to_dose": entry.to_dose,
    }


def ledger_from_dict(data):
    return LedgerEntry(
        transition=data["transition"],
        action=data["action"],
        drug=data["drug"],
        reason=data["reason"],
        new_dose=data["new_dose"],
        to_drug=data["to_drug"],
        to_dose=data["to_dose"],
    )


def fault_to_dict(fault):
    return {
        "fault_type": fault.fault_type,
        "drug": fault.drug,
        "transition": fault.transition,
        "other_drug": fault.other_drug,
        "detail": fault.detail,
        "corrected_at": fault.corrected_at,
    }


def fault_from_dict(data):
    return FaultRecord(
        fault_type=data["fault_type"],
        drug=data["drug"],
        transition=data["transition"],
        other_drug=data["other_drug"],
        detail=data["detail"],
        corrected_at=data["corrected_at"],
    )


def journey_to_dict(journey):
    return {
        "patient_id": journey.patient_id,
        "lists": dict(
            (str(step), [entry_to_dict(e) for e in entries])
            for step, entries in journey.lists.items()
        ),
        "intended_lists": dict(
            (str(step), [entry_to_dict(e) for e in entries])
            for step, entries in journey.intended_lists.items()
        ),
        "ledger": [ledger_to_dict(e) for e in journey.ledger],
        "faults": [fault_to_dict(f) for f in journey.faults],
    }


def journey_from_dict(data):
    return Journey(
        patient_id=data["patient_id"],
        lists=dict(
            (int(step), [entry_from_dict(e) for e in entries])
            for step, entries in data["lists"].items()
        ),
        intended_lists=dict(
            (int(step), [entry_from_dict(e) for e in entries])
            for step, entries in data["intended_lists"].items()
        ),
        ledger=[ledger_from_dict(e) for e in data["ledger"]],
        faults=[fault_from_dict(f) for f in data["faults"]],
    )
