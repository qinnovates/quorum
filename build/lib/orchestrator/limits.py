"""Run limits and subagent spawn caps.

Limits are enforced in code. A refused spawn is recorded with its reason
and never silently skipped, so a stopped run says why it stopped.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class SpawnRefused(RuntimeError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"spawn refused: {reason}")


@dataclass(frozen=True)
class RunLimits:
    token_budget: int = 200_000
    max_agents: int = 8
    max_depth: int = 2
    max_output_tokens: int = 2_000


@dataclass
class RunBudget:
    limits: RunLimits
    spent_tokens: int = 0
    agents_spawned: int = 0
    refusals: list[str] = field(default_factory=list)

    def remaining_tokens(self) -> int:
        return max(0, self.limits.token_budget - self.spent_tokens)

    def clamp_output(self, requested: int) -> int:
        """Per-agent output cap, and never more than the budget has left."""
        remaining = self.remaining_tokens()
        if remaining == 0:
            reason = "token budget exhausted"
            self.refusals.append(reason)
            raise SpawnRefused(reason)
        return max(1, min(requested, self.limits.max_output_tokens, remaining))

    def authorize_spawn(self, depth: int, estimated_tokens: int) -> None:
        """Raise SpawnRefused (and record why) if the spawn breaks a limit."""
        reason = None
        if self.agents_spawned >= self.limits.max_agents:
            reason = f"max_agents={self.limits.max_agents} reached"
        elif depth > self.limits.max_depth:
            reason = f"depth {depth} exceeds max_depth={self.limits.max_depth}"
        elif estimated_tokens > self.remaining_tokens():
            reason = (
                f"estimated {estimated_tokens} tokens exceeds remaining "
                f"budget {self.remaining_tokens()}"
            )
        if reason is not None:
            self.refusals.append(reason)
            raise SpawnRefused(reason)
        self.agents_spawned += 1

    def charge(self, tokens: int) -> None:
        self.spent_tokens += max(0, tokens)

    def exhausted(self) -> bool:
        return self.remaining_tokens() == 0


# Starting points, not measured results. Override them in config.
DEFAULT_PHASE_SHARES = {"independent": 0.5, "challenge": 0.3, "judge": 0.2}
STAKES_PROFILES = {
    "low": {"budget_share": 0.25, "panel_size": 3},
    "medium": {"budget_share": 0.5, "panel_size": 5},
    "high": {"budget_share": 1.0, "panel_size": 7},
}


@dataclass
class PhaseBudgets:
    """Separate allowances, so early work cannot consume the judge's reserve."""

    allowance: dict[str, int]
    spent: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_stakes(cls, total: int, stakes: str, shares: dict[str, float]) -> "PhaseBudgets":
        if abs(sum(shares.values()) - 1.0) > 1e-9:
            raise ValueError("phase shares must add up to 1")
        run_total = int(total * STAKES_PROFILES[stakes]["budget_share"])
        return cls({phase: int(run_total * share) for phase, share in shares.items()})

    def remaining(self, phase: str) -> int:
        return max(0, self.allowance.get(phase, 0) - self.spent.get(phase, 0))

    def authorize(self, phase: str, estimated_tokens: int) -> None:
        if estimated_tokens > self.remaining(phase):
            raise SpawnRefused(
                f"phase {phase} needs {estimated_tokens} tokens, {self.remaining(phase)} remain"
            )

    def charge(self, phase: str, tokens: int) -> None:
        self.spent[phase] = self.spent.get(phase, 0) + max(0, tokens)
