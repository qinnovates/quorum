"""Pair each model family with one source, so that the total weight is highest.

A greedy pass can drop a family's second source and under-score an honest
option, which hands the verdict to its rival. This is the Hungarian method.
"""

from __future__ import annotations

UNMATCHED = -1


def best_assignment(weights: list[list[float]]) -> list[int]:
    """Column chosen for each row, or UNMATCHED. Each column is used at most once."""
    if not weights or not weights[0]:
        return [UNMATCHED] * len(weights)
    rows, columns = len(weights), len(weights[0])
    size = max(rows, columns)
    cost = [[-(weights[r][c]) if r < rows and c < columns else 0.0 for c in range(size)] for r in range(size)]
    row_for_column = _solve(cost, size)
    chosen = [UNMATCHED] * rows
    for column, row in enumerate(row_for_column):
        if row < rows and column < columns and weights[row][column] > 0:
            chosen[row] = column
    return chosen


def _solve(cost: list[list[float]], size: int) -> list[int]:
    """Minimum-cost assignment on a square matrix. Returns the row for each column."""
    row_potential, column_potential = [0.0] * (size + 1), [0.0] * (size + 1)
    matched_row, previous = [0] * (size + 1), [0] * (size + 1)
    for row in range(1, size + 1):
        matched_row[0], column = row, 0
        slack, used = [float("inf")] * (size + 1), [False] * (size + 1)
        while matched_row[column]:
            used[column] = True
            current, delta, next_column = matched_row[column], float("inf"), 0
            for candidate in range(1, size + 1):
                if not used[candidate]:
                    reduced = cost[current - 1][candidate - 1] - row_potential[current] - column_potential[candidate]
                    if reduced < slack[candidate]:
                        slack[candidate], previous[candidate] = reduced, column
                    if slack[candidate] < delta:
                        delta, next_column = slack[candidate], candidate
            for candidate in range(size + 1):
                if used[candidate]:
                    row_potential[matched_row[candidate]] += delta
                    column_potential[candidate] -= delta
                else:
                    slack[candidate] -= delta
            column = next_column
        while column:
            matched_row[column] = matched_row[previous[column]]
            column = previous[column]
    return [matched_row[column] - 1 for column in range(1, size + 1)]
