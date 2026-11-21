from med_rec.generate import generate_journey
from med_rec.models import (
    FORMULARY,
    MedEntry,
    class_alternatives,
    dose_text,
    drug_class,
    journey_from_dict,
    journey_to_dict,
    standard_dose,
    standard_freq,
)


def test_every_class_has_at_least_two_drugs():
    classes = {}
    for drug in FORMULARY:
        classes.setdefault(drug_class(drug), []).append(drug)
    for cls, drugs in classes.items():
        assert len(drugs) >= 2, cls


def test_dose_ladders_positive_and_sorted():
    for drug, spec in FORMULARY.items():
        doses = spec["doses"]
        assert doses == sorted(doses), drug
        assert all(d > 0 for d in doses), drug
        assert spec["freq"] >= 1, drug


def test_class_alternatives_same_class_excluding_self():
    for drug in FORMULARY:
        alts = class_alternatives(drug)
        assert drug not in alts
        assert all(drug_class(a) == drug_class(drug) for a in alts)


def test_standard_dose_on_ladder():
    for drug in FORMULARY:
        assert standard_dose(drug) in FORMULARY[drug]["doses"]
        assert standard_freq(drug) == FORMULARY[drug]["freq"]


def test_dose_text():
    assert dose_text(500) == "500"
    assert dose_text(2.5) == "2.5"
    assert dose_text(40.0) == "40"


def test_entry_text():
    entry = MedEntry("metformin", 500, 2)
    assert entry.text() == "metformin 500, 2x/day"


def test_journey_serialisation_round_trip():
    journey = generate_journey(4, 20261121)
    data = journey_to_dict(journey)
    restored = journey_from_dict(data)
    assert journey_to_dict(restored) == data


def test_round_trip_preserves_faults_and_ledger():
    journey = generate_journey(9, 20261121)
    restored = journey_from_dict(journey_to_dict(journey))
    assert len(restored.faults) == len(journey.faults)
    assert len(restored.ledger) == len(journey.ledger)
    for step in (0, 1, 2, 3):
        assert [e.drug for e in restored.lists[step]] == [
            e.drug for e in journey.lists[step]
        ]
