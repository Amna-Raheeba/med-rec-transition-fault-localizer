"""Plain-text rendering of one journey: the four lists, the
ledger, the planted ground truth, and the localizer's genealogy."""

from .localize import ground_truth_instances, localize
from .models import STEP_NAMES, TRANSITION_NAMES


def _render_list(entries):
    if not entries:
        return ["    (empty)"]
    return ["    - %s" % entry.text() for entry in entries]


def render_journey_report(journey):
    lines = []
    lines.append(
        "Patient %d: home -> admission -> transfer -> discharge"
        % journey.patient_id
    )
    lines.append("")
    lines.append("Charted lists:")
    for step in (0, 1, 2, 3):
        lines.append("  %s:" % STEP_NAMES[step])
        lines.extend(_render_list(journey.lists[step]))
    lines.append("")
    lines.append("Reason ledger (intentional changes):")
    if not journey.ledger:
        lines.append("  (none)")
    for entry in journey.ledger:
        detail = ""
        if entry.action == "dose_change":
            detail = " -> dose %s" % entry.new_dose
        elif entry.action == "start":
            detail = " at dose %s" % entry.new_dose
        elif entry.action == "substitute":
            detail = " -> %s at dose %s" % (entry.to_drug, entry.to_dose)
        lines.append(
            "  - [%s] %s %s%s (%s)"
            % (
                TRANSITION_NAMES[entry.transition],
                entry.action,
                entry.drug,
                detail,
                entry.reason,
            )
        )
    lines.append("")
    lines.append("Ground truth (planted discrepancies):")
    truth = ground_truth_instances(journey)
    if not truth:
        lines.append("  (none)")
    for inst in truth:
        status = (
            "survives to discharge"
            if inst["survives"]
            else "corrected before discharge"
        )
        other = (
            " (incoming: %s)" % inst["other_drug"] if inst["other_drug"] else ""
        )
        lines.append(
            "  - %s: %s, born at %s, present in steps %s -- %s%s"
            % (
                inst["drug"],
                inst["fault_type"],
                TRANSITION_NAMES[inst["birth"]],
                inst["present_steps"],
                status,
                other,
            )
        )
    lines.append("")
    lines.append("Localizer genealogy (lists + ledger only):")
    found = localize(journey)
    if not found:
        lines.append("  (no discrepancies found)")
    for inst in found:
        status = (
            "survives to discharge" if inst["survives"] else "gone by discharge"
        )
        lines.append(
            "  - %s: %s, born at %s -- %s"
            % (
                inst["drug"],
                inst["fault_type"],
                TRANSITION_NAMES[inst["birth"]],
                status,
            )
        )
    return "\n".join(lines)
