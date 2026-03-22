# Changelog

All notable changes to Quorum are documented here.

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
- Scoped adversarial agent file access to project directory

### Architecture
- **SKILL.md split:** 1490 lines → 250 lines. All architecture, templates, and deep-dive content moved to docs/. SKILL.md is now user-facing only with progressive loading references.
- **Divergence Engine:** Provocateur archetype, EXPLORE mode, preserve-if-unique triage, creative disruption check, research partition overlap
- **Structural Protections (enforced):** Adversarial immunity, Socratic follow-ups (2-3 per team), refutation resistance (replaces confidence scores), Socratic Remainder, inverted early termination
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
