from med_rec.generate import demo_journey, generate_journey
from med_rec.report import render_journey_report

SEED = 20261121


def test_demo_report_sections():
    report = render_journey_report(demo_journey(SEED))
    assert "Charted lists:" in report
    assert "Reason ledger" in report
    assert "Ground truth" in report
    assert "Localizer genealogy" in report


def test_demo_report_names_transitions_and_types():
    report = render_journey_report(demo_journey(SEED))
    assert "home -> admission" in report
    assert "resurrection" in report
    assert "survives to discharge" in report


def test_clean_journey_report_shows_no_faults():
    journey = generate_journey(0, SEED, fault_scale=0.0)
    report = render_journey_report(journey)
    assert "Ground truth (planted discrepancies):" in report
    assert "(none)" in report
    assert "(no discrepancies found)" in report


def test_report_lists_home_medications():
    journey = demo_journey(SEED)
    report = render_journey_report(journey)
    for entry in journey.lists[0]:
        assert entry.drug in report
