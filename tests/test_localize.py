from med_rec.evaluate import evaluate_journeys
from med_rec.generate import generate_journeys
from med_rec.localize import (
    end_to_end_diff,
    expected_lists,
    ground_truth_instances,
    localize,
)
from med_rec.models import Journey, LedgerEntry, MedEntry

SEED = 20261121


def _journey(lists, ledger=None):
    return Journey(
        patient_id=999,
        lists=lists,
        intended_lists={},
        ledger=ledger or [],
        faults=[],
    )


def _entries(*specs):
    return [MedEntry(drug, dose, freq) for (drug, dose, freq) in specs]


def test_expected_lists_match_generator_intended():
    for journey in generate_journeys(25, SEED):
        expected = expected_lists(journey)
        for step in (0, 1, 2, 3):
            got = sorted((e.drug, e.dose, e.freq) for e in expected[step])
            want = sorted(
                (e.drug, e.dose, e.freq) for e in journey.intended_lists[step]
            )
            assert got == want


def test_clean_journeys_have_no_discrepancies():
    for journey in generate_journeys(8, SEED, fault_scale=0.0):
        assert localize(journey) == []


def test_ground_truth_presence_contiguous_from_birth():
    for journey in generate_journeys(40, SEED):
        for inst in ground_truth_instances(journey):
            present = inst["present_steps"]
            assert present, inst
            assert present == list(
                range(inst["birth"], inst["birth"] + len(present))
            ), inst


def test_localizer_perfect_on_seeded_batch():
    journeys = generate_journeys(30, SEED)
    scores = evaluate_journeys(journeys)
    full = scores["localization"]["localizer_full"]
    assert full["accuracy"] == 1.0
    assert scores["detection"]["localizer"]["f1"] == 1.0


def test_missing_transfer_list_costs_accuracy():
    journeys = generate_journeys(30, SEED)
    scores = evaluate_journeys(journeys)
    full = scores["localization"]["localizer_full"]["accuracy"]
    missing = scores["localization"]["localizer_missing_transfer"]["accuracy"]
    assert missing < full


def test_blame_last_matches_share_born_at_discharge():
    journeys = generate_journeys(30, SEED)
    scores = evaluate_journeys(journeys)
    blame = scores["localization"]["blame_last_transition"]
    truth_total = blame["n_truth"]
    born_at_3 = 0
    for journey in journeys:
        for inst in ground_truth_instances(journey):
            if inst["survives"] and inst["birth"] == 3:
                born_at_3 += 1
    assert blame["birth_correct"] == born_at_3
    assert blame["accuracy"] == round(born_at_3 / truth_total, 4)


def test_handbuilt_omission():
    home = _entries(("metformin", 500, 2), ("amlodipine", 5, 1))
    rest = _entries(("metformin", 500, 2))
    journey = _journey({0: home, 1: rest, 2: rest, 3: rest})
    found = localize(journey)
    assert len(found) == 1
    inst = found[0]
    assert inst["drug"] == "amlodipine"
    assert inst["fault_type"] == "omission"
    assert inst["birth"] == 1
    assert inst["survives"]


def test_handbuilt_dose_drift_at_transfer():
    base = _entries(("metformin", 500, 2))
    drifted = _entries(("metformin", 1000, 2))
    journey = _journey({0: base, 1: base, 2: drifted, 3: drifted})
    found = localize(journey)
    assert len(found) == 1
    assert found[0]["fault_type"] == "dose_drift"
    assert found[0]["birth"] == 2


def test_handbuilt_duplication_at_discharge():
    base = _entries(("amlodipine", 5, 1))
    dup = _entries(("amlodipine", 5, 1), ("amlodipine", 5, 1))
    journey = _journey({0: base, 1: base, 2: base, 3: dup})
    found = localize(journey)
    assert len(found) == 1
    assert found[0]["fault_type"] == "duplication"
    assert found[0]["birth"] == 3


