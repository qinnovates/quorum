# Changelog

All notable changes to Quorum are documented here.

## [v7.3.0](https://github.com/qinnovates/quorum/releases/tag/v7.3.0) — 2026-03-29

### Changed — Terminology Revert: "dissent" → "adversarial"
- **Reverted all instances** of "dissent" back to "adversarial" across all documentation and skill definitions (~67 occurrences, 9 files)
- **Rationale:** "Adversarial" accurately describes the mechanism — agents that attack proposals to stress-test them — and aligns with the new Adversarial Attack Model. The v5.2.0 rename to "dissent" is preserved in cognitive science citations (Nemeth, Asch, Moscovici) where it is the native term
- Key reverts: "dissent-driven convergence" → "adversarial-driven convergence", "dissent agents" → "adversarial agents", "Dissent 1/2" → "Adversarial 1/2", "dissent minimum" → "adversarial minimum"

### Added — Adversarial Attack Model
- **5 named attack agents** that stress-test Quorum's scoring system: The Minimalist (complexity), The Exploiter (rubric gaming), The Statistician (weight validity), The Retrieval Hacker (evidence manipulation), The Skeptic (consensus-on-wrong-answer)
- Each agent includes: attack strategy, target terms, concrete falsification example, and "survives?" assessment
- Summary table of all attacks and fixes applied
- New section in ARCHITECTURE.md between Operational Definitions and Prompt Templates

### Changed — Scoring Formula Enhancements
- **Convergence C simplified:** `C = (A×0.6) + (D×0.4)` — N (Novelty Decay) removed from score (>0.9 correlated with A), retained as termination signal (N < 0.1 for 2 consecutive rounds → EXHAUSTED)
- **Calibration penalties added:** Hedging penalty H (`hedge_mult = 1 - 0.3×H`) and Overconfidence penalty O (`overconf_mult = max(0.1, 1-O)`) — agents who hedge without conditions or overclaim relative to evidence tier lose vote weight
- **Evidence scoring upgraded:** Binary (1.5/1.0/0.5) → continuous `E(claim) = source_weight(tier) × relevance(claim, source)` with source deduplication (`E_adjusted = E × unique_sources/total_citations` when citations > 3) and optional `--strict-evidence` entailment check
- **CDI weights labeled** as tunable hyperparameters with defaults `[0.15, 0.3, 0.3, 0.25]`, not derived constants
- **Vote weight formula expanded:** `vote_weight = confidence × evidence_tier_mult × independence_mult × hedge_mult × overconf_mult`
- **Vote thresholds clarified:** C* ≥ 0.8 CONVERGED, [0.65, 0.8) VOTE, [0.5, 0.65) CONTINUE, <0.5 after 3+ TENSION

### Added — Codex CLI Prompt Improvement
- **Vagueness gate enhanced:** When vagueness gate fires and Codex CLI is detected, generates 3 alternative prompt reformulations alongside clarifying questions
- User can pick a suggestion, modify one, or write their own
- Falls back to questions-only when Codex not available — existing behavior unchanged

### Added — Python Scoring Module
- **First Python code:** `src/quorum_scorer.py` — offline scoring harness implementing all v7.3.0 formulas
- **Dataclasses:** Claim, Attack, AgentOutput, RoundData, ScoringTrace, ScoringConfig
- **Functions:** compute_round_scores, agreement_growth, defense_success_rate, novelty_decay, compute_cdi, compute_vote_weight, compute_evidence_score, hedging_penalty, overconfidence_penalty, source_dedup_ratio, classify_outcome
- **Test suite:** `src/test_scoring.py` — 40 deterministic tests across 3 canned scenarios (GOOD, SHALLOW, HALLUCINATED)
- **Trace output:** ScoringTrace serializable to JSON for observability

### Added — Operational Definitions
- **Claim extraction spec:** What counts as a claim, semantic matching with τ_match = 0.85 cosine threshold
- **Defense success definition:** Attack = explicit contest; survived = claim persists despite attack
- **Agreement Growth computation:** Set-intersection of claims_held across rounds via semantic matching
- **Evidence Quality Score:** Continuous computation with source deduplication and optional entailment check

---

