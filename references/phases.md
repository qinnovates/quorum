## How It Works

### Default (5 agents)

1. **Setup + Vagueness Gate** — Supervisor analyzes the question. If the prompt is too vague to produce a useful verdict (no scope, no constraints, no success criteria), the supervisor asks 2-4 targeted clarifying questions before spawning agents. Picks 5 SMEs with diverse perspectives. Minimum 2 challenger.
2. **Independent work** — All agents work in parallel. No one sees anyone else's output.
3. **Triage** — Supervisor reads all reports, builds claim pool (text + source + direction for every factual claim), identifies key disagreements.
4. **Cross-review** — Debate pairs argue. Devil's Advocate challenges the majority. Critics must counter-propose, not just attack.
5. **Synthesis + Drift Detection** — Supervisor authors the verdict, then diffs every claim against the Phase 1 claim pool. Unsourced expansions (DRIFT) are auto-corrected: web-searched, sourced, or removed. Inverted findings are corrected to match source direction. Resolved drift diff included in verdict.
6. **Validation** — Web fact-check (preferred) or Challenger review.
7. **Final report** — What survived, what's disputed, drift diff (auto-corrected + unresolved), what to do next.

### Max (7-15 recommended, scalable)

`--max` always runs **challenge-driven convergence** — the full panel iterates across rounds until a solution survives sustained attack. The supervisor also auto-selects the right structure.

**Scaling beyond 15:**

By default, the supervisor picks 7-15 agents based on question complexity. To go higher:

```bash
# Supervisor picks agent count (7-15)
/quorum "question" --max

# You set the agent count explicitly
/quorum "question" --max --set 25

# Even larger — swarm architecture auto-engages at 20+
/quorum "question" --max --set 50
```

`--max --set N` combines deep deliberation (iterative rounds, convergence scoring) with custom scale. At 20+, swarm architecture auto-engages (MECE partitioning, environment coordination). The 15-agent recommended ceiling exists because conversational inequality increases with group size (Dunbar layer 1) — but for research landscapes, red-team exercises, or prediction markets, larger panels are justified.

**Challenge-driven convergence (always at --max):**

| Role | What They Do |
|------|-------------|
| **Proposer** | Goes first. Defends and adapts across rounds. |
| **Realist** | "This fails because X, and here's what survives X." Every criticism includes a survival path. |
| **Breaker** | Red-teams the proposal. Self-rates attacks. "I can't break this" = strongest signal. |
| **Synthesizer** | Reports what survived and what collapsed at checkpoints. |
| **Judge** | Neutral arbiter. Computes convergence score. Ends when C ≥ 0.8 (max 6 rounds). |

**Anti-duplication:** No repetition across rounds. "This won't work" is not allowed — must include what WOULD work. No free nihilism. 40/60 challenger ratio (Nemeth 2001, Liang 2023).

**Four outcomes:** CONVERGED (survived attack) / **VOTE** (near-consensus tiebreaker) / TENSION (irreducible tradeoff — user decides) / EXHAUSTED (diminishing returns).

**Structured Vote (near-consensus tiebreaker):**

When C* is in the close-call zone [0.65, 0.8) — positions are similar but not converged — agents cast a structured vote: position + confidence (1-10) + one-sentence rationale. Votes are **weighted by evidence quality and independence**, not raw headcount. A well-sourced vote from an independent agent counts more than an unsourced vote that echoes another agent. The supervisor uses the weighted result to inform (not override) the synthesis. Vote result is visible in the verdict. [Full spec →](docs/ARCHITECTURE.md#structured-vote-near-consensus-tiebreaker)

**Auto-selected structures (supervisor decides which to layer on):**
- **Teams** — if 3+ domains with different incentives. Teams deliberate internally, leads cross-challenge. Socrates questions weakest points, Plato audits evidence.
- **Dialectic** — if the question is binary or philosophical. 2 agents drill through contradiction across rounds.
- **Hackathon** — if the query is "build X" / "implement Y". Generates PRD with TDD + acceptance criteria, converse-stress-tests it, outputs the PRD for you to execute in the permission mode you choose.

### Set N (user-defined scale)

At 20+ agents, swarm architecture auto-engages:
- **Partition Engine** — MECE taxonomy, each agent gets a unique territory
- **Environment Server** — shared state, agents POST/REACT/HANDOFF/SHIFT (prompt-orchestrated, not a runtime service)
- **Pattern Detection** — supervisor reads emerging patterns, not individual reports
- **Prediction mode** — auto-detected for forecasting questions ("will X happen by Y?")
