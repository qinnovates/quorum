"""Per-run token and cost ledger.

Prices are never hard-coded. They come from the config's pricing table,
which must be filled from current published rates. A model with no
configured price is reported as unpriced; its cost is not guessed.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .providers import Result


@dataclass(frozen=True)
class Price:
    input_per_mtok: float
    output_per_mtok: float


@dataclass(frozen=True)
class Entry:
    phase: str
    family: str
    model_id: str
    tokens_in: int
    tokens_out: int
    cost_usd: float | None
    latency_s: float
    ok: bool
    usage_known: bool = True


@dataclass
class Ledger:
    pricing: dict[str, Price] = field(default_factory=dict)
    entries: list[Entry] = field(default_factory=list)

    def record(self, phase: str, result: Result) -> Entry:
        price = self.pricing.get(result.model_id)
        cost = None
        if price is not None and result.usage_known:
            cost = (
                result.tokens_in * price.input_per_mtok
                + result.tokens_out * price.output_per_mtok
            ) / 1_000_000
        entry = Entry(
            phase=phase,
            family=result.family,
            model_id=result.model_id,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=cost,
            latency_s=result.latency_s,
            ok=result.ok,
            usage_known=result.usage_known,
        )
        self.entries.append(entry)
        return entry

    def total_tokens(self) -> int:
        return sum(e.tokens_in + e.tokens_out for e in self.entries)

    def by_model(self) -> dict[str, dict]:
        """Totals per model ID. `cost_usd` is None if any call was unpriced."""
        out: dict[str, dict] = defaultdict(
            lambda: {"calls": 0, "tokens": 0, "cost_usd": 0.0, "priced": True}
        )
        for e in self.entries:
            row = out[e.model_id]
            row["calls"] += 1
            row["tokens"] += e.tokens_in + e.tokens_out
            if e.cost_usd is None:
                row["priced"] = False
            else:
                row["cost_usd"] += e.cost_usd
        for row in out.values():
            if not row["priced"]:
                row["cost_usd"] = None
        return dict(out)

    def unpriced_models(self) -> list[str]:
        return sorted({e.model_id for e in self.entries if e.model_id not in self.pricing})

    def estimated_usage_models(self) -> list[str]:
        """Models whose token counts are estimates, so their cost is unknown."""
        return sorted({e.model_id for e in self.entries if not e.usage_known})
