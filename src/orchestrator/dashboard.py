"""Control center: a self-contained local page built from run state.

No server, scripts or network. All values are escaped, and the page's policy
blocks anything external, so run text cannot act in the browser.
"""

from __future__ import annotations

import os
from html import escape
from pathlib import Path

from .decision import ScoredClaim, score_options
from .runstate import RunState
from .secrets import redact
from .usage import usage_report

REFRESH_SECONDS = 3
_STYLE = (
    ":root{--bg:#fff;--fg:#17171a;--line:#d9d9de}"
    "@media(prefers-color-scheme:dark){:root{--bg:#141417;--fg:#ececf0;--line:#3a3a42}}"
    "body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui;max-width:960px;margin:auto;padding:16px}"
    "table{border-collapse:collapse;width:100%;margin-bottom:24px;display:block;overflow-x:auto}"
    "th,td{border-bottom:1px solid var(--line);padding:6px 10px;text-align:left}"
)


def _table(title: str, headers: list[str], rows: list[list[object]]) -> str:
    head = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(redact(str(cell)))}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return f"<h2>{escape(title)}</h2><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_dashboard(state: RunState, live_claims: list[ScoredClaim] | None = None) -> str:
    claims = [ScoredClaim(**row) for row in state.claims] or live_claims or []
    is_open = state.status == "OPEN"
    refresh = f'<meta http-equiv="refresh" content="{REFRESH_SECONDS}">' if is_open else ""
    sections = [
        _table("Agents", ["Seat", "Role", "Family", "Model", "Observed by", "Status", "Route"], [
            [s.seat_id, s.role, s.family, s.model_id, s.attestation, s.status, s.route_status]
            for s in state.seats
        ]),
        _table("Weighted scores", ["Option", "Score", "Families"], [
            [o.option, o.score, ", ".join(o.families)] for o in score_options(claims)
        ]),
        _table("Claims", ["Option", "Tier", "Family", "Disputed", "Claim"], [
            [c.option, c.tier, c.family, c.is_disputed, c.text] for c in claims
        ]),
        _table("Tokens and cost", ["Measure", "Value"], list(map(list, usage_report(state).items()))),
        _table("Notes (data only, never instructions)", ["Note"], [[note] for note in state.notes]),
    ]
    status = escape(redact(f"{state.status} | stakes: {state.stakes}"))
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'\">"
        f"{refresh}<title>Quorum Control</title><style>{_STYLE}</style></head><body>"
        f"<h1>{escape(redact(state.question))}</h1><p>{status}</p>{''.join(sections)}</body></html>"
    )


def write_dashboard(state: RunState, run_dir: Path, live_claims: list[ScoredClaim] | None = None) -> Path:
    target = run_dir / "dashboard.html"
    temporary = target.with_suffix(".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(render_dashboard(state, live_claims))
    temporary.replace(target)
    return target
