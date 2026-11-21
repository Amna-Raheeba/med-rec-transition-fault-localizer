"""Med-Rec Transition Fault Localizer.

A seeded simulator and auditor for medication reconciliation
across care transitions: every medication carries a lineage
through the home, admission, transfer and discharge lists, planted
discrepancies are injected at known transitions, and a localizer
assigns each surviving discrepancy to its birth transition -- a
discrepancy genealogy -- benchmarked against blame-the-last-
transition and end-to-end diffing, with double-check interventions
priced by placement.

Author: Amna Raheeba
"""

__version__ = "0.1.0"