def test_handbuilt_resurrection():
    home = _entries(("metformin", 500, 2), ("amlodipine", 5, 1))
    stopped = _entries(("metformin", 500, 2))
    back = _entries(("metformin", 500, 2), ("amlodipine", 5, 1))
    ledger = [
        LedgerEntry(1, "stop", "amlodipine", "course complete")
    ]
    journey = _journey({0: home, 1: stopped, 2: back, 3: back}, ledger)
    found = localize(journey)
    assert len(found) == 1
    assert found[0]["drug"] == "amlodipine"
    assert found[0]["fault_type"] == "resurrection"
    assert found[0]["birth"] == 2


def test_handbuilt_substitution_pairs_same_class():
    home = _entries(("omeprazole", 20, 1))
    swapped = _entries(("pantoprazole", 40, 1))
    journey = _journey({0: home, 1: home, 2: swapped, 3: swapped})
    found = localize(journey)
    assert len(found) == 1
    assert found[0]["drug"] == "omeprazole"
    assert found[0]["fault_type"] == "substitution"
    assert found[0]["birth"] == 2


def test_old_extra_is_not_a_substitution_partner():
    home = _entries(("metformin", 500, 2), ("gliclazide", 40, 1))
    with_addition = _entries(
        ("metformin", 500, 2),
        ("gliclazide", 40, 1),
        ("insulin_glargine", 20, 1),
    )
    after_omission = _entries(
        ("metformin", 500, 2), ("insulin_glargine", 20, 1)
    )
    journey = _journey(
        {0: home, 1: with_addition, 2: after_omission, 3: after_omission}
    )
    found = dict((i["drug"], i) for i in localize(journey))
    assert found["insulin_glargine"]["fault_type"] == "addition"
    assert found["insulin_glargine"]["birth"] == 1
    assert found["gliclazide"]["fault_type"] == "omission"
    assert found["gliclazide"]["birth"] == 2


def test_end_to_end_cannot_see_resurrection():
    home = _entries(("metformin", 500, 2), ("amlodipine", 5, 1))
    stopped = _entries(("metformin", 500, 2))
    back = _entries(("metformin", 500, 2), ("amlodipine", 5, 1))
    ledger = [LedgerEntry(1, "stop", "amlodipine", "course complete")]
    journey = _journey({0: home, 1: stopped, 2: back, 3: back}, ledger)
    e2e = end_to_end_diff(journey)
    assert all(i["drug"] != "amlodipine" for i in e2e)
    assert any(
        i["fault_type"] == "resurrection" for i in localize(journey)
    )


def test_end_to_end_flags_intentional_change_localizer_does_not():
    home = _entries(("metformin", 500, 2))
    changed = _entries(("metformin", 1000, 2))
    ledger = [
        LedgerEntry(
            1,
            "dose_change",
            "metformin",
            "dose increased -- inadequate response",
            new_dose=1000,
        )
    ]
    journey = _journey({0: home, 1: changed, 2: changed, 3: changed}, ledger)
    assert localize(journey) == []
    e2e = end_to_end_diff(journey)
    assert len(e2e) == 1
    assert e2e[0]["fault_type"] == "dose_drift"


def test_missing_transfer_attributes_gap_birth_to_discharge():
    home = _entries(("metformin", 500, 2), ("amlodipine", 5, 1))
    rest = _entries(("metformin", 500, 2))
    journey = _journey({0: home, 1: home, 2: rest, 3: rest})
    full = localize(journey)
    assert full[0]["birth"] == 2
    missing = localize(journey, drop_steps=(2,))
    assert len(missing) == 1
    assert missing[0]["fault_type"] == "omission"
    assert missing[0]["birth"] == 3


def test_corrected_fault_does_not_survive():
    home = _entries(("metformin", 500, 2), ("amlodipine", 5, 1))
    missing_list = _entries(("metformin", 500, 2))
    journey = _journey({0: home, 1: missing_list, 2: home, 3: home})
    found = localize(journey)
    assert len(found) == 1
    assert found[0]["fault_type"] == "omission"
    assert not found[0]["survives"]
    assert found[0]["last_step"] == 1
