"""Family-diversity guard.

The guard counts distinct model families among panelists that answered.
Below the configured floor the run fails loudly with FAILED_DIVERSITY. It
does not fall back to an all-Claude panel.
"""

from __future__ import annotations

from dataclasses import dataclass

from .providers import UNATTRIBUTED_FAMILIES, Result

FAILED_DIVERSITY = "FAILED_DIVERSITY"


class DiversityError(RuntimeError):
    """Raised when fewer than `min_families` families answered."""

    def __init__(self, report: "FamilyReport"):
        self.report = report
        super().__init__(
            f"{FAILED_DIVERSITY}: {len(report.answered)} of {report.required} "
            f"required families answered ({', '.join(sorted(report.answered)) or 'none'})"
        )


@dataclass(frozen=True)
class FamilyReport:
    answered: frozenset[str]
    failed: tuple[str, ...]
    required: int

    @property
    def passed(self) -> bool:
        return len(self.answered) >= self.required


def family_report(results: list[Result], min_families: int) -> FamilyReport:
    """Summarise attributed families that answered. Only `ok` results count."""
    answered = frozenset(
        r.family for r in results if r.ok and r.family not in UNATTRIBUTED_FAMILIES
    )
    failed = tuple(sorted({f"{r.family}:{r.model_id}" for r in results if not r.ok}))
    return FamilyReport(answered=answered, failed=failed, required=min_families)


def enforce_family_floor(results: list[Result], min_families: int) -> FamilyReport:
    """Return the report if the floor is met; otherwise raise DiversityError."""
    report = family_report(results, min_families)
    if not report.passed:
        raise DiversityError(report)
    return report