## [v7.2.0](https://github.com/qinnovates/quorum/releases/tag/v7.2.0) — 2026-03-28

### Added — Multi-Model Diversity (`--diverse`)
- **Multi-model panels** ��� replace 2 of 5 agent slots with Gemini and Codex (OpenAI) via their CLIs. Different training data, different RLHF, different blind spots. Genuine prior diversity, not prompt-level diversity on one model
- **Phase 1 injection** — external models participate as independent analysts in parallel with Claude agents. Their claims enter the Phase 2 claim pool tagged with `model: gemini` or `model: codex` for cross-model tracking
- **Phase 5 cold-review** — after synthesis, an external model reviews the verdict without seeing deliberation history. Structural independence + genuine prior diversity
- **Cross-Model Divergence flag** — new flag type: when the cold reviewer challenges a high-severity claim that the internal panel agreed on, it's flagged as `CROSS_MODEL_DIVERGENCE`
- **Model Diversity Report** — new section in every `--diverse` verdict: cross-model agreement percentage, Claude-only claims (flagged as potential training bias), external-only claims (surfaced as potential blind spots)
- **Auto-detection** — `--max` auto-enables `--diverse` when `gemini` and `codex` CLIs are detected. Override with `--no-diverse`
- **Graceful degradation** — pre-flight auth check, 120s timeout per external call, fallback to all-Claude with warning if CLIs fail
- **Output parsing fallback** — JSON → markdown code fence extraction → unstructured claim extraction (same as Phase 2 triage)

### Changed — Convergence Formula (CDI)
- **D_m term added** — model diversity now contributes 25% of the Cognitive Diversity Index: `CDI = 0.15 × D_p + 0.3 × D_r + 0.3 × D_o + 0.25 × D_m`. Cross-model agreement is treated as stronger evidence than within-model agreement
- **New convergence threshold** — multi-model diverse panel can converge at C = 0.68 (vs 0.73 for CDP-diverse, 0.88 for homogeneous)
- When `--diverse` is not active, D_m = 0.0 and CDI reduces to original weights

### Changed — Validation Layers (6 → 7)
- **Layer 7: Cross-Model Consistency** — agreement across different model families is stronger evidence; disagreement triggers escalated review. Claude-only claims flagged as potential training bias. External-only claims surfaced as potential blind spots

### Changed — Flags (6 → 8)
- New flags: `--diverse` (use multi-model panel), `--no-diverse` (suppress auto-detection under `--max`)
- Allowed tools: added `Bash(gemini:*)` and `Bash(codex exec:*)` for external CLI calls

### Changed
- Version bump 7.1.0 → 7.2.0

## [v7.1.0](https://github.com/qinnovates/quorum/releases/tag/v7.1.0) — 2026-03-28

### Added — Structured Vote (Near-Consensus Tiebreaker)
- **Weighted voting** for close calls — when convergence score C* is in [0.65, 0.8), agents cast structured ballots: position + confidence (1-10) + one-sentence rationale
- **Evidence-weighted, not headcount** — votes multiplied by evidence quality (1.5x for cited sources, 0.5x for preference-only) and independence (1.2x if low overlap with co-voters, 0.8x if echo voting detected)
- **Supervisor can override** with stated reasoning — vote informs the synthesis, doesn't dictate it
- **Visible in verdict** — full vote breakdown with weighted totals shown to user
- Also triggers in default mode when supervisor detects a 40-60% near-split with similar evidence quality

### Added — Vagueness Gate (Auto-Triggered)
- **Automatic prompt quality check** — supervisor detects vague prompts (no scope, no constraints, no success criteria) and asks 2-4 targeted clarifying questions before spawning agents
- **Fires without --ponder** — auto-triggered when 2+ vagueness signals detected. User answers refine the internal prompt agents see
- **Override with "just run it"** — user can bypass if speed matters more than precision
- **Relationship to --ponder:** vagueness gate asks only what's needed (2-4 questions). --ponder runs full interactive prompt optimization. --ponder supersedes the gate

