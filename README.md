# Med-Rec Transition Fault Localizer

Where was this error born? A seeded simulator of medication
reconciliation that traces every medication's **lineage** through
the home, admission, transfer and discharge lists, and assigns
each surviving discrepancy to the **transition that introduced
it** — a discrepancy genealogy, benchmarked against the ways
errors are actually attributed today.

## 1. What it is

When a patient's medication list is wrong at discharge, the usual
question is *what* is wrong. The operationally useful question is
*where it went wrong*: which handoff introduced the error decides
where a double-check belongs, which team owns the fix, and how
long the wrong list was the working list. Observational studies
can count reconciliation errors and classify them by type; they
cannot attribute each one to its introduction point, because real
charts do not record the moment an error was born.

This tool can, because it generates the truth first. It:

1. simulates synthetic patient journeys — home list → admission
   orders → transfer orders → discharge list — with intentional
   changes documented in a reason ledger (stops, dose
   adjustments, formulary swaps, each with a reason);
2. plants unintentional discrepancies at known transitions —
   omission, dose drift, duplication, substitution, addition, and
   resurrection of a drug that was intentionally stopped — and
   lets a modelled pharmacist review correct some of them
   downstream;
3. runs a localizer that sees only the lists and the ledger,
   reconstructs what each list *should* have been, diffs
   consecutive lists, and assigns every surviving discrepancy a
   birth transition and a type;
4. prices interventions: a double-check placed at admission,
   transfer or discharge, scored by how many discrepancies still
   reach the discharge list and how long the wrong list was live.

Everything is offline, deterministic and seeded. Pure Python
standard library; no API keys, no model downloads, no network.
All clinical content is synthetic — no real patient data anywhere.

## 2. The novel mechanism

**Discrepancy genealogy.** Every medication carries a lineage
record through the four lists. The localizer replays the reason
ledger onto the home list to reconstruct the expected list at
each step, then reads the divergence between expected and charted
lists step by step. A discrepancy is an instance with a birth
transition (where its signature first appears), a lifespan (the
lists it appears in), and an outcome (corrected downstream, or
surviving to discharge). Intentional change is separated from
error by the ledger, not by guessing.

**Genealogy-aware substitution pairing.** When a drug vanishes
and another appears, is it a substitution or an omission plus an
addition? The localizer pairs a missing drug with an extra drug
of the same class only at the step where the disappearance is
new, and only with an extra drug that is itself new in the chart
(or already paired with it). An extra drug that has been sitting
in the chart since an earlier step is an old addition, not a
substitution partner — pairing is an event, not a state. This one
rule is what keeps the genealogy stable across steps.

**Priced absence.** The benchmark also runs the localizer with
the transfer list withheld — a routine real-world gap — and
measures exactly what the missing snapshot costs: instances first
visible after the gap can only be certified "born by discharge",
and accuracy falls accordingly.

## 3. Prior art and the differentiator

Pippins et al. classified and predicted reconciliation errors
observationally (72% arising from history-taking, the most harm
potential at discharge); e-medrec meta-analyses measure the
effect of interventions on real wards. Both are valuable and both
stop where this starts: no seeded simulator attributes each
discrepancy to its introduction point against known ground truth,
no localizer is benchmarked, and intervention placement is never
priced per transition against a genealogy. (Distinct from
gold-swap-component-attribution: that swaps AI pipeline
components; this traces medication lineage through a clinical
process — different domain, data, and method.)

## 4. Headline results (measured)

120 seeded patient journeys (seed 20261121; reproduce with
`python scripts/reproduce_results.py`). Full numbers in
`results/HEADLINE.md` and `results/evaluation_summary.md`.

**The corpus:** 374 discrepancies planted; **316 survive to the
discharge list** (2.63 per journey) — by type: 88 omissions, 78
dose drifts, 58 additions, 40 substitutions, 35 duplications, 17
resurrections. The rest were caught by the modelled downstream
review before discharge.

**Birth-transition localisation (surviving discrepancies):**

| Method | Accuracy |
|---|---|
| Localizer (all lists + ledger) | **1.000** (316/316) |
| Localizer (transfer list missing) | 0.677 (214/316) |
| Blame the last transition | 0.386 (122/316) |

