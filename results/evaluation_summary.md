# Evaluation summary

Seed 20261121, 120 seeded patient journeys.

## Corpus

- Faults injected: 374; instances appearing in the chart: 374; surviving to discharge: 316 (2.63 per journey)
- Surviving by type: addition 58, dose_drift 78, duplication 35, omission 88, resurrection 17, substitution 40

## Birth-transition localisation accuracy

- localizer_full: 1.000 (316/316 correct, 316 matched)
- localizer_missing_transfer: 0.677 (214/316 correct, 312 matched)
- blame_last_transition: 0.386 (122/316 correct, 316 matched)

## Per-type accuracy (localizer, full lists)

- addition: 1.000 (n=58)
- dose_drift: 1.000 (n=78)
- duplication: 1.000 (n=35)
- omission: 1.000 (n=88)
- resurrection: 1.000 (n=17)
- substitution: 1.000 (n=40)

## Detection at discharge (surviving discrepancies)

- end_to_end: P 0.401 / R 0.763 / F1 0.526
- localizer: P 1.000 / R 1.000 / F1 1.000

## Intervention pricing (double-check efficacy 0.80)

- no_check: 2.63 survivors/journey, 5.65 exposure steps/journey
- check_at_admission: 2.03 survivors/journey, 3.48 exposure steps/journey
- check_at_transfer: 1.22 survivors/journey, 2.62 exposure steps/journey
- check_at_discharge: 0.52 survivors/journey, 3.53 exposure steps/journey