### Added — Ratify Mode (`--ratify`)
- **Human-in-the-loop approval gate** — after deliberation, `--ratify` adds a structurally independent Auditor review and pauses for human approval before the verdict is final
- **Auditor agent** — fresh agent invocation with structural independence (reads ONLY original question + verdict, no phase history). Evaluates: logical coherence, evidence sufficiency, scope completeness, internal consistency, actionability. Research basis: Lorenz et al. (2011) social influence isolation
- **Human review** — Accept / Refine / Reject. REFINE injects a constraint and re-runs Phases 3-7 once. One revision maximum — research (Schulz-Hardt et al. 2006) shows first revision captures the quality gain, subsequent rounds flatten
- **Orthogonal composability** — `--ratify` composes with all tiers. `--max --ratify` = deep deliberation + audit + human approval. Two independent axes: depth (--max) and control (--ratify)
- **Token cost** — ~1.7x base for --ratify alone, ~2.4x for --max --ratify

### Added — Research Drift Diff (Supervisor-Integrated Anti-Hallucination)
- **Phase 4.5: Drift Detection & Auto-Correction** — integrated into the supervisor's synthesis workflow, not a passive validation layer. Supervisor builds a claim pool from Phase 1 outputs (text + source + finding direction), diffs every synthesis claim against it, and auto-corrects before the verdict ships
- **Three drift classifications:** EXPANDED (sourced new claim — verify source), DRIFT (unsourced new claim — supervisor web-searches, sources, or removes), INVERTED (finding direction flipped from source — supervisor corrects to match source or preserves both in disagreement register)
- **Resolved diff in every verdict** — user sees what the supervisor already fixed + what remains unresolved. Supervisor is the first line of defense; user handles genuine judgment calls
- **Catches the most dangerous hallucination pattern:** real DOI grafted onto fabricated metadata with inverted finding direction. Based on QIF research protocol incident (2026-03-17)
- Validation layers increased from 5 to 6

