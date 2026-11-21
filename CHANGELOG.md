# Changelog

## 0.1.0 — 2026-11-21

- Initial release.
- Seeded journey generator: synthetic patients whose medication
  lists evolve through home, admission, transfer and discharge,
  with intentional changes recorded in a reason ledger and
  unintentional discrepancies (omission, dose drift, duplication,
  substitution, addition, resurrection of a stopped drug) planted
  at known transitions, plus probabilistic pharmacist-review
  corrections.
- Discrepancy genealogy: a localizer that reconstructs the
  expected lists from the home list and ledger, diffs consecutive
  lists with genealogy-aware substitution pairing, and assigns
  each surviving discrepancy its birth transition.
- Baselines: blame-the-last-transition, and end-to-end
  home-vs-discharge diffing (blind to resurrections, flags
  intentional changes).
- Missing-snapshot condition: localisation is re-scored with the
  transfer list withheld, pricing the lost genealogy.
- Intervention pricing: a double-check placed at admission,
  transfer or discharge, scored by discrepancies surviving to
  discharge and by chart exposure steps.
- Headline evaluation on 120 seeded journeys, CLI, Streamlit
  dashboard, and a reproduce script with a headline-drift guard.
