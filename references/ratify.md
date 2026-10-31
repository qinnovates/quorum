## Ratify Mode (--ratify)

Human-in-the-loop approval gate. After the panel deliberates and produces a verdict, `--ratify` pauses for your review before the verdict is final. Composes with any tier.

```bash
# Review before acting on a high-stakes decision
/quorum "Should we open-source ClawFish's core engine?" --max --ratify

# Approve a PRD before executing it in Auto mode
/quorum "Build the obstacle detection pipeline for Spot" --max --ratify
```

### How --ratify Works

1. **Phases 0-7 run normally** (deliberation, synthesis, validation)
2. **Auditor pass** — A structurally independent agent reviews the verdict cold. It sees ONLY the original question and the final verdict — no phase history, no agent transcripts, no deliberation dynamics. Evaluates: logical coherence, evidence sufficiency, scope completeness, internal consistency, actionability. Outputs specific findings or confirms the verdict holds.
3. **Human review** — You see the verdict + auditor annotations. Three options:

```
  [a] Accept   — verdict is final
  [r] Refine   — inject a constraint, re-run Phase 3-7 (one revision)
  [x] Reject   — discard verdict, restart from Phase 0
```

4. **If you Refine** — Your constraint is injected as authoritative input. Phases 3-7 re-run once. The Auditor re-reviews. You get one final ACCEPT or REJECT. No further refinements — if it's still wrong, REJECT and reframe the question.

### Why One Auditor Pass, Not a Loop

Research (Schulz-Hardt et al. 2006): first structured revision captures the quality gain. Subsequent rounds show flat or negative returns. Iterative averaging introduces correlated error (Larrick & Soll 2006). The Auditor gets one shot. The human gets one refinement. Beyond that, the issue is upstream — re-deliberate with a better question.

### Composability (2x2)

| | Auto-accept | Human-ratified |
|---|---|---|
| **Quick (1 round)** | `/quorum "q"` | `/quorum "q" --ratify` |
| **Deep (multi-round)** | `/quorum "q" --max` | `/quorum "q" --max --ratify` |

`--max` controls how hard agents think. `--ratify` controls whether a human approves. Independent axes.

### Auditor Structural Independence

The Auditor is isolated from the panel's deliberation to prevent anchoring (Lorenz et al. 2011). It evaluates the verdict against the original question — not against the panel's internal reasoning. This is stronger than the Phase 5 validation gate (which operates within the same session context).

### Token Cost

| Config | Median | Multiplier vs base |
|--------|--------|--------------------|
| Base (no flags) | ~60K | 1.0x |
| `--ratify` | ~100K | 1.7x |
| `--max` | ~100K | 1.7x |
| `--max --ratify` | ~145K | 2.4x |
| `--diverse` | Use a multi-model panel through `quorum-run`. Requires setup and consent |
| `--max --diverse` | ~71K Claude + external | ~1.0x net |
| `--max --diverse --ratify` | ~71K + auditor + cold-review | ~1.1x net |
