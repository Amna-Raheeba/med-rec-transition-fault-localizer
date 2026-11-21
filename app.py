"""Streamlit dashboard for med-rec-transition-fault-localizer.

Three tabs:
1. Journey genealogy -- one seeded patient journey: the four
   charted lists, the reason ledger, the planted ground truth and
   the localizer's reconstructed genealogy side by side.
2. Localisation -- stored headline results: birth-transition
   accuracy for the localizer (full lists), the localizer with the
   transfer list missing, and the blame-last-transition baseline,
   plus per-type accuracy.
3. Evaluation -- detection vs end-to-end diffing, and the price of
   a double-check placed at each transition (survivors and chart
   exposure per journey).

Run: streamlit run app.py
"""

import json
import os

import pandas as pd
import streamlit as st

from med_rec.evaluate import DEFAULT_CONFIG
from med_rec.generate import generate_journeys
from med_rec.localize import ground_truth_instances, localize
from med_rec.models import STEP_NAMES, TRANSITION_NAMES, journey_from_dict, journey_to_dict

st.set_page_config(
    page_title="Med-Rec Transition Fault Localizer", layout="wide"
)

SEED = DEFAULT_CONFIG["seed"]


@st.cache_data
def load_journeys(n=20):
    journeys = generate_journeys(n, SEED)
    return [journey_to_dict(j) for j in journeys]


@st.cache_data
def load_results():
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "results", "evaluation.json"
    )
    if not os.path.exists(path):
        return None
    with open(path) as handle:
        return json.load(handle)


st.title("Med-Rec Transition Fault Localizer")
st.caption(
    "Where was this error born? Each medication carries a lineage "
    "through home, admission, transfer and discharge lists; the "
    "localizer assigns every surviving discrepancy to the "
    "transition that introduced it."
)

tab1, tab2, tab3 = st.tabs(["Journey genealogy", "Localisation", "Evaluation"])

with tab1:
    journeys = [journey_from_dict(d) for d in load_journeys()]
    idx = st.slider("Patient", 0, len(journeys) - 1, 0)
    journey = journeys[idx]
    cols = st.columns(4)
    for step in (0, 1, 2, 3):
        with cols[step]:
            st.subheader(STEP_NAMES[step])
            rows = [
                {"drug": e.drug, "dose": e.dose, "per day": e.freq}
                for e in journey.lists[step]
            ]
            st.dataframe(pd.DataFrame(rows), hide_index=True)
    st.subheader("Reason ledger (intentional changes)")
    if journey.ledger:
        ledger_rows = [
            {
                "transition": TRANSITION_NAMES[e.transition],
                "action": e.action,
                "drug": e.drug,
                "reason": e.reason,
            }
            for e in journey.ledger
        ]
        st.dataframe(pd.DataFrame(ledger_rows), hide_index=True)
    else:
        st.write("No intentional changes in this journey.")
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Ground truth (planted)")
        truth_rows = [
            {
                "drug": i["drug"],
                "type": i["fault_type"],
                "born at": TRANSITION_NAMES[i["birth"]],
                "survives": i["survives"],
            }
            for i in ground_truth_instances(journey)
        ]
        if truth_rows:
            st.dataframe(pd.DataFrame(truth_rows), hide_index=True)
        else:
            st.write("No faults planted in this journey.")
    with col_b:
        st.subheader("Localizer genealogy")
        found_rows = [
            {
                "drug": i["drug"],
                "type": i["fault_type"],
                "born at": TRANSITION_NAMES[i["birth"]],
                "survives": i["survives"],
            }
            for i in localize(journey)
        ]
        if found_rows:
            st.dataframe(pd.DataFrame(found_rows), hide_index=True)
        else:
            st.write("No discrepancies found.")

with tab2:
    results = load_results()
    if results is None:
        st.write("No stored results yet. Run: python -m med_rec evaluate")
    else:
        loc = results["localization"]
        st.subheader("Birth-transition accuracy (surviving discrepancies)")
        acc_df = pd.DataFrame(
            {
                "method": [
                    "localizer (full lists)",
                    "localizer (transfer list missing)",
                    "blame last transition",
                ],
                "accuracy": [
                    loc["localizer_full"]["accuracy"],
                    loc["localizer_missing_transfer"]["accuracy"],
                    loc["blame_last_transition"]["accuracy"],
                ],
            }
        ).set_index("method")
        st.bar_chart(acc_df)
        st.dataframe(acc_df)
        st.subheader("Per-type accuracy (localizer, full lists)")
        per_type = loc["localizer_full"]["per_type"]
        type_rows = [
            {
                "type": fault_type,
                "accuracy": scores["accuracy"],
                "n": scores["n"],
            }
            for fault_type, scores in sorted(per_type.items())
        ]
        st.dataframe(pd.DataFrame(type_rows), hide_index=True)
        st.caption(
            "With every intermediate list present, step-level "
            "diffing against the ledger recovers each discrepancy's "
            "birth transition exactly on this seeded corpus; the "
            "measured findings are the degradations -- one missing "
            "snapshot, end-to-end diffing, and blame-the-last-"
            "transition all lose the genealogy."
        )

with tab3:
    results = load_results()
    if results is None:
        st.write("No stored results yet. Run: python -m med_rec evaluate")
    else:
        corpus = results["corpus"]
        st.subheader("Corpus")
        st.write(
            "%d journeys, %d faults injected, %d surviving to "
            "discharge (%.2f per journey)."
            % (
                corpus["n_journeys"],
                corpus["faults_injected"],
                corpus["instances_surviving"],
                corpus["mean_surviving_per_journey"],
            )
        )
        st.subheader("Detection at discharge")
        det_rows = [
            {
                "method": name,
                "precision": scores["precision"],
                "recall": scores["recall"],
                "F1": scores["f1"],
            }
            for name, scores in sorted(results["detection"].items())
        ]
        st.dataframe(pd.DataFrame(det_rows), hide_index=True)
        st.subheader(
            "Double-check pricing (efficacy %.2f)"
            % results["config"]["check_efficacy"]
        )
        inv = results["interventions"]
        order = [
            "no_check",
            "check_at_admission",
            "check_at_transfer",
            "check_at_discharge",
        ]
        inv_rows = [
            {
                "placement": name,
                "survivors / journey": inv[name][
                    "mean_survivors_per_journey"
                ],
                "exposure steps / journey": inv[name][
                    "mean_exposure_steps_per_journey"
                ],
            }
            for name in order
        ]
        inv_df = pd.DataFrame(inv_rows).set_index("placement")
        st.dataframe(inv_df)
        st.bar_chart(inv_df[["survivors / journey"]])
        st.bar_chart(inv_df[["exposure steps / journey"]])
        st.caption(
            "Checking at discharge leaves the fewest errors in the "
            "discharge list but lets them live in the chart all "
            "stay; checking at transfer minimises exposure while "
            "still catching everything born before it."
        )