### Changed — Terminology: "adversarial" → "dissent"
- **Renamed all instances** of "adversarial" to "dissent" across all documentation and skill definitions (~96 occurrences, 8 files)
- **Rationale:** "Dissent" is the native term in the cognitive science literature that grounds Quorum (Nemeth 2001, Moscovici 1969, Asch 1951). It accurately describes the mechanism — productive disagreement that improves group output — without the militaristic connotation of "adversarial"
- **Preserved proper nouns:** "adversarial" retained where it refers to external concepts (Kahneman's "adversarial collaboration", SimpleQA adversarial benchmarks, adversarial attack surfaces in prompt templates)
- Key renames: "adversarial convergence" → "dissent-driven convergence", "adversarial agents" → "dissent agents", "Adversarial 1/2" → "Dissent 1/2", "adversarial minimum" → "dissent minimum", "adversarial ratio" → "dissent ratio"

## [v5.2.0](https://github.com/qinnovates/quorum/releases/tag/v5.2.0) — 2026-03-22

### Added — Converse Mode (`--converse`)
- **Converse Mode** — iterative dissent-driven convergence where the full panel (5-7 agents) stays in the room across multiple rounds, attacking proposals, building counter-proposals, and converging on solutions that survive sustained critique
- **Research-backed agent composition** — 40% dissent / 60% constructive ratio derived from convergent findings across 8 research domains:
  - Wisdom of crowds: Page (2007) diversity prediction theorem
  - Groupthink prevention: Asch (1951) single-ally conformity breaking, Janis (1972)
  - Adversarial collaboration: Kahneman (2003) 1:1 adversarial structure
  - Devil's advocate: Nemeth (2001) authentic dissent > role-played DA; Schweiger (1986) counter-plans beat critique by 34%
  - Jury deliberation: Moscovici (1969) consistent minority of 2; Nemeth (1977) unanimity rules; Kerr & MacCoun (1985)
  - Multi-agent AI debate: Du et al. (2023) 3-agent optimum; Liang et al. (2023) performance drops at 4+ agents; Irving et al. (2018) 1:1 + judge
  - Collective intelligence: Woolley et al. (2010) equal conversational turns; Lorenz et al. (2011) social influence narrowing
  - Delphi method: Dalkey & Helmer (1963); Linstone & Turoff (2002)
- **Five core personas:** Proposer (goes first), Realist (constructive pessimist), Breaker (red teamer), Synthesizer (what survived?), Judge (neutral arbiter, calls endpoint)
- **Two additional personas for --full:** Historian (precedent), Survivor (pessimistic but constructive)
- **Anti-duplication rules** — no repetition across rounds, every criticism requires counter-proposal, constructive pessimism only (no free nihilism)
- **Convergence detection** — Judge tracks agreement growth, loop detection, diminishing returns. Three outcomes: CONVERGED / TENSION / EXHAUSTED
- **Attack resistance map** — output shows each surviving component and which specific attacks it withstood
- **Formula:** `Critics = min(floor(N × 0.4), 3)`, Builders fixed at minimum (Proposer + Synthesizer + Judge)

### Architecture
- New Converse Mode section in ARCHITECTURE.md with full research foundation table (10 citations with DOIs)
- Converse Mode comparison table vs Standard, Dialectic, Swarm
- 7 new prompt templates in PROMPTS.md (Proposer, Realist, Breaker, Synthesizer, Judge, Historian, Survivor)
- Converse Mode section in GUIDE.md with decision matrix, cost table, and examples
- Anti-duplication rules, convergence detection protocol, and phase-by-phase workflow

### Fixed
- **Deletang et al. citation misattribution** — README attributed the "lossy decompression produces artifacts/hallucinations" claim to Deletang et al. 2024, but that paper is about lossless compression. Corrected to the full Shannon → Deletang → Chlon attribution chain. SAFETY.md already had the correct attribution.
- **Validation gate honesty** — Phase 5 "Independent Validation" renamed to "Validation Gate" with explicit disclosure that agent review is prompt-level independence, not structural independence (per Lorenz et al. 2011, Nemeth 2001)
- **Swarm O(patterns) honesty** — Added disclosure that the Environment Server is prompt-orchestrated, not a persistent runtime service. O(patterns) scaling is a design goal, not a current guarantee.
- **Dissent minimum raised** — Standard mode minimum dissent agents at 5-agent swarms raised from 1 to 2, matching Moscovici (1969) credible minority threshold

### Changed
- Version bump 5.1.0 → 5.2.0
- New flag: `--converse` (composable with `--full`, `--mode research`, `--seed`, `--viz`)
- README updated: scaling table, features list, examples, new "What's New in v5.2.0" section
- SKILL.md updated: argument-hint, options table, examples

### Design Process
Feature designed through dissent research: 59 searches across Semantic Scholar, Google Scholar, arXiv, CORE, and Crossref. All DOIs verified. Research challenged the initial assumption that "more critics = better" — the evidence converged on quality and authenticity of dissent over quantity.

---

## [v5.1.0](https://github.com/qinnovates/quorum/releases/tag/v5.1.0) — 2026-03-22

### Added — Outcome Predictor
- **Outcome Ledger** — every session automatically logs testable claims with confidence levels, persona attribution, and timestamps to `_swarm/ledger.json`
- **Calibrate mode** (`--calibrate`) — review past claims, mark outcomes (CORRECT/INCORRECT/PARTIALLY_CORRECT), compute calibration scores per confidence level, persona type, mode, and rigor
- **Monitor mode** (`--monitor SESSION_ID`) — re-run a previous session's question with fresh data, compare position shifts, output Drift Report

### Added — Structured Seed Data
- **Seed Data Engine** (`--seed PATH`) — accepts JSON, CSV, and RSS/Atom feed URLs as structured input alongside the text prompt
- Seed data partitioned across agents by the Partition Engine (index ranges, categories, or MECE territory mapping in swarm mode)
- Agents cite seed data entries with `[Seed:ID]` format
- Research agents receive seed data summary for search query generation
- Size limits enforced: max 500 entries, 100KB per agent partition

### Added — Visualization Export
- **Viz export** (`--viz`) — outputs D3-compatible JSON + self-contained HTML viewer to `_swarm/viz/`
- **HTML viewer features:** force-directed agent graph (archetype-colored nodes, interaction edges), opinion drift chart, timeline scrubber with Play animation, cluster/coalition convex hull overlays, click-to-inspect info panel
- Fully offline viewer — all D3.js and CSS inlined, zero network requests
- Swarm mode extends viz with: taxonomy tree, territory assignments, cascade chains, sentiment trajectory animation
- Respects `--redact` flag for credential/PII stripping in viz output

### Added — Temporal Simulation
- **Temporal simulation** (`--simulate TIMEFRAME`) — divide a timeframe into steps, inject events per step, watch the swarm's predictions evolve over simulated time
- **Event generation pipeline:** agent-generated events (each proposes 1-2 per step), supervisor-curated selection, mandatory wildcard events for anti-boxing
- **Seed events:** `--seed events.json` provides pre-planned event timelines for scenario testing
- **Temporal viz:** timeline scrubber shows time labels ("Month 3: EU DPA issues first fine") with event markers on the opinion drift chart

### Architecture
- Phase 7 and Phase S7 updated: claim extraction for Outcome Ledger + viz data collection as post-synthesis steps
- New Seed Data Engine section in architecture (format parsing, even-split partition, enriched citation format)
- New Temporal Simulation Mode section (event schema, per-step workflow, constraints)
- New prompt template blocks: `{{SEED_DATA}}` conditional for Analysis and Research agents
- Safety additions: seed data sanitization with explicit injection actions (Section 9), viz data privacy with CSP (Section 10)

### Fixed (from 8-agent self-review)
- **[C1] Viz HTML viewer** — switched from LLM-generated D3 to pre-built template. Supervisor injects JSON data only. Template stored at `_swarm/viz/viewer-template.html`
- **[C2] Ledger format** — switched from JSON array to JSONL (JSON Lines). Atomic append, no read-modify-write race conditions
- **[C3] Seed data injection defense** — added explicit action rules: strip + flag + report on detection. >20% bad entries aborts seed entirely
- **[C4] Claim extraction** — added worked examples, max claims (5-7 standard, 15 swarm), `testable_by` field, falsifiability requirement
- **[C5] Template sync** — seed data variables added to PROMPTS.md with format definitions
- **[M6] PARTIALLY_CORRECT** — defined as 0.5 in calibration math. Report shows correct/partial/incorrect breakdown
- **[M7] Monitor mode** — creates new claims with `supersedes` field, never modifies existing entries
- **[O1] Seed partition** — simplified to even-split only, dropped category heuristic
- **[O2] RSS dropped** — removed from `--seed`, use research agents for web feeds
- **[O3] Calibration buckets** — primary view = confidence level only (3 buckets), secondary dimensions optional. Minimum raised to 20

### Changed
- Version bump 5.0.0 → 5.1.0
- New flags: `--seed PATH`, `--seed-preview`, `--viz`, `--calibrate`, `--monitor ID`, `--simulate TIMEFRAME`

### Inspiration
Outcome Predictor inspired by MiroFish's swarm prediction concept — adapted to track ALL Quorum session types (reviews, audits, research, decisions), not just forecasts. Temporal simulation adds the time dimension that makes prediction engines useful. Visualization export brings MiroFish-style swarm observation to Quorum's epistemic architecture.

---

## [v5.0.0](https://github.com/qinnovates/quorum/releases/tag/v5.0.0) — 2026-03-22

### Added — Swarm Mode
- **Swarm Mode** (`--swarm`) — scales Quorum from 3-17 agents to 20-1000+ agents using environment-based coordination
- **Partition Engine (Tier S1)** — generates MECE (mutually exclusive, collectively exhaustive) taxonomy from the problem space. Each agent gets a unique territory. Hard no-overlap guarantee via territory boundaries and handoff routing.
- **Environment Server (Tier S2)** — shared state store replacing per-agent context passing at scale. Agents POST findings, REACT to others, HANDOFF cross-territory discoveries, SHIFT positions. Pattern detection identifies opinion clusters, polarizations, cascades, and coalitions.
- **Activation Scheduler (Tier S3)** — probabilistic agent activation so not all agents run every round. Four strategies: round-robin (default), reactive, priority-weighted, probabilistic.
- **Prediction mode** (`--predict`) — probabilistic activation, sentiment trajectory tracking, coalition detection. Designed for forecasting and Delphi-method consensus.
- **8-phase swarm workflow** — Taxonomy → Spawn → Simulation Rounds → Pattern Extraction → Synthesis → Structural Challenge → Validation → Final Report
- **Supervisor interviews** — supervisor directly interviews 3-5 selected agents (isolated findings, minority positions) for depth at scale
- **Swarm output format** — emergent consensus, polarizations, cascades, coalition map, sentiment trajectory
- New flags: `--swarm`, `--predict`, `--branches`, `--schedule`, `--taxonomy show`, `--interviews N`

### Architecture
- 5-Tier → 6-Tier architecture (3 new infrastructure tiers for swarm mode)
- Swarm-scale scoring added to Task Classification Gate
- Detailed comparison table: Quorum Swarm Mode vs MiroFish/OASIS

### Changed
- Version bump 4.1.0 → 5.0.0 (breaking: new architecture tier, new output format for swarm mode)

### Inspiration
Scaling approach inspired by MiroFish/OASIS swarm intelligence prediction engine (environment-as-coordinator, probabilistic activation, emergent pattern detection). Adapted with Quorum's epistemic guarantees: MECE territory enforcement, evidence tiers, structural challenge, independent validation, anti-boxing rules.

---

## [v4.1.0](https://github.com/qinnovates/quorum/releases/tag/v4.1.0) — 2026-03-17

### Security
- Fixed injection defense gap in ARCHITECTURE.md templates (Cross-Review, Devil's Advocate, Phase 5 reviewer)
- Added profile sanitization for project profile poisoning prevention
- Added injection defense to Provocateur archetype
- Scoped dissent agent file access to project directory

### Architecture
- **SKILL.md split:** 1490 lines → 250 lines. All architecture, templates, and deep-dive content moved to docs/. SKILL.md is now user-facing only with progressive loading references.
- **Divergence Engine:** Provocateur archetype, EXPLORE mode, preserve-if-unique triage, creative disruption check, research partition overlap
- **Structural Protections (enforced):** Dissent immunity, Socratic follow-ups (2-3 per team), refutation resistance (replaces confidence scores), Socratic Remainder, inverted early termination
- **Anti-boxing:** Condition-based outsider injection (replaces counter-based), exploration signal in Socratic Gate, Contestability replaces Falsifiability
- Added EXPLORE mode to GUIDE.md with Provocateur documentation

### Changed
- Version bump 4.0.0 → 4.1.0
- Socratic Gate: 5 dimensions → 6 (added Exploration signal)
- Socratic Gate: Falsifiability → Contestability (supports normative questions)

---

## [v4.0.0](https://github.com/qinnovates/quorum/releases/tag/v4.0.0) — 2026-03-17

### Added — Adaptive Intelligence
- **Project Profiles** (`_swarm/project-profile.json`) — auto-generated on first run, persists project context (type, domains, tech stack, default teams, constraints) across runs. Eliminates re-discovery. Boosts Socratic Gate scoring. Sharpens ponder questions.
- **Task Classification Gate** — 4-dimension scoring matrix (Domain count, Certainty demand, Scope breadth, Artifact presence). Score 0-12 maps to mode, agent count, structure, and rigor. Override rules for binary decisions (auto-dialectic), feasibility probes (dialectic-first), and cross-domain questions (auto-org).
- **Config Transparency Block** — replaces `--dry-run` with "here's what I read, here's my config, here's why." Always shown unless `--quiet`. User approves, edits, or cancels before tokens are spent.
- **Adaptive Output Templates** — 5 templates matched to task type: AUDIT (verdict + finding table), RESEARCH (evidence table + citations), DIALECTIC (dialogue transcript + what emerged), DECISION (recommendation + tradeoff table), ORG (team positions + clash table + Socrates/Plato sections).
- New flags: `--yes` (auto-proceed), `--quiet` (suppress transparency block), `--profile show|update|reset`, `--format audit|research|dialectic|decision|org`

### Changed
- Quick Start updated: "auto-configures everything" replaces "default is fast mode (5 agents)"
- Version bump 3.2.0 → 4.0.0 (breaking: output format changes, default behavior changes)

### Design Process
Feature designed by a 6-agent Quorum swarm (3 teams: Architecture, UX, Efficiency). Swarm report: `_swarm/2026-03-17-quorum-adaptive-intelligence.md`

---

## [v3.2.0](https://github.com/qinnovates/quorum/releases/tag/v3.2.0) — 2026-03-17

### Security Hardening
- **[CRITICAL FIX] Removed `Bash`, `Write`, `Edit` from manifest `allowed-tools`.** These were available to all spawned agents despite documentation stating they were supervisor-only. Now only the supervisor session has access.
- **[CRITICAL FIX] Added XML tag injection defense.** Artifact content and inter-agent transfers now use unique session boundaries (`{{SESSION_BOUNDARY}}`) instead of fixed XML tags, preventing tag-injection prompt escapes.
- **Added agent-level prompt injection detection.** All agent templates (Research, Analysis) now include active defense instructions to detect and flag injection attempts in fetched content.
- **Added credential detection patterns.** Defined 8+ specific regex patterns for automatic redaction (AWS keys, Stripe, Slack, GitHub PATs, JWTs, private keys) instead of relying on undefined model heuristics.
- **Added path validation guidance.** `--output` and `--resume` must validate against allowed path prefixes.
- **Fixed privacy disclosure.** Cross-AI validation gate now clearly states that artifact excerpts may be included in synthesis passed to the validation agent.
- **Added independence disclaimer.** Phase 5 "independent" reviewer is now explicitly documented as same-session Claude instance, not a separate model.

### Architecture
- **Added `argument-hint` frontmatter.** Autocomplete now shows available flags when typing `/quorum`.
- **Added `disable-model-invocation: true`.** Prevents Claude from auto-triggering Quorum without explicit user invocation.
- **Added Usage Guide** (`docs/GUIDE.md`) — decision matrix for flat swarms vs subteams vs dialectic vs validation, cost guide, real-world examples.

---

## [v3.1.0](https://github.com/qinnovates/quorum/releases/tag/v3.1.0) — 2026-03-17

### Added
- **Research + Validation Workflow** — new section in SKILL.md with three copy-paste patterns:
  - Two-stage (research swarm, then validation swarm)
  - Validate any external research (not just Quorum output)
  - Resume and re-validate a prior session
- **Three-tier verdict output** for validation runs: VALIDATED / FLAGGED / BLOCKED
- **Panel Provenance** section in validation output (who validated, their stances, what models)
- **Coverage Notice** in validation output (what the panel could and could not evaluate)
- **Scope disclaimer** hard-coded into validation output template
- 5th Quick Start example showing validation pattern

### Changed
- Version bump 3.0.0 → 3.1.0

### Design Process
Feature designed by an 11-agent Quorum swarm (3 teams: Product Design, Engineering, Documentation + Socrates + Plato structural roles). Swarm report: `_swarm/2026-03-17-quorum-validate-feature.md`

---

## [v3.0.0](https://github.com/qinnovates/quorum/commit/8c4ce4f) — 2026-03-14

### Added
- **Subteam Mode** (`--teams`, `--org`) — hierarchical org-chart deliberation with team leads, internal debate, cross-team challenges
- **Socrates** (cross-team questioner) and **Plato** (evidence auditor) structural roles
- **Dialectic Mode** (`--rigor dialectic`) — Socratic deep-dive, two agents drilling through contradiction
- **5-layer validation pipeline** — source grading, contradiction check, hallucination red flags, independent validation, transparency
- **Research-backed defaults** — team sizes, org structure grounded in Hackman, Miller, Brooks, Janis
- **Session persistence** — resume prior swarms with `--resume`
- **Privacy controls** — `--no-web`, `--no-save`, `--redact`, `--no-cross-ai`
- **Output formats** — `--format full/brief/actions-only`
- Published to GitHub, submitted to Anthropic marketplace

### Changed
- Renamed from "Expert Swarm" to "Quorum"

---

## v2.1.0 — 2026-03-13

### Added
- Multi-agent intelligence with built-in BS detection
- Devil's Advocate, Naive User, Domain Outsider mandatory roles
- Cross-AI validation gate
- Competitive positioning vs Claude Swarm, Auto-Claude, CrewAI

### Changed
- Reframed as "swarm conductor" with outcome-focused documentation

---

## v1.0.0 — 2026-03-12

### Added
- Initial release as "Expert Swarm"
- Basic multi-agent panel with parallel independent work and supervisor synthesis
