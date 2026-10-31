> **Prompt mode only.** These scores are advisory and rest on unvalidated constants. They do not set the verdict in `quorum-run`, which uses evidence weighting. Never present C* as proof.

## Math-Based Reasoning Guarantees

### Convergence Formula (Converse Mode)

The Judge computes convergence score each round using three measurable signals:

```
C = (A × 0.6) + (D × 0.4)

Where:
  A = Agreement Growth    = |claims_held(r) ∩ claims_held(r-1)| / |claims_held(r-1)|
      (claim matching via semantic similarity, τ_match = 0.85 cosine threshold)
  D = Defense Success Rate = (attacks survived) / (attacks received)
      (attack = explicit contest of a claim; survived = claim persists despite attack)

Termination signal (not scored):
  N = Novelty Decay = 1 - (new arguments this round / new arguments round 1)
  If N > 0.9 for 2 consecutive rounds → EXHAUSTED (no new arguments, diminishing returns)

Thresholds:
  C* ≥ 0.8          → CONVERGED (solution is battle-tested)
  C* ∈ [0.65, 0.8)  → VOTE (near-consensus — structured ballot breaks tie)
  C* ∈ [0.5, 0.65)  → continue (still productive)
  C* < 0.5 after 3+ rounds → check for TENSION or EXHAUSTED
```

**Why these weights:** Agreement growth (0.6) is the primary signal — it directly measures whether critics are running out of attacks. Defense success (0.4) measures solution robustness under challenger pressure. Novelty decay (N) was removed from the score because it correlates >0.9 with A (as claims stabilize, new arguments also decline). N is retained as a termination signal — if agents stop producing new arguments for 2 consecutive rounds, the deliberation ends regardless of C.

### Cognitive Diversity Profiles (CDP)

Each agent gets a 3-axis cognitive profile that changes HOW they reason, not just what they say. Personas define WHAT an agent knows. CDP defines HOW the agent thinks.

**Three axes, three levels each (27 possible profiles):**
- **Risk Tolerance:** low (weight downside 3x) / mid (balanced) / high (weight upside 2x)
- **Skepticism:** low (trust established sources) / mid (verify key claims) / high (challenge every assumption)
- **Abstraction:** low (concrete implementation) / mid (balanced) / high (system-level patterns)

These compile to analytical instructions, not personality adjectives. "R=low" doesn't mean the agent sounds cautious. It means the agent structurally weights negative outcomes more heavily.

**Anti-stereotypical assignment:** A security expert gets HIGH risk tolerance (forced to see opportunities, not just threats). A creative gets HIGH skepticism (forced to pressure-test their ideas). The tension between persona and cognitive profile produces reasoning that neither alone would generate. Assignment is mechanical (fixed lookup table per archetype), not supervisor-judged.

**Parameter-adjusted convergence:**
```
C* = C × (1 + 0.3 × (CDI − 0.5))

CDI = 0.15 × D_p + 0.3 × D_r + 0.3 × D_o + 0.25 × D_m

Where:
  D_p = persona diversity (existing)
  D_r = risk/skepticism/abstraction profile spread (existing)
  D_o = opinion diversity (existing)
  D_m = model diversity = 1 − (agents_from_most_common_model / total_agents)
```

**CDI weights are tunable hyperparameters** with these defaults. They are not derived constants. Empirically tune after 50+ runs with outcome tracking via `--calibrate`.

**D_m examples:**
- 5 Claude, 0 external: D_m = 0.0 (no model diversity)
- 3 Claude + 1 Gemini + 1 Codex: D_m = 0.4
- 2 Claude + 2 Gemini + 1 Codex: D_m = 0.6

### Calibration Penalties (v7.3.0)

Two penalties adjust agent influence in structured votes and synthesis weighting:

**Hedging Penalty H:**
```
H(agent) = count(vaguely_hedged_claims) / count(total_claims)

Where:
  vaguely_hedged = qualifiers ("might", "could", "possibly") WITHOUT specifying
  conditions under which the claim holds. Legitimate hedging with conditions is not penalized.

  hedge_multiplier = 1 - (0.3 × H)
  Range: [0.7, 1.0]. An agent hedging 100% of claims loses 30% vote weight.
```

**Overconfidence Penalty O:**
```
O(agent) = |{claims where agent_confidence > evidence_tier}| / |total_claims|

Where:
  confidence mapped: HIGH=3, MEDIUM=2, LOW=1
  evidence_tier mapped: STRONG=3, MODERATE=2, WEAK=1, UNVERIFIED=0
  Overclaim = agent says HIGH confidence but cites WEAK or UNVERIFIED source

  overconfidence_multiplier = max(0.1, 1 - O)
  Range: [0.1, 1.0]. An agent overclaiming 100% of findings retains only 10% vote weight.
```

