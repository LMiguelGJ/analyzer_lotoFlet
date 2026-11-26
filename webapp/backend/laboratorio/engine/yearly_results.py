"""Result per calendar year of a saved owned-laboratory run, derived when the run is read.

Nothing here is stored: session indices are relative to the draws the run replayed (ranked rows
inside the window), so the draw labels are rebuilt from the history and checked against the
stored run before any figure is reported.
"""

import numpy as np

_CLOSED = ("goal", "ruin", "timeout")


def eligible_labels(history, rankings, window_start: str, window_end: str) -> list[str]:
    """Labels of the draws a run replayed, in replay order (same rule as ``run_reference_lab``)."""
    labels = history.labels
    row_ids = np.asarray(rankings.row_ids, dtype=np.int64).tolist()
    return [labels[i] for i in row_ids if window_start <= labels[i] <= window_end]


def results_by_year(sessions, labels, *, capital, eligible_draws, first, last):
    """Per-year figures, ascending by year, or ``None`` when ``labels`` do not match the run.

    A session belongs to the year of its last draw: the closing draw of a closed session, the
    last evaluated draw of the open one. ``net`` is ``final_balance - capital`` summed over them.
    """
    if len(labels) != eligible_draws:
        return None
    if labels and (labels[0] != first or labels[-1] != last):
        return None
    years: dict[int, dict] = {}
    for session in sessions:
        end = session["end_index"]
        if not 0 <= end < len(labels):
            return None
        year = int(labels[end][:4])
        row = years.setdefault(
            year,
            {"year": year, "net": 0, "goals": 0, "ruins": 0, "timeouts": 0, "sessions_closed": 0},
        )
        row["net"] += session["final_balance"] - capital
        outcome = session["outcome"]
        if outcome in _CLOSED:
            row["sessions_closed"] += 1
            row[{"goal": "goals", "ruin": "ruins", "timeout": "timeouts"}[outcome]] += 1
    rows = [years[year] for year in sorted(years)]
    for row in rows:
        # Percentage points of the starting capital, like the other ``*_pct`` figures.
        row["return_pct"] = round(row["net"] * 100 / capital, 2)
    return rows
