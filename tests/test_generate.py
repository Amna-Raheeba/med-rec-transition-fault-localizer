from med_rec.generate import demo_journey, generate_journeys, generate_journey
from med_rec.localize import ground_truth_instances
from med_rec.models import FAULT_TYPES, FORMULARY, drug_class, journey_to_dict

SEED = 20261121


def test_deterministic_same_seed():
    a = generate_journey(3, SEED)
    b = generate_journey(3, SEED)
    assert journey_to_dict(a) == journey_to_dict(b)


def test_different_patients_differ():
    a = generate_journey(3, SEED)
    b = generate_journey(4, SEED)
    assert journey_to_dict(a) != journey_to_dict(b)


def test_journey_has_four_steps():
    journey = generate_journey(0, SEED)
    assert sorted(journey.lists.keys()) == [0, 1, 2, 3]
    assert sorted(journey.intended_lists.keys()) == [0, 1, 2, 3]
    assert journey.lists[0] == journey.intended_lists[0]


def test_home_list_valid():
    for journey in generate_journeys(10, SEED):
        home = journey.lists[0]
        drugs = [e.drug for e in home]
        assert len(drugs) == len(set(drugs))
        assert 4 <= len(drugs) <= 8
        for entry in home:
            assert entry.dose in FORMULARY[entry.drug]["doses"]
            assert entry.freq == FORMULARY[entry.drug]["freq"]


def test_ledger_entries_valid():
    for journey in generate_journeys(10, SEED):
        for entry in journey.ledger:
            assert entry.transition in (1, 2, 3)
            assert entry.action in ("stop", "start", "dose_change", "substitute")
            assert entry.reason


def test_faults_valid_types_and_transitions():
    for journey in generate_journeys(15, SEED):
        for fault in journey.faults:
            assert fault.fault_type in FAULT_TYPES
            assert fault.transition in (1, 2, 3)


def test_at_most_one_fault_per_drug():
    for journey in generate_journeys(15, SEED):
        involved = []
        for fault in journey.faults:
            involved.append(fault.drug)
            if fault.other_drug is not None:
                involved.append(fault.other_drug)
        assert len(involved) == len(set(involved))


def test_faults_avoid_same_transition_intentional_changes():
    for journey in generate_journeys(15, SEED):
        for fault in journey.faults:
            involved = {fault.drug}
            if fault.other_drug is not None:
                involved.add(fault.other_drug)
            for entry in journey.ledger:
                if entry.transition != fault.transition:
                    continue
                assert entry.drug not in involved
                if entry.to_drug is not None:
                    assert entry.to_drug not in involved


def test_resurrection_follows_an_earlier_stop():
    seen = 0
    for journey in generate_journeys(40, SEED):
        for fault in journey.faults:
            if fault.fault_type != "resurrection":
                continue
            seen += 1
            stops = [
                e
                for e in journey.ledger
                if e.transition < fault.transition
                and (
                    (e.action == "stop" and e.drug == fault.drug)
                    or (e.action == "substitute" and e.drug == fault.drug)
                )
            ]
            assert stops, fault
    assert seen > 0


def test_substitution_incoming_same_class():
    seen = 0
    for journey in generate_journeys(40, SEED):
        for fault in journey.faults:
            if fault.fault_type == "substitution":
                seen += 1
                assert fault.other_drug is not None
                assert drug_class(fault.other_drug) == drug_class(fault.drug)
    assert seen > 0


def test_correction_only_after_birth():
    for journey in generate_journeys(15, SEED):
        for fault in journey.faults:
            if fault.corrected_at is not None:
                assert fault.corrected_at > fault.transition


def test_clean_journeys_chart_matches_intended():
    for journey in generate_journeys(8, SEED, fault_scale=0.0):
        assert journey.faults == []
        for step in (0, 1, 2, 3):
            charted = sorted(
                (e.drug, e.dose, e.freq) for e in journey.lists[step]
            )
            intended = sorted(
                (e.drug, e.dose, e.freq) for e in journey.intended_lists[step]
            )
            assert charted == intended


def test_batch_patient_ids():
    journeys = generate_journeys(5, SEED)
    assert [j.patient_id for j in journeys] == [0, 1, 2, 3, 4]


def test_demo_journey_is_rich():
    journey = demo_journey(SEED)
    types = set(f.fault_type for f in journey.faults)
    assert len(journey.faults) >= 3
    assert "resurrection" in types
    surviving = [
        i for i in ground_truth_instances(journey) if i["survives"]
    ]
    assert len(surviving) >= 2
