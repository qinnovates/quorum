# Quorum FAQ

Empirical findings from testing Quorum at multiple scales, plus statistical methodology for evaluating multi-agent debate systems.

Based on controlled experiments running the same philosophical question through Quorum at N=5, N=10 (cluster), and N=100 (swarm) agent scales, with and without context/memory injection.

---

## Table of Contents

- [General](#general)
- [Scale & Agent Count](#scale--agent-count)
- [Context & Memory](#context--memory)
- [Personas & Cognitive Diversity](#personas--cognitive-diversity)
- [Statistical Methodology](#statistical-methodology)
- [Interpreting Results](#interpreting-results)

---

## General

### What is a Quorum verdict?

A synthesized output from multiple AI agents that independently analyzed the same question, then had their positions cross-examined, challenged, and merged by a supervisor. The verdict includes: what survived scrutiny, what's disputed, evidence quality scores, bias checks, and actionable recommendations.

### What verdict types exist?

| Verdict | Meaning |
|---------|---------|
| **CONVERGED** | A position survived sustained attack. Convergence score C >= 0.8. |
| **VOTE** | Near-consensus (C in [0.65, 0.8)). Structured vote resolved it. |
| **TENSION** | Irreducible tradeoff. The panel identified a structural disagreement that cannot be resolved by more debate. |
| **EXHAUSTED** | Diminishing returns after max rounds. No convergence, no clean tension — the question may need reframing. |

### Does Quorum always produce the "right" answer?

No. Quorum produces the answer that **survived the most scrutiny**. On questions with objectively correct answers (technical, factual), this correlates strongly with correctness. On philosophical, ethical, or strategic questions, it surfaces the structural tradeoffs and tells you what you're choosing between — which is more useful than a false single answer.

---

## Scale & Agent Count

### Does scaling from 5 to 100 agents change the verdict?

**Structural verdict: No.** In controlled tests, the core findings (e.g., a trilemma, the irreducible tensions, the surviving claims) were identical at N=5 and N=100. The verdict type (TENSION in our test case) did not change.

**Depth and coverage: Yes.** Scaling to 100 surfaced findings that 5 agents missed:

| Finding | Emerged at N=5? | Emerged at N=100? |
|---------|----------------|------------------|
| Core trilemma | Yes | Yes |
| Nuremberg threshold | Yes | Yes |
| Judicial minimalism (enforcement isn't binary) | No | Yes |
| Measurement problem ("widely considered" by whom?) | Partial | Yes, from multiple angles |
| Weaponizability of refusal precedent | No | Yes |
| Complicity-vs-futility dilemma | No | Yes |
| Proportionality analysis as institutional tool | No | Yes |
| Constituent power theory (Schmitt) as limit case | No | Yes |

**Takeaway:** 5 agents get the structure right. 100 agents get the structure right *plus* the institutional, historical, and meta-structural reasons why it's irreducible.

### What's the difference between 10 cluster agents and 100 individual agents?

A cluster agent (one agent summarizing ~10 perspectives) averages out minority positions. An individual agent holding a single position can defend it against attack. Cluster representatives are encyclopedists, not debaters — they suppress the sharpest disagreements in favor of balanced summaries.

For exploratory questions where you want the full landscape, clusters are fine. For stress-testing where minority positions might be the most important signal, use individual agents.

### When should I use `--max` vs `--set 100` vs default?

| Scenario | Recommended | Why |
|----------|------------|-----|
| Quick opinion on a scoped question | Default (5 agents) | Gets the structure right in ~2 minutes |
| Stress-testing a decision | `--max` (7-15 agents) | Adversarial-driven convergence with iterative rounds |
| Research landscape | `--set 50-100` | MECE partitioning covers more territory |
| Prediction / forecasting | `--set 100+` | Swarm architecture with pattern detection |
| High-stakes architecture decision | `--max --ratify` | Full convergence + human approval gate |

---

## Context & Memory

### Does injecting context/memory change the output?

**For domain-general questions (philosophy, ethics, strategy): No.**

Controlled experiment: same philosophical question, same agent assignments, one run with full context/memory injected, one run sterile. Results:

| Metric | With Context | Without Context | Overlap |
|--------|-------------|----------------|---------|
| Verdict type | TENSION | TENSION | Identical |
| Surviving claims | 29 | 29 | ~90% semantic match |
| Irreducible disagreements | 19 | 19 | ~93% semantic match |
| Unique thinkers cited | ~78 | ~75 | ~88% overlap |
| Core structural finding | Trilemma | Same trilemma | 100% |

**The ~10% variation was rhetorical, not analytical** — different metaphors, slightly different secondary citations, minor emphasis shifts. No agent in the context run reached a conclusion contradicting their no-context counterpart.

### When WOULD context matter?

Context/memory would meaningfully shift outputs for questions about:
- **Project-specific decisions** (architecture, dependencies, past tradeoffs)
- **User preferences and constraints** (team size, deadlines, risk tolerance)
- **Codebase-specific patterns** (existing conventions, known tech debt)
- **Historical project context** (why a decision was made, what was tried before)

For these, context provides information the agents literally cannot derive from the question alone.

### Is the convergence between runs statistically significant?

See [Statistical Methodology](#statistical-methodology) for the full answer, but the short version: "statistical significance" is the wrong frame for LLM experiments. The right question is **effect size** — and the observed effect of context injection was negligible (d < 0.1 on all measured dimensions).

---

## Personas & Cognitive Diversity

### Do personas actually drive output variance?

This is testable via **variance decomposition** (ICC analysis). The experiment design measures how much of the total variance in agent outputs is attributable to:

1. **Persona/tradition assignment** — does a legal positivist reliably produce different output from a natural law theorist?
2. **CDP profile** (risk tolerance, skepticism, abstraction) — does a high-skepticism agent actually reason differently?
3. **Residual noise** — temperature sampling, prompt sensitivity, etc.

If ICC_tradition is near zero, persona assignment is theater. If it's > 0.15, it's driving meaningful differentiation. (Full methodology in [Statistical Methodology](#statistical-methodology).)

### What are Cognitive Diversity Profiles (CDP)?

Three axes that change *how* an agent reasons, not *what* it knows:

| Axis | Low | Mid | High |
|------|-----|-----|------|
| **Risk Tolerance** | Weights downside 3x | Balanced | Weights upside 2x |
| **Skepticism** | Trusts established sources | Verifies key claims | Challenges every assumption |
| **Abstraction** | Concrete implementation | Balanced | System-level patterns |

CDPs are assigned **anti-stereotypically**: a security expert gets HIGH risk tolerance (forced to see opportunities), a creative gets HIGH skepticism (forced to pressure-test ideas). The tension between persona and CDP produces reasoning neither alone would generate.

### Does the number of adversarial agents matter?

Yes. Quorum enforces a minimum of 2 adversarial agents per panel of 5+. The research basis:

- **Asch (1951):** A single dissenter reduces conformity from 32% to 5%
- **Moscovici (1969):** A minority of 2 establishes a credible pattern — 1 is dismissed as eccentric
- **Nemeth (2001):** Assigned devil's advocacy makes people MORE entrenched. Critics must hold authentic positions
- **Schweiger (1986):** Critics who propose counter-plans produce 34% higher decision quality than critics who only attack

This is why Quorum's adversarial agents must counter-propose, not just critique.

---

## Statistical Methodology

### How do you measure philosophical positions quantitatively?

Five dependent variables, coded from each agent's text output:

| DV | Type | What It Measures |
|----|------|-----------------|
| **Primary Stance** | 5-point ordinal | Enforce unconditionally (1) through refuse on moral grounds (5) |
| **Justification Type** | Categorical (multi-label) | Deontological, consequentialist, virtue, pragmatic, rights-based, pluralist |
| **Judicial Role Conception** | 3-point ordinal | Positivist (1), interpretivist (2), natural law/activist (3) |
| **Epistemic Certainty** | Continuous [0,1] | Ratio of categorical assertions to total claims |
| **Novelty Score** | Continuous [0,1] | Semantic distance from response centroid via embeddings |

Two independent human raters code DV1-DV4 (blind to condition). DV5 is computed algorithmically. Inter-rater reliability thresholds: Cohen's kappa > 0.75, Krippendorff's alpha > 0.70, ICC > 0.80.

### What statistical tests are appropriate?

| Hypothesis | Test | Why This Test |
|-----------|------|--------------|
| Context shifts stance distribution | Cumulative link mixed model (ordinal logistic with random effects) | Ordinal DV, nested data (agents within traditions) |
| Agents collapse to attractor positions | HDBSCAN on embeddings + finite mixture model | Density-based clustering doesn't require pre-specifying k; mixture model tests component count |
| Persona assignment drives variance | ICC from mixed models | Variance partition: how much is tradition vs residual? |
| Context surfaces novel claims | Linear mixed model on novelty score | Continuous DV, same nesting structure |

**Primary inferential engine: Permutation tests** (10,000 shuffles). Valid without distributional assumptions. This sidesteps the meta-question of whether LLM outputs constitute a valid statistical sample.

### Do we need 95% confidence / 2 standard deviations?

**No.** The 95% CI (approximately 1.96 standard deviations on a normal distribution) is a convention, not a requirement. For this experiment, it's arguably the wrong threshold for three reasons:

1. **We're not sampling from a population.** LLM agents are deterministic functions of prompts + sampling noise. The "population" is artificial. Permutation tests don't rely on normal distributions or standard CI logic.

2. **Effect size matters more than significance.** With 600 data points (100 agents x 3 replications x 2 conditions), trivially small effects reach p < 0.05. A statistically significant but tiny context effect (d = 0.1 shift on a 5-point scale) is meaningless for Quorum's actual purpose.

3. **The outputs won't be normally distributed.** Philosophical positions cluster around attractors. Expect a multimodal distribution, not a bell curve. Applying normal-distribution assumptions (mean +/- 2 sigma) to multimodal data is a category error.

**The right thresholds are practical, not statistical:**

| Question | Meaningful Threshold |
|----------|---------------------|
| Does context shift the stance distribution? | Cohen's d > 0.4 (medium effect) |
| Do agents collapse to attractors? | k_clusters < 10, silhouette > 0.5 |
| Does persona drive variance? | ICC_tradition > 0.15 |
| Does context surface novel claims? | Novelty score differs by d > 0.3 |

### Why run each agent 3 times?

To separate signal from noise. LLM outputs are stochastic at temperature > 0. Without replication, you can't distinguish "context changed the output" from "the LLM sampled differently." The 3 replications per agent per condition provide a noise floor:

- **Within-agent variance** = temperature/sampling noise
- **Between-agent variance** = persona + tradition + CDP effects
- **Between-condition variance** = context injection effect

If within-agent variance approaches between-agent variance, persona assignment isn't meaningfully differentiating outputs.

### Is this even a valid experiment? LLM agents aren't independent samples.

Correct. LLM agents are deterministic functions of (prompt, weights, sampling seed), not independent draws from a population. "Statistical significance" in the frequentist sense has no straightforward interpretation here.

**The reframe:** This is a **computational experiment** (like a simulation study), not a behavioral experiment. We're characterizing a system's sensitivity to input perturbation.

The valid inferential framework:

1. **Randomization inference** — permutation tests are valid regardless of population assumptions. They test the sharp null that context labels are exchangeable with respect to the outcome.
2. **Replication runs are essential** — they provide the noise floor without which signal detection is impossible.
3. **Report effect sizes, not just p-values** — the question is "does context injection shift the distribution enough to change the verdict?" not "is the shift nonzero?"

### What about outliers?

Do not discard them. Outlier agents (high novelty score, unusual positions) are potentially the most valuable data — they represent the minority positions that cluster-summarization would suppress.

Handling:
- Report all analyses with and without high-novelty agents (DV5 > 2 SD from centroid)
- Use robust estimators (Huber-White sandwich standard errors) for parametric models
- HDBSCAN naturally classifies low-density points as noise rather than forcing them into clusters
- Analyze the high-novelty subset qualitatively as a dedicated results section

### What are the threats to validity?

| Threat | Mitigation |
|--------|-----------|
| Temperature/sampling variance | 3 replications per agent; ICC_replication measured |
| Prompt sensitivity | Fixed question across all runs; acknowledge single-stimulus limitation |
| Order effects in coding | Randomized presentation to raters; blind to condition |
| Persona-tradition confounding | CDP assigned independently of tradition; check interaction effects |
| Ceiling/floor effects | Report marginal distribution of DV1 before modeling |
| Embedding model sensitivity | Repeat DV5 and cluster analyses with 2 different embedding models |

---

## Interpreting Results

### What does a TENSION verdict actually mean?

It means the panel found an **irreducible tradeoff** — a structural disagreement that cannot be resolved by more evidence, more agents, or more rounds. The disagreement reflects genuinely incompatible foundational commitments.

Example: the trilemma surfaced in our test (rule of law, moral constraint, democratic legitimacy — pick two) is irreducible because each position sacrifices a different value. No amount of debate resolves which value to sacrifice — that's a human choice.

TENSION is not a failure. It's the most informative verdict type for complex questions, because it tells you exactly what you're choosing between and why.

### How should I read the Evidence Scorecard?

```
Claims: 15 total
  Sourced (STRONG):    10  (67%)
  Sourced (MODERATE):   3  (20%)
  Unsourced:            1  (7%)
  Framework-derived:    1  (7%)

Hallucination Risk: LOW (7% unsourced)
```

- **STRONG**: Traced to a specific, verifiable source (peer-reviewed paper, official docs)
- **MODERATE**: Sourced but not independently verified in this session
- **UNSOURCED**: Claim exists in the synthesis but no agent provided a source. Flagged.
- **Framework-derived**: Synthesized from the panel's work (e.g., a trilemma constructed from the positions), not sourced externally

Thresholds: LOW risk (< 10% unsourced), MEDIUM (10-25%), HIGH (> 25% + mandatory disclaimer).

### Can I trust the convergence score?

The convergence formula is:

```
C = (A × 0.6) + (D × 0.4)

A = Agreement Growth    = claims held this round / claims held last round
    (claim matching via semantic similarity, τ = 0.85 cosine threshold)
D = Defense Success Rate = attacks survived / attacks received

Termination signal (not scored):
N = Novelty Decay = 1 - (new arguments this round / new arguments round 1)
If N > 0.9 for 2 consecutive rounds → EXHAUSTED
```

It's a measured signal, not a vote count. C >= 0.8 means: agents are running out of attacks and surviving claims are defending successfully against adversarial pressure. Novelty decay (N) is tracked as a termination signal but removed from the score — it correlates >0.9 with A and adds noise rather than signal. It's adjusted for cognitive diversity (C* = C x (1 + 0.3 x (CDI - 0.5))) so agreement among diverse thinkers counts for more.

The score is useful as a stopping criterion and relative confidence indicator. It is not a probability and should not be interpreted as one.

---

## Experimental Findings Summary

From controlled runs on the question: *"If a law is passed that is widely considered unjust by the population but is technically constitutional, should a judge enforce it?"*

| Finding | Confidence |
|---------|-----------|
| Verdict type is stable across scales (N=5, 10, 100) | HIGH — reproduced 4x |
| Core structural findings are stable across scales | HIGH — trilemma emerged every run |
| Context/memory injection does not change domain-general verdicts | HIGH — < 10% variation, all rhetorical |
| Scaling surfaces minority positions that clusters suppress | MODERATE — observed but not yet statistically validated |
| Agents appear to collapse to a small number (~5) attractor positions | MODERATE — consistent pattern, needs HDBSCAN validation |
| CDP profiles drive measurable output variation | UNVALIDATED — requires ICC analysis on replicated runs |
