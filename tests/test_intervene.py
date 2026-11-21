from med_rec.generate import generate_journeys
from med_rec.intervene import price_interventions, simulate_check
from med_rec.localize import ground_truth_instances

SEED = 20261121


def _truth_totals(journey):
    survivors = 0
    exposure = 0
    for inst in ground_truth_instances(journey):
        exposure += len(inst["present_steps"])
        if inst["survives"]:
            survivors += 1
    return survivors, exposure


def test_no_check_matches_ground_truth():
    for journey in generate_journeys(6, SEED):
        result = simulate_check(journey, None, 0.8, SEED)
        survivors, exposure = _truth_totals(journey)
        assert result["survivors"] == survivors
        assert result["exposure_steps"] == exposure


def test_discharge_check_perfect_efficacy_catches_all_survivors():
    for journey in generate_journeys(6, SEED):
        result = simulate_check(journey, 3, 1.0, SEED)
        assert result["survivors"] == 0


def test_zero_efficacy_equals_no_check():
    for journey in generate_journeys(6, SEED):
        none = simulate_check(journey, None, 0.0, SEED)
        for placement in (1, 2, 3):
            result = simulate_check(journey, placement, 0.0, SEED)
            assert result["survivors"] == none["survivors"]
            assert result["exposure_steps"] == none["exposure_steps"]


def test_admission_check_perfect_efficacy_leaves_later_births():
    for journey in generate_journeys(6, SEED):
        result = simulate_check(journey, 1, 1.0, SEED)
        later = sum(
            1
            for inst in ground_truth_instances(journey)
            if inst["survives"] and inst["birth"] > 1
        )
        assert result["survivors"] == later


def test_check_is_deterministic():
    journey = generate_journeys(1, SEED)[0]
    a = simulate_check(journey, 2, 0.8, SEED)
    b = simulate_check(journey, 2, 0.8, SEED)
    assert a == b


def test_price_interventions_structure():
    journeys = generate_journeys(10, SEED)
    priced = price_interventions(journeys, 0.8, SEED)
    assert set(priced) == {
        "no_check",
        "check_at_admission",
        "check_at_transfer",
        "check_at_discharge",
    }
    for name, values in priced.items():
        assert values["mean_survivors_per_journey"] >= 0
        assert values["mean_exposure_steps_per_journey"] >= 0


def test_discharge_check_never_worse_than_no_check_on_survivors():
    journeys = generate_journeys(10, SEED)
    priced = price_interventions(journeys, 0.8, SEED)
    assert (
        priced["check_at_discharge"]["mean_survivors_per_journey"]
        <= priced["no_check"]["mean_survivors_per_journey"]
    )


def test_any_check_never_increases_exposure():
    journeys = generate_journeys(10, SEED)
    priced = price_interventions(journeys, 0.8, SEED)
    base = priced["no_check"]["mean_exposure_steps_per_journey"]
    for name in (
        "check_at_admission",
        "check_at_transfer",
        "check_at_discharge",
    ):
        assert priced[name]["mean_exposure_steps_per_journey"] <= base
