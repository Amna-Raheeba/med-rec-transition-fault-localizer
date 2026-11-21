# Headline results

Discrepancy genealogy for medication reconciliation, measured on 120 seeded synthetic patient journeys (seed 20261121; reproduce with `python scripts/reproduce_results.py`).

- Of 374 planted discrepancies, **316 survive to the discharge list** (2.63 per journey) -- those are the errors the patient takes home.
- The localizer names the birth transition of a surviving discrepancy with accuracy **1.000**, vs **0.386** for blaming the last transition. With the transfer list missing, accuracy falls to **0.677** -- the price of one lost snapshot.
- Detection at discharge: localizer F1 **1.000** vs end-to-end home-vs-discharge diffing F1 **0.526** -- the end-to-end diff cannot see resurrections at all and flags intentional, documented changes as errors.
- A double-check (efficacy 0.80) at discharge leaves the fewest errors in the discharge list (**0.52** survivors per journey vs 2.63 unchecked) but the most chart exposure; a check at admission cuts exposure to **3.48** steps per journey (vs 5.65 unchecked) while missing everything born later.

Caveat: all journeys are synthetic and seeded. Fault rates, correction rates and check efficacy are declared parameters, not measurements of any real ward; the benchmark measures localisation and pricing machinery against known ground truth that observational reconciliation studies do not have.
