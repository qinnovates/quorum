# Quorum

**Orchestrate a swarm of AI experts on any question. From 3 agents to 1,000. One command, multiple minds, stress-tested answers.**

Type one command. Quorum spins up a team of specialists — researchers, analysts, skeptics, domain experts — makes them work the problem from every angle, debate each other, validate their claims, and deliver a synthesized verdict you can actually act on.

Like having a room full of smart people argue about your question before anyone gives you the answer. Or, in swarm mode, an entire conference hall.

```
/quorum "your question here"
```

Built by [qinnovate](https://qinnovate.com) | [Full docs](docs/ARCHITECTURE.md)

---

## Why Quorum?

When you ask AI a question, you get one perspective. It sounds confident. It might be completely wrong. And you have no way to know.

Quorum gives you what a single AI agent never can: **a second opinion, a third opinion, a devil's advocate, and a fact-checker — all at once.**

Here's what happens when you run it:

1. **A team assembles.** Quorum picks the right experts for your question — a strategist, a skeptic, a researcher, a domain specialist, someone from a completely different field
2. **They work independently.** No groupthink. Each expert tackles the question from their unique angle without seeing anyone else's answer
3. **They challenge each other.** The skeptic pokes holes. The researcher checks sources. Debate pairs argue the real disagreements
4. **A supervisor synthesizes.** Not a vote count — an authored judgment that weighs reasoning quality, surfaces buried insights, and tells you what actually matters
5. **You get the verdict.** What survived scrutiny, what's still disputed, and what to do next

**The result: answers that have been stress-tested by multiple minds before you see them.**

## Quick Start

```bash
# Install
claude install qinnovates/quorum

# Ask anything — 5 agents, auto-configured
/quorum "Should we use PostgreSQL or DynamoDB for our new service?"

# Stress-test a decision — full adversarial convergence
/quorum "Should we build or buy our auth system?" --max

# Build something — auto-generates battle-tested PRD + Ralph loop
/quorum "Build a REST API for user auth with JWT" --max

# Review a document
/quorum "Review this proposal for risks" --artifact proposal.md

# Sequential review pipeline — auto-resolves mechanical, surfaces taste calls
/quorum "Is this API spec production-ready?" --reviewers --artifact api-spec.md

# Massive scale — swarm auto-engages at 20+
/quorum "Impact of EU AI Act on BCI startups" --set 200

# See the plan before spending tokens
/quorum "your question" --max --dry-run
```

## How It Works

Quorum runs a multi-phase pipeline. You don't need to understand this to use it — just type `/quorum "question"` and go. But if you want the details:

**Standard mode (3-17 agents):**
1. **Setup** — Supervisor analyzes your question, picks the right experts and assigns each a unique angle
2. **Independent work** — All agents work in parallel, no one sees anyone else's output
3. **Triage** — Supervisor reads all reports, drops low-value agents, identifies key disagreements
4. **Cross-review** — Selected agents debate each other directly. Devil's Advocate challenges the majority
5. **Synthesis** — Supervisor authors the final report with editorial judgment
6. **Validation** — Adversarial reviewer challenges the synthesis (web fact-check preferred; same-session agent review as fallback — see [Limitations](#honest-limitations))
7. **Final report** — What survived, what's disputed, what to do next

**Converse mode (`--converse`):**
1. **Propose** — Proposer puts a solution on the table
2. **Contradict** — Realist and Breaker attack with specific failure modes and counter-proposals
3. **Defend or abandon** — Proposer revises; critics attack the fixes; Synthesizer reports what survived
4. **Converge** — Judge declares: CONVERGED (survived attack) / TENSION (irreducible tradeoff) / EXHAUSTED (diminishing returns)

**Swarm mode (20-1000+ agents):**
1. **Taxonomy** — Partition Engine decomposes the problem into non-overlapping territories
2. **Spawn** — One agent per territory, persona derived from its domain
3. **Simulation** — Agents POST findings, REACT to others, HANDOFF cross-territory discoveries, SHIFT positions across multiple rounds
4. **Pattern extraction** — Environment Server identifies opinion clusters, polarizations, cascades, coalitions
5. **Synthesis** — Supervisor reads patterns (not individual reports), interviews key agents
6. **Structural challenge** — Socrates questions clusters, Plato audits evidence
7. **Validation** — Adversarial reviewer challenges the synthesis
8. **Final report** — Emergent consensus, polarizations, sentiment trajectory, what to do next

**[Full architecture documentation →](docs/ARCHITECTURE.md)**

## Modes

Quorum scales in five tiers. Each tier is a fundamentally different kind of reasoning — not just more agents.

| Mode | Agents | Structure | When to Use |
|------|--------|-----------|-------------|
| **Flat** (`--lite`, default) | 3-8 | Single panel, everyone debates everyone | Focused questions in 1-2 domains |
| **Converse** (`--converse`) | 5-7 | Iterative adversarial convergence, multiple rounds | Battle-tested solutions, architecture decisions, build-vs-buy |
| **Reviewers** (`--reviewers`) | 3-5 phases | Sequential cascade, auto-decide mechanical findings | Reviewing concrete artifacts, PRs, specs, architecture docs |
| **Dialectic** (`--rigor dialectic`) | 2 + supervisor | Socratic dialogue, 3-5 rounds of deepening | Deep understanding, philosophical/strategic questions |
| **Subteam/Org** (`--teams`, `--org`) | 9-22 | Named teams + Socrates + Plato | Cross-domain complexity, 3+ domains with different incentives |
| **Swarm** (`--swarm`) | 20-1000+ | Taxonomy-partitioned, environment-based coordination | Predictions, landscape surveys, exhaustive red teaming |

### Flat (Default)

```bash
/quorum "Should we use Rust or Go for our CLI?"        # 5 agents, auto-configured
/quorum "Best Python web framework?" --lite             # 3 agents, fast
/quorum "Review this API design" --artifact spec.yaml   # Document review
```

A single panel of experts debates in parallel. The supervisor coordinates directly. Best for focused questions in 1-2 domains where 5-8 agents provide enough coverage.

### Converse Mode (`--converse`)

```bash
/quorum "Best approach to real-time anomaly detection?" --converse
/quorum "Build or buy our auth system?" --converse --full
/quorum "Most robust BCI auth method?" --converse --mode research
```

The full panel stays in the room across multiple rounds. Solutions must survive sustained adversarial attack. Five core roles:

| Role | What they do |
|------|-------------|
| **Proposer** | Goes first. Defends and adapts across rounds. |
| **Realist** | "This fails because X, and here's what survives X." Every criticism includes a survival path. |
| **Breaker** | Red-teams the proposal. Self-rates attacks. When they say "I can't break this" — strongest signal in the system. |
| **Synthesizer** | Reports what survived and what collapsed at checkpoints. |
| **Judge** | Neutral arbiter. Tracks convergence. Ends conversation when signal plateaus. |

`--full` adds **Historian** (precedent) and **Survivor** (pessimistic but constructive).

**The agent ratio is research-backed** — 40% adversarial / 60% constructive, derived from convergent findings across 8 domains:

- **Nemeth (2001):** Assigned devil's advocacy makes people MORE entrenched. Critics must hold authentic positions with counter-proposals.
- **Schweiger (1986):** Counter-plans beat pure critique by 34% on decision quality.
- **Liang et al. (2023):** AI debate performance DROPS at 4+ adversarial agents. Context overload.
- **Asch (1951):** Single dissenter reduces conformity 32%→5%. Two establishes credible minority (Moscovici 1969).

**Anti-duplication rule:** No repetition across rounds. "This won't work" is not allowed — "This won't work because X, and here's what would survive X" is required. No free nihilism.

Three outcomes: **CONVERGED** (solution survived attack), **TENSION** (irreducible tradeoff — user decides), **EXHAUSTED** (no convergence, best surviving proposal reported).

### Dialectic Mode (`--rigor dialectic`)

```bash
/quorum "Should we open-source our core product?" --rigor dialectic
```

Two agents enter a Socratic dialogue that spirals deeper through contradiction:

- **Thesis** states a position with evidence
- **Antithesis** finds the contradiction, the unstated assumption, the edge case where it breaks
- Each round goes **deeper, not wider** — no new topics, no retreating to generalities
- The supervisor calls it when: **Synthesis** (combined position), **Bedrock** (irreducible values disagreement), or **Spark** (a new question nobody started with)

### Subteam/Org Mode (`--teams`, `--org`)

```bash
/quorum "Review our BCI security posture" --teams "engineering,legal,clinical"
/quorum "Should we ship this feature?" --org
```

When a question crosses 3+ domains with different incentives, flat swarms produce noise. Subteams solve this with **local consensus before global debate.** Teams deliberate internally, then team leads cross-challenge each other.

Two structural roles appear:
- **Socrates** asks each team lead ONE question targeting their weakest point. Prevents echo chambers.
- **Plato** audits every claim: SUPPORTED or UNSUPPORTED. Prevents hallucination.

### Swarm Mode (`--swarm`)

```bash
/quorum "Impact of EU AI Act on BCI startups" --swarm
/quorum "Will neural data be biometric by 2028?" --swarm --predict --size 200
/quorum "Red team our auth" --swarm --branches "network,app,social,physical,supply-chain"
```

Scales from 20 to 1000+ agents using taxonomy-partitioned territories and environment-based coordination. The supervisor reads emerging patterns, not individual reports. (The environment server is currently prompt-orchestrated — true scaling depends on effective summarization.)

**Prediction mode** (`--predict`) adds probabilistic activation, sentiment trajectory tracking, and coalition detection for Delphi-method forecasting.

**[Full guide: when to use each mode →](docs/GUIDE.md)**

### Superpower Mode (Auto-Detected)

When you say "build", "implement", "create", "scaffold", "write a", "set up", or "add feature", the supervisor auto-triggers the superpower pipeline. No flag needed.

```bash
/quorum "Build a REST API for user auth with JWT" --max
```

**What happens:**

1. Supervisor detects implementation intent ("Build") → triggers superpower pipeline
2. **Decomposition agent** generates a PRD with TDD enforcement:
   - Exact file paths for every file created or modified
   - Bite-sized tasks (one action each, 2-5 minutes)
   - Each task: write failing test → verify fail → implement → verify pass → commit
   - Machine-verifiable acceptance criteria (not "works correctly" but "returns 200 with valid JWT containing user_id claim")
3. **Adversarial convergence** stress-tests the PRD (only with `--max`):
   - Architect: "Are the boundaries right? Missing abstractions?"
   - Breaker: "Which acceptance criteria are ambiguous? Edge cases?"
   - TDD Enforcer: "Is every task actually testable? Assertions specific enough?"
   - Pragmatist: "Is this over-engineered? Can tasks be eliminated?"
   - Judge: Computes convergence score. Declares READY or sends back for revision.
4. **Output:** `_swarm/prd-user-auth.md` with Ralph loop command

```bash
# Run the PRD autonomously
./quorum/scripts/ralph.sh --prd _swarm/prd-user-auth.md
```

**The Ralph loop** executes each task with fresh context: reads PRD + progress.md → picks next task → TDD (test → fail → implement → pass → commit) → updates progress → every 3 tasks runs Quorum review to catch regressions → repeats until done.

**With vs without `--max`:**

| | `/quorum "Build X"` | `/quorum "Build X" --max` |
|--|---------------------|--------------------------|
| PRD generation | 5 agents (lighter) | 7-15 agents (full decomposition) |
| Stress-test | No adversarial review | Full convergence (5 personas, C ≥ 0.8) |
| Output quality | Good for small features | Battle-tested for production systems |

No `--superpower` flag exists. Same capability, zero cognitive load.

### Reviewers Mode (`--reviewers`)

Top-down sequential review pipeline. Unlike default Quorum (horizontal debate), `--reviewers` runs phases in cascade — each phase's output feeds the next. Personas are dynamically assembled based on the prompt topic, not hardcoded.

```bash
# Review a plan through domain-appropriate phases
/quorum "Review this API design for production readiness" --reviewers --artifact api-spec.md

# Review an app design top-down
/quorum "Is this iOS app architecture ready to ship?" --reviewers --artifact ARCHITECTURE.md

# Review a security posture
/quorum "Evaluate our auth implementation" --reviewers --artifact auth-flow.md
```

**How it works:**

1. **Intake & Assembly** — Supervisor reads the prompt, assembles 3-5 review phases with topic-appropriate personas (e.g., Security: Threat Modeler → Architect → Penetration Tester → Compliance)
2. **Sequential Review** — Each phase runs one reviewer who receives the original prompt + artifact + ALL prior phase outputs. Findings are classified as **Mechanical** (auto-decidable) or **Taste** (needs human judgment)
3. **Auto-resolution** — Mechanical findings are auto-resolved using decision principles (completeness, blast radius, pragmatic, DRY, explicit over clever, bias toward action)
4. **Final Gate** — Only taste decisions surface for your approval. Cross-phase themes are highlighted

**--reviewers vs Default vs --max:**

| | Default (horizontal) | --max (adversarial) | --reviewers (vertical) |
|--|---------------------|--------------------|-----------------------|
| Topology | Flat panel | Iterative convergence | Sequential cascade |
| Agent relationship | Peers debate | Attackers vs defenders | Each builds on previous |
| Decision style | Emerges from debate | Survives sustained attack | Auto-decided, taste surfaced |
| Best for | Ambiguous questions | Stress-testing decisions | Reviewing concrete artifacts |
| Output | Synthesized verdict | Converged/tension/exhausted | Approved with overrides |

### Rules for Prompts That Don't Produce Garbage

1. **Name the exact pipeline, not the app.** "Fix the detection pipeline" not "fix Spot"
2. **State the current broken state.** "Currently nothing detects" not "make it work"
3. **Attach the design doc.** `--artifact` gives the AI the spec, not vibes
4. **One pipeline per prompt.** Don't combine LiDAR + detection + onboarding + App Store
5. **Include a constraint verb.** "Trace before touching code" forces investigation before editing

The single best improvement: **always include `--artifact` pointing to your design doc.** That's the difference between "build me a thing" and "build this specific thing to this spec."

```bash
# Bad: vibes
/quorum "Build the auth system" --max

# Good: spec-driven
/quorum "Build the auth system to this spec" --artifact AUTH-DESIGN.md --max
```

### Subagent Validation (Fresh-Context Testing)

For validation and testing phases, Quorum can spawn Claude Code subagents — fresh instances with zero knowledge of the main session's conversation. The subagent does not know what the "right" answer is, so it tests honestly. This eliminates confirmation bias structurally, not just by prompt instruction.

```bash
# Main session designs test protocol with pass/fail criteria
# Subagent executes in fresh context — no anchoring, no expected outcomes
# Subagent reports raw PASS/FAIL with evidence
# Main session interprets results — discrepancies are the signal
```

This pattern proved its value in production: a validation subagent caught a real bug that the main session missed, because the main session was anchored on prior discussion. See [Architecture: Subagent Execution Model](docs/ARCHITECTURE.md#subagent-execution-model) for the full specification.

## What Makes Quorum Different

Every multi-agent tool in the Claude Code ecosystem does the same thing: splits a task, hands each piece to an agent, collects answers, merges them. More hands, same brain. If all 8 agents hallucinate the same thing, you get a confident, well-formatted wrong answer.

Quorum is the only plugin that asks: *"How do we know this answer is actually right?"*

**What Quorum adds that none of them have:**

- Agents assigned **opposing positions**, forced to defend them with evidence
- A **Devil's Advocate** who argues against the majority — because the answer that survives pushback is the one worth trusting
- Challenge agents get **less context on purpose** so they can't just agree with everyone
- Research agents search **different sources with different terms** — not the same Google result five times
- The supervisor **judges reasoning quality**, not vote counts — a well-argued minority beats a hand-waving majority
- **Converse mode** — research-backed adversarial convergence where critics must counter-propose, not just attack
- **Dialectic mode** — two agents drill through contradiction across multiple rounds until they hit bedrock
- **Swarm mode** — 1000+ agents with taxonomy-partitioned territories and emergent pattern detection

### Anti-Boxing

When you give an AI a project profile and a classification gate, it starts only pulling from familiar domains, only spawning agents it already knows. The profile IS the box. Every efficiency optimization that prunes "low-signal" agents is killing exactly the perspectives that would break the box.

**Anti-boxing** is Quorum's structural guarantee that the system keeps reaching outside its own comfort zone. It is not an established term in AI/ML literature — it draws from lateral thinking (de Bono), structured dissent (Janis), adversarial robustness, and cognitive diversity research. Anti-boxing as a named architectural pattern for multi-agent systems is original to Quorum.

**The 6 anti-boxing rules:**

1. **Domain Outsider never from the profile's default domains.** The outsider's value comes from NOT being in the profile.
2. **Classification gate scores the question, not the project.** A business question in a research repo gets business agents.
3. **Condition-based outsider injection.** High consensus with low challenge → inject a lateral thinker.
4. **Exploratory queries invert the profile.** "What am I missing?" spawns from domains the profile doesn't list.
5. **Adversarial agents are immune to pruning.** Devil's Advocate and Provocateur can never be killed by efficiency rules.
6. **Inverted early termination.** When everyone agrees, scrutiny goes UP. Unanimous consensus is the highest-risk scenario.

## Validation & BS Detection (5 layers)

| Layer | What It Does |
|---|---|
| Source Grading | Every finding rated STRONG / MODERATE / WEAK / UNVERIFIED |
| Contradiction Check | Catches when agents disagree AND when they agree without evidence |
| Hallucination Red Flags | Supervisor checklist for fabricated stats, fake citations, too-clean numbers |
| Adversarial Validation | Reviewer challenges the synthesis (web search preferred, subagent with fresh context, or same-session agent review as fallback) |
| Transparent Output | Report shows what's verified, what's unresolved, what couldn't be checked |

**The rule: If it can't be sourced, it gets flagged. If it can't be verified, it says so. If agents disagree, both sides are shown. You decide — not the AI.**

### Validation Verdicts (for review/audit workflows)

| Verdict | Meaning |
|---------|---------|
| **VALIDATED** | Evidence found, no refutation |
| **FLAGGED** | Below threshold or panel disagreed — needs human review |
| **BLOCKED** | Consensus: unsupported, contradicted, or hallucinated |

## Examples

It's not a developer tool. It's a thinking tool. Any question where you'd want a smart friend to push back before you commit.

```bash
# Quick opinion — 5 agents, done in 2 minutes
/quorum "Should we use PostgreSQL or DynamoDB for our new service?"

# Stress-test a decision — full adversarial convergence
/quorum "Should we build or buy our auth system?" --max

# Build something — auto-detects superpower mode, generates battle-tested PRD
/quorum "Build a REST API for user auth with JWT" --max
# → Supervisor detects "Build" → generates PRD with TDD + acceptance criteria
# → Adversarial convergence stress-tests the PRD
# → Outputs: _swarm/prd-user-auth.md with Ralph loop command
# → Run: ./quorum/scripts/ralph.sh --prd _swarm/prd-user-auth.md

# Settling an argument — auto-routes to dialectic (binary question detected)
/quorum "Is a hot dog a sandwich?"

# Buying a house
/quorum "Found a house for $450K, 1960s build, no inspection. What should first-time buyers worry about?"

# Career crossroads — auto-routes to dialectic (two-option tension)
/quorum "Making $180K in fintech, offered $140K at a climate startup. Worth the pay cut?"

# Before a job interview
/quorum "Interviewing at Stripe for senior security. What will they ask I'm not preparing for?"

# Evaluating a business idea
/quorum "App that matches dog owners for group walks. Business or feature?" --max

# Document review
/quorum "Review this contract for risks I might miss" --artifact contract.pdf

# Sequential review pipeline — assembles domain-appropriate reviewers
/quorum "Review our payment flow for PCI compliance" --reviewers --artifact payment-flow.md

# Research landscape — auto-routes to web research
/quorum "Complete landscape of EEG-based authentication methods"

# Validate prior research (two-stage)
/quorum "Fact-check for hallucinations" --artifact _swarm/eeg-auth.md --no-web

# Massive scale prediction — swarm auto-engages at 20+
/quorum "Will BCI startups consolidate or fragment by 2028?" --set 200

# Exhaustive red team at scale
/quorum "Red team our auth system — every attack vector" --set 100

# Private, no web searches
/quorum "Evaluate our internal security posture" --artifact audit.md --no-web

# See the plan before spending tokens
/quorum "Microservices or monolith?" --max --dry-run
```

## Options

**Three tiers:**

| Tier | Flag | Agents | What Happens |
|------|------|--------|-------------|
| Default | *(none)* | 5 | SME panel debates, supervisor synthesizes |
| Max | `--max` | 7-15 | Full adversarial convergence, teams/dialectic/superpower auto-selected |
| Reviewers | `--reviewers` | 3-5 phases | Sequential review cascade, auto-decide mechanical, surface taste |
| Custom | `--set N` | N | Swarm auto-engages at 20+ |

**Five optional flags:**

| Flag | Why It Can't Be Auto-Detected |
|------|-------------------------------|
| `--artifact PATH` | Supervisor can't know which file you mean |
| `--reviewers` | User wants vertical sequential review, not horizontal debate |
| `--no-web` | Privacy choice only the user can make |
| `--ponder` | User explicitly wants Q&A before the swarm runs |
| `--dry-run` | User wants to see the plan without spending tokens |

**Everything else is auto-detected.** The supervisor picks mode, structure, rigor, research, teams, dialectic, superpower — based on what you asked and what it finds.

## Output Format

Every standard report includes:
- **Executive Summary** — 3-5 sentences, degree of consensus, key finding
- **Supervisor's Assessment** — The quorum's own judgment (most valuable section)
- **Confidence & Verification** — What's backed by evidence vs. supervisor judgment
- **Disagreement Register** — Unresolved disputes with both positions preserved
- **Priority Actions** — Ranked by impact, not by how many agents mentioned them
- **Blind Spots** — What the team collectively could not evaluate

Converse mode adds:
- **Attack Resistance Map** — Each surviving component and which attacks it withstood

Swarm reports add:
- **Emergent Consensus** — Findings agents in unrelated territories reached independently (strongest signal)
- **Polarizations** — Genuine disagreements with evidence on both sides
- **Cascades** — Findings that changed the swarm's trajectory
- **Coalition Map** — Which territory groups aligned on which recommendations
- **Sentiment Trajectory** — How the swarm's collective position evolved across rounds

## Honest Limitations

Quorum is a reasoning quality tool, not a magic truth machine. These are the known structural limitations:

1. **The validation gate is not truly independent.** Phase 5's agent review uses a separate agent in the same Claude session. This is prompt-level independence, not structural independence. Lorenz et al. (2011) showed even mild social influence narrows diversity. Web search fact-checking (Method 1) provides genuinely independent evidence; agent review (Method 2) provides useful-but-limited adversarial review. Neither is a substitute for human review.

2. **The environment server is simulated.** Swarm mode's Environment Server and Pattern Detection are prompt-orchestrated, not a persistent runtime service. The supervisor summarizes agent outputs — the quality of pattern detection depends on summarization quality, not a dedicated algorithm. True O(patterns) scaling is a design goal, not a current guarantee.

3. **Agent count scaling is heuristic.** The Task Classification Gate (score 0-12 → agent count 3-17) uses operational heuristics, not research-derived thresholds. The research supports specific tiers: 3 (minimal), 5-7 (synchronous optimum per Dunbar/Woolley), then jump to asynchronous/swarm. The intermediate counts (8, 10, 14) are interpolated.

4. **Hallucination is structural.** No amount of multi-agent debate eliminates hallucination. Quorum makes it visible and reduces it. It does not and cannot eliminate it. Every report is a starting point for human judgment.

<details>
<summary><strong>Version History</strong></summary>

### v6.0.0 — Reviewers Mode (2026-03-26)
Sequential review pipeline (`--reviewers`). Dynamic persona assembly per topic. Mechanical/taste finding classification. Auto-resolution with decision principles. Converse mode prompts documented.

### v5.2.0 — Converse Mode (2026-03-22)
Research-backed iterative adversarial convergence. 5-7 agents, 40/60 adversarial ratio, 10 peer-reviewed citations. Adversarial minimum raised from 1→2 for all swarm sizes ≥5 (Moscovici 1969). Validation gate honesty disclosure. Swarm O(patterns) honesty disclosure.

### v5.1.0 — Outcome Predictor (2026-03-22)
Outcome Ledger, Calibrate mode, Monitor mode, Structured Seed Data, Visualization Export, Temporal Simulation.

### v5.0.0 — Swarm Mode (2026-03-22)
20-1000+ agents with MECE taxonomy, environment-based coordination, activation scheduling, prediction mode. Inspired by MiroFish/OASIS.

### v4.1.0 — Divergence Engine (2026-03-17)
Provocateur archetype, EXPLORE mode, structural protections, security hardening.

### v4.0.0 — Adaptive Intelligence (2026-03-17)
Project Profiles, Task Classification Gate, Config Transparency Block, Adaptive Output Templates.

### v3.2.0 — Security Hardening (2026-03-17)
Removed shell access from agent manifest, injection defense, credential detection.

### v3.1.0 — Epistemic Quality Gate (2026-03-17)
Two-stage research + validation workflow. VALIDATED / FLAGGED / BLOCKED verdicts.

### v3.0.0 — Subteams & Dialectic (2026-03-14)
Subteam/Org modes, Socrates + Plato, Dialectic mode, 5-layer validation pipeline.

[Full changelog →](docs/CHANGELOG.md)
</details>

## On Hallucination

No LLM is hallucination-proof. Not GPT-4. Not Claude. Not any model running inside Quorum. Hallucination is not a bug — it is a structural property of how these systems work.

Every transformer output is a probability sample from a learned distribution, not a fact lookup (Vaswani et al. 2017). Deletang et al. (2024) showed that language modeling and lossless compression are mathematically equivalent — transformers are powerful general-purpose compressors. But a model with finite parameters cannot losslessly encode a training corpus with greater entropy (Shannon 1948). The weights are necessarily a lossy compression, and lossy decompression produces artifacts. In images, those artifacts are JPEG blocks. In language models, they are hallucinations (Chlon et al. 2025). The math does not permit zero error.

This is not unique to machines. Artificial neural networks were modeled after biological neurons (McCulloch & Pitts 1943). Biological brains also confabulate — reconstructing memories from statistical patterns rather than retrieving stored records (Bartlett 1932, Schacter 1999, Loftus & Palmer 1974). Both systems fill gaps with plausible guesses. The difference is that we built the LLM, so we can study the mechanism.

Quorum's 5-layer validation pipeline, adversarial agents, and evidence audits reduce hallucination. They make it *visible*. They do not eliminate it. Every Quorum report is a starting point for human judgment, not a replacement for it.

Models will get more accurate. The rates will shrink. They will not reach zero, because probability in an indeterministic world means errors are structural, not temporary. That is what keeps us learning.

**[Full scientific explanation with citations →](docs/SAFETY.md#0-on-hallucination-why-no-llm-is-hallucination-proof)**

## Documentation

- **[Usage Guide](docs/GUIDE.md)** — When to use flat vs converse vs dialectic vs subteams vs swarm. Decision matrix, cost guide, examples
- **[Architecture](docs/ARCHITECTURE.md)** — Full phase-by-phase technical specification
- **[Prompt Templates](docs/PROMPTS.md)** — All agent templates with variable reference
- **[Safety & Privacy](docs/SAFETY.md)** — Guardrails, privacy disclosure, tool permissions
- **[Privacy Policy](https://qinnovate.com/privacy)** — Full privacy policy for all qinnovate tools
- **[Changelog](docs/CHANGELOG.md)** — Version history and what changed
- **[Releases](https://github.com/qinnovates/quorum/releases)** — GitHub releases with download links

## License

MIT

## Author

Kevin Qi — [qinnovate.com](https://qinnovate.com)