With every intermediate list present and a complete ledger,
step-level diffing recovers each discrepancy's birth exactly —
that perfect score validates the machinery against ground truth,
and it is the *degradations* that carry the findings. Lose one
snapshot and a third of the genealogies are gone: anything born
at transfer is indistinguishable from anything born at discharge.
Blaming the last transition — what a reviewer holding only the
discharge list implicitly does — is right only for the 39% of
errors actually born there.

**Detection at discharge (is the final list wrong, and how):**

| Method | Precision | Recall | F1 |
|---|---|---|---|
| Localizer | 1.000 | 1.000 | **1.000** |
| End-to-end diff (home vs discharge) | 0.401 | 0.763 | 0.526 |

The end-to-end diff fails in both directions: it flags documented,
intentional changes as errors (precision 0.401), and it is blind
to resurrections — a stopped drug that comes back is on both the
home and discharge lists, so the diff sees nothing — and to any
error that a later intentional change happens to cancel out.

**Intervention pricing (double-check efficacy 0.80):**

| Placement | Survivors / journey | Exposure steps / journey |
|---|---|---|
| No check | 2.63 | 5.65 |
| Check at admission | 2.03 | 3.48 |
| Check at transfer | 1.22 | **2.62** |
| Check at discharge | **0.52** | 3.53 |

No placement dominates. Checking at discharge leaves the cleanest
discharge list but lets every early error live in the chart for
the whole stay (exposure 3.53, barely better than checking at
admission). Checking at transfer minimises exposure *and* beats
the admission check on survivors, because it sees everything born
in the first two transitions while there is still a step left to
protect. Where the check belongs depends on which price you are
paying — and now both prices are numbers.

## 5. How it works

1. `med_rec/generate.py` — the journey generator: sampled home
   lists, ledger-documented intentional changes, planted faults
   at declared rates, probabilistic review corrections.
2. `med_rec/localize.py` — expected-list reconstruction from the
   ledger, per-step signatures with genealogy-aware substitution
   pairing, instance building and birth assignment; also the
   blame-last and end-to-end baselines.
3. `med_rec/intervene.py` — the double-check simulation: catch
   probability applied to discrepancies present at the chosen
   transition, survivors and exposure priced per placement.
4. `med_rec/evaluate.py` — the headline experiment, result
   files, and the drift guard the reproduce script checks.

## 6. Run it

```bash
pip install -r requirements.txt
python -m med_rec demo        # one journey, genealogised
python -m med_rec audit       # localizer scores on a seeded batch
python -m med_rec evaluate    # full experiment, writes results/
python scripts/reproduce_results.py   # verify the headline numbers
python scripts/build_cases.py         # rebuild data/demo_journey.json
streamlit run app.py          # dashboard: genealogy, localisation, pricing
pytest                        # 64 tests
```

## 7. Honest limits

- All journeys are synthetic and seeded. Fault rates, the review
  correction rate (0.15 per transition) and check efficacy (0.80)
  are declared parameters, not measurements of any real ward,
  EHR or clinician population; the numbers quantify the
  localisation and pricing machinery under those parameters, not
  any hospital's error profile.
- The localizer's perfect score is a property of complete
  information: every intermediate list present, and a ledger that
  documents every intentional change. Real charts have missing
  lists and undocumented changes; the missing-transfer condition
  (0.677) is the first step of that degradation, not the last.
- Declared generator simplifications keep the ground-truth
  genealogy unambiguous: intentional changes never target a drug
  carrying a planted fault (so faults are cleared only by review
  corrections, never as a side effect of a later order), each
  fault type fires at most once per transition, and the generator
  does not plant an addition or resurrection in the class of a
  drug omitted at the same transition — a combination no
  reviewer, human or algorithmic, could tell apart from a
  substitution.
- A medication is a (drug, dose, frequency) line: no routes,
  no PRN orders, no IV infusions, no patient-level covariates.
  Exposure is counted in charted lists, not hours.

## 8. Layout

```
med_rec/        generator, localizer, interventions, evaluation, CLI
data/           stored demo journey (regenerable)
examples/       runnable audit example + captured sample report
notebooks/      01 demo run, 02 evaluation experiment (runnable .py)
scripts/        build_cases.py, reproduce_results.py (drift guard)
results/        evaluation.json/.csv, summary and headline
tests/          64 tests
app.py          Streamlit dashboard (3 tabs)
```

Author: Amna Raheeba. MIT license.