When `--diverse` is not active, D_m = 0.0 and CDI reduces to the original weights (rescaled: D_p=0.2, D_r=0.4, D_o=0.4).

Agreement among diverse thinkers is stronger evidence. A homogeneous all-Claude panel needs raw C = 0.88 to converge. A diverse CDP panel can converge at C = 0.73. A multi-model diverse panel with high CDP diversity can converge at C = 0.68 — cross-model agreement is the strongest convergence signal available. [Full CDP specification →](docs/ARCHITECTURE.md#cognitive-diversity-profiles-cdp)

### Bias Detection (All Modes)

The supervisor runs 4 cognitive bias checks on every synthesis before presenting it:

| Bias | Detection Method | Action |
|------|-----------------|--------|
| **Anchoring** | Did the first agent's answer disproportionately shape the synthesis? Compare word overlap between Agent 1 output and final synthesis vs. other agents. | If Agent 1 overlap > 2x average → flag and re-weight |
| **Base-rate neglect** | Does the synthesis cite frequencies/probabilities? If yes, does it state the base rate? | If probability claim without base rate → flag "missing base rate" |
| **Confirmation bias** | Did agents with the same stance cite the same sources? | If >50% source overlap between aligned agents → flag "echo sourcing" |
| **Survivorship bias** | Does the synthesis generalize from successes without mentioning failures? | If recommendations cite only positive examples → flag "no failure cases" |

The supervisor MUST address every flag in the final report. Flags are visible to the user — they can't be silently dismissed.

### Anti-Hallucination Scorecard (All Modes)

Every final report includes a mandatory **Evidence Scorecard:**

```
Claims: 12 total
  Sourced (STRONG):     5  (42%)
  Sourced (MODERATE):   3  (25%)
  Sourced (WEAK):       1  (8%)
  Unsourced:            2  (17%)  ← FLAGGED
  Disputed:             1  (8%)   ← BOTH SIDES SHOWN

Hallucination Risk: MEDIUM (17% unsourced)
```

**Thresholds:**
- LOW risk: <10% unsourced claims
- MEDIUM risk: 10-25% unsourced
- HIGH risk: >25% unsourced → supervisor MUST add disclaimer

The scorecard is computed, not estimated. The supervisor counts every claim in the synthesis, traces each to a source (or marks it unsourced), and computes the percentages. This is math, not judgment.

### Research Drift Diff (All Modes — Supervisor-Integrated)

The supervisor runs drift detection as part of Phase 4 synthesis, not as a post-hoc check. It auto-corrects what it can and presents only unresolved findings to the user.

**How it works:**

1. **Phase 2:** Supervisor builds a claim pool from all Phase 1 agent outputs (claim text + source + finding direction)
2. **Phase 4.5:** After drafting the synthesis, supervisor diffs every claim against the pool
3. **Auto-correction:** Supervisor resolves drift before the verdict ships:
   - DRIFT (unsourced) → web search for source. If found: reclassify. If not: remove or label "unverified"
   - INVERTED (direction flipped) → correct synthesis to match source. If intentional disagreement: preserve both in disagreement register
   - EXPANDED (sourced) → verify source exists. If unverifiable: reclassify as DRIFT
4. **Resolved diff in verdict:** User sees what was auto-corrected AND what remains unresolved

```
RESEARCH DRIFT DIFF — Phase 1 → Phase 4

Auto-corrected by supervisor:
  [D-001] DRIFT → REMOVED: "Most teams adopt within 6 months"
          Reason: unsourced, web search found no supporting data
  [D-002] INVERTED → CORRECTED: "adds latency" was written as "reduces latency"
          Corrected to match source direction

Unresolved (requires user validation):
  [D-003] EXPANDED: "Migration cost bounded to 3 days"
          Source: Architect agent estimate (not externally sourced)
          Supervisor note: reasonable but unverified. Included as estimate.

Drift summary: 3 findings, 2 auto-corrected, 1 requires validation
```

The supervisor is the first line of defense. The user reviews judgment calls, not mechanical verification.

### Independence Score (All Modes)

Measures how independently agents arrived at their conclusions:

```
I = 1 - (max pairwise similarity between any two agent reports)

Similarity = (shared claims) / (total unique claims across the pair)

I > 0.7  → HIGH independence (agents genuinely explored different space)
I ∈ [0.4, 0.7] → MEDIUM (some convergence, check for anchoring)
I < 0.4  → LOW → trigger: supervisor re-examines whether agents were given enough asymmetric context
```

**Why this matters:** Woolley et al. (2010) showed collective intelligence requires diversity of approach, not just diversity of opinion. If two agents reach the same conclusion via the same reasoning path, that's one data point, not two. The Independence Score catches this.
