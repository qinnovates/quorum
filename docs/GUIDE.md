# Quorum Usage Guide

> When to use what — flat swarms, subteams, dialectic, and validation workflows.

---

## Quorum's Tier Architecture

Quorum is not a flat system. It operates as a **tiered hierarchy** where each tier serves a different epistemological function. Understanding the tiers explains why a 3-agent lite swarm and a 17-agent org produce fundamentally different kinds of answers — not just more or less of the same thing.

### The 5 Tiers

```
Tier 0: Context Engine (reads project, classifies task, auto-configures)
  │
Tier 1: Supervisor (polymath orchestrator — designs the debate, writes the verdict)
  │
Tier 2: Structural Roles (Socrates questions, Plato audits — cross-cutting, no position)
  │
Tier 3: Team Leads / Analysis Agents (domain experts — take positions, debate, synthesize)
  │
Tier 4: Research Agents / Team Members (evidence gatherers — search, cite, report)
```

**Each tier has a distinct job. No tier does the work of another.**

### Tier 0: Context Engine (Pre-Phase 0)

**Job:** Read the project, classify the task, configure the swarm.

This tier runs before any agent is spawned. It reads the project profile, scores the query on 4 dimensions (domain count, certainty demand, scope, artifact), and selects mode, agent count, structure, and rigor. It shows the Config Transparency Block so the user can approve or override.

Tier 0 is the only tier that talks to the user before the swarm runs. Every other tier works internally.

**What it does NOT do:** Tier 0 does not analyze the question. It does not form an opinion. It configures the instrument — it does not play it.

### Tier 1: Supervisor (Phase 0-7)

**Job:** Design the intellectual structure of the debate, make executive calls, write the synthesis.

The supervisor is a polymath — not an expert in any single domain, but capable of understanding any domain well enough to ask the right questions. The supervisor:

- Decides what the real question is (often different from the literal words)
- Picks which experts to spawn and what positions they should argue
- Engineers the collision points — where will experts disagree productively?
- Reads all agent outputs and writes the final synthesis with editorial judgment
- Weighs reasoning quality over vote counts — a well-argued minority beats a hand-waving majority

**The supervisor is the most important agent.** Every other agent produces raw material. The supervisor produces the answer.

**What it does NOT do:** The supervisor does not search the web, does not take a domain position, and does not defend a stance. If the supervisor starts arguing with its own agents, the architecture has failed.

### Tier 2: Structural Roles (Socrates + Plato)

**Job:** Prevent the three failure modes of multi-agent reasoning.

Structural roles are not experts. They do not take positions. They operate orthogonally to the content debate:

**Socrates** prevents echo chambers. After team leads present their positions, Socrates asks each lead ONE question targeting the weakest point in their argument. The question must be specific, not rhetorical. Socrates cannot state an opinion. The team lead must answer before the supervisor proceeds.

**Plato** prevents hallucination. Plato reads every claim from every team and checks: is this SOURCED or ASSERTED? Plato does not evaluate whether claims are right or wrong — only whether they are supported by evidence. The Evidence Audit table makes unsupported claims visible.

**Why they are separate from Tier 3:** Domain experts (Tier 3) are incentivized to build strong positions. Socrates and Plato are incentivized to dismantle weak ones. Mixing these incentives in the same agent produces agents that half-argue and half-question — doing neither well.

**When they appear:** Socrates and Plato only appear in subteam/org mode (9+ agents). In flat swarms, the Devil's Advocate partially fills this role, but without the structural separation.

### Tier 3: Team Leads / Analysis Agents

**Job:** Take positions, argue them with evidence, debate each other.

In flat swarms, these are individual analysis agents — each with a unique persona, stance, and seed questions. They work independently, then cross-review each other's positions.

In subteam/org mode, these are **Team Leads** who synthesize their team members' work into a single Team Position, then present to the supervisor and respond to cross-team challenges.

**Key principle:** Tier 3 agents are assigned positions, not asked for opinions. The supervisor tells them what stance to argue and from what framework. This is deliberate — unassigned agents converge on the same comfortable consensus. Assigned positions force the swarm to explore the full solution space.

**What they do NOT do:** Tier 3 agents do not search the web (that's Tier 4). They do not question the overall structure (that's Tier 2). They argue their assigned domain with the evidence they're given.

### Tier 4: Research Agents / Team Members

**Job:** Gather evidence. Search, cite, report.

Research agents get non-overlapping search partitions (different sources, different facets, different date ranges) to prevent duplication. They produce structured findings with sources, evidence tiers, and conflict notes.

Team members in org mode work similarly — each assigned a unique angle within their team's domain. Their output goes to the Team Lead (Tier 3), not directly to the supervisor.

**Key principle:** Tier 4 agents see the least context. They know their search partition and the topic. They do not know what other agents found, what the supervisor is thinking, or what conclusion is forming. This isolation prevents anchoring — they can't be biased by information they don't have.

**What they do NOT do:** Tier 4 agents do not interpret their findings. They do not recommend actions. They report what they found and what they didn't find. Interpretation is Tier 3's job.

### How the Tiers Interact

```
Tier 0: "This is an iOS accessibility project asking about authentication.
         Score: D=2 C=2 S=1 A=0 → 5. Config: 6 agents, flat, medium rigor."

Tier 1 (Supervisor): "The real question is device-level auth for embedded hardware.
         I'll spawn: Security Architect, iOS Engineer, Accessibility Expert,
         Hardware Auth Specialist, Devil's Advocate, Domain Outsider (economist)."

Tier 4 (Research): [2 agents search different sources, return evidence pool]

Tier 3 (Analysis): [4 agents argue positions from their domains using the evidence]
         Security Architect: "mTLS with hardware-bound certs"
         iOS Engineer: "Sign in with Apple, it's built-in"
         Accessibility Expert: "Biometric + VoiceOver passthrough"
         Devil's Advocate: "All three assume a reliable network connection"

Tier 2 (Socrates): "Security Architect — your mTLS recommendation assumes
         the device has a TPM. Does this hardware have one?"
         (Plato): "Accessibility Expert's claim about VoiceOver passthrough
         latency is UNSUPPORTED — no source cited."

Tier 1 (Supervisor): [Reads all positions, Socrates' questions, Plato's audit]
         Synthesis: "Hardware-bound tokens with biometric fallback.
         mTLS is correct but requires TPM verification first.
         VoiceOver passthrough needs latency benchmarking before commit."
```

### Why Tiers Beat Flat

| Property | Flat (5 agents) | Tiered (17 agents, org) |
|----------|----------------|------------------------|
| Information flow | Everyone sees everything → anchoring | Controlled: each tier sees what it needs |
| Disagreement quality | Agents with different names agree on the same thing | Teams with different incentives surface real tensions |
| Evidence handling | Mixed with opinions in the same agent output | Separated: Tier 4 gathers, Tier 3 interprets, Tier 2 audits |
| Hallucination detection | Devil's Advocate might catch it | Plato systematically audits every claim |
| Minority positions | Easily drowned by majority | Protected: Socrates forces engagement, supervisor weighs reasoning quality |
| Cost | ~150K tokens | ~400-600K tokens |
| When to use | 1-2 domains, straightforward | 3+ domains, high stakes, cross-team tension |

**The tiers are not bureaucracy. They are separation of concerns applied to reasoning.** Each tier does one thing well. The alternative — agents that simultaneously research, analyze, challenge, and synthesize — produces agents that do all four poorly.

---

## Decision Matrix: Which Mode Do I Use?

| Situation | Use This | Why |
|-----------|----------|-----|
| Quick question, one domain | `/quorum "question" --lite` | 3 agents, fast, cheap |
| Standard question, needs debate | `/quorum "question"` | 5 agents, 1 round, default |
| Complex question, needs depth | `/quorum "question" --full` | 8 agents, 2 rounds, validation gate |
| Research question, needs sources | `/quorum "question" --mode research` | Agents search the web, cite sources |
| Review a document | `/quorum "review this" --artifact file.md` | All agents analyze the file |
| 3+ domains intersecting | `/quorum "question" --org` | Auto-detects teams, hierarchical |
| Specific departments needed | `/quorum "question" --teams "eng,legal,clinical"` | You pick the teams |
| Deep philosophical/strategic question | `/quorum "question" --rigor dialectic` | 2 agents, multiple rounds, Socratic |
| Need a battle-tested solution | `/quorum "question" --converse` | 5 agents iterate, critics must counter-propose |
| Stress-test before building | `/quorum "question" --converse --full` | 7 agents, Judge decides rounds, historian + survivor |
| Fact-check prior research | `/quorum "validate" --artifact report.md --rigor high` | Validation workflow |
| High-stakes irreversible decision | `/quorum "question" --ratify` | Human sign-off before finalization |
| Pre-automation approval (Ralph loop) | `/quorum "Build X" --max --ratify` | Approve PRD before automated execution |
| Bias-free production testing | Subagent with self-contained prompt | Subagent validation (fresh context) |

---

## Prompt Optimization (`--ponder`)

Before spending 300K+ tokens on a swarm, make sure the question is right.

**Default (always on):** Supervisor silently refines vague questions before spawning.

**`--ponder` (interactive):** Supervisor asks you 2-3 clarifying questions, then generates an optimized prompt for your approval.

```bash
/quorum "How should we handle auth?" --ponder

# Quorum asks: What system? Current approach? Priority: security vs UX vs speed?
# You answer. Quorum generates a precise prompt. You approve, edit, or cancel.
```

Use `--ponder` when:
- Your question is broad ("What about security?")
- You're not sure what the swarm should optimize for
- You want to save tokens by getting the prompt right before spawning 8+ agents

---

## Flat Swarms (Default)

A flat swarm is a single panel of experts debating in parallel. No hierarchy, no teams. The supervisor coordinates everyone directly.

```
         ┌─────────────┐
         │  Supervisor  │
         └──────┬──────┘
                │
    ┌───────────┼───────────┐
    │     │     │     │     │
   A1    A2    A3    A4    A5
```

### When to use flat swarms

- The question touches 1-2 domains
- You want speed over depth
- 5-8 agents is enough coverage
- The answer doesn't require institutional perspectives (legal vs. engineering vs. clinical)

### How it works

1. Supervisor picks 5-8 experts with diverse perspectives
2. All agents work independently (no one sees anyone else's output)
3. Agents cross-review and debate each other
4. Supervisor synthesizes the verdict

### Example

```bash
# Technical decision — flat swarm is perfect
/quorum "Should we use SQLite or PostgreSQL for our embedded analytics?" --size 6

# Quick take — minimal flat swarm
/quorum "Is this API design RESTful enough?" --artifact api-spec.yaml --lite
```

### Mandatory dissent agents (scales with size)

| Swarm Size | Dissent Agents | Research Basis |
|---|---|---|
| 3 (minimum) | Devil's Advocate (1) | Asch (1951): single dissenter reduces conformity 32%→5% |
| 5-8 | Devil's Advocate + Naive User (2) | Moscovici (1969): minority of 2 establishes credible pattern |
| 9+ | Devil's Advocate + Naive User + Domain Outsider (3) | Schweiger (1986): multiple challenge perspectives improve quality |

---

## Subteam Mode (`--teams` / `--org`)

When a question crosses 3+ domains with fundamentally different incentives, flat swarms produce noise. A security researcher and a clinician use the same words to mean different things. A flat supervisor managing 15 individual perspectives loses signal.

Subteams solve this with **local consensus before global debate.**

```
                    ┌─────────────┐
                    │  Supervisor  │
                    └──────┬──────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
     ┌──────┴──────┐ ┌────┴─────┐ ┌──────┴──────┐
     │ Team Lead A │ │ Team Lead B│ │ Team Lead C │
     └──────┬──────┘ └────┬─────┘ └──────┬──────┘
            │              │              │
      ┌─────┼─────┐   ┌───┼───┐    ┌─────┼─────┐
      │  M1 │ M2  │   │ M1│M2 │    │  M1 │ M2  │
      └─────┴─────┘   └───┴───┘    └─────┴─────┘
```

### When to use subteams

- The question touches 3+ domains with **different success metrics** (engineering cares about feasibility, legal cares about liability, clinical cares about safety)
- You need institutional perspectives, not just individual opinions
- The flat swarm would be 9+ agents (subteams handle scale better)
- You want cross-team challenges ("Security, respond to Legal's concern about your recommendation")

### `--org` vs `--teams`

| Flag | What It Does | When to Use |
|------|-------------|-------------|
| `--org` | Supervisor auto-detects teams from your question | You trust the AI to pick the right departments |
| `--teams "a,b,c"` | You specify exactly which teams | You know which perspectives matter |

### How it works

**Phase 0:** Supervisor designs the org chart. Each team gets a different incentive:

| Team Type | What They Optimize For |
|-----------|----------------------|
| Engineering | Can we build it? At what cost? |
| Security | What can go wrong? What's the blast radius? |
| Clinical/Medical | Is this clinically defensible? |
| Legal/Compliance | Does this create regulatory exposure? |
| Research | What does the literature say? |
| Product/UX | Will the end user understand this? |
| Ethics | Should we do this? Who is harmed? |
| Finance/Business | Is this worth the investment? |
| QA/Validation | Does the output match the spec? |

**Phase 1:** Teams deliberate internally (parallel). Members work independently, team lead synthesizes into a **Team Position** (1-page doc: what we found, what we recommend, what we're uncertain about, what we need from other teams).

**Phase 2:** Team leads present to the supervisor. Supervisor identifies agreements, disagreements, and blind spots.

**Phase 2.5:** Socrates and Plato intervene (see below).

**Phase 3:** Cross-team challenges. The supervisor creates targeted pairs:
- "Security team: Legal found liability concerns with your recommendation. Respond."
- "Clinical team: Engineering says your safety requirement is infeasible. What's the minimum viable threshold?"

**Phase 4:** Supervisor synthesizes — arbitrating between institutional positions, not 15 individual opinions.

### Structural Roles: Socrates and Plato

Every subteam org includes two cross-cutting roles that prevent the three failure modes of multi-agent reasoning:

**Socrates (the questioner)**
- Reads all team positions
- Asks each team lead ONE question targeting the weakest point in their argument
- Cannot state an opinion — only asks questions
- Must ask the question the team would least want to answer
- Team leads must answer before the supervisor proceeds

*Socrates prevents echo chambers.*

**Plato (the evidence auditor)**
- Reads every claim from every team
- Produces an Evidence Audit table: each claim rated SUPPORTED / PARTIALLY SUPPORTED / UNSUPPORTED
- Does not evaluate right or wrong — evaluates whether claims are sourced
- Any UNSUPPORTED claim gets flagged in the final report

*Plato prevents hallucination.*

```
Phase 1: Teams deliberate (Socrates and Plato observe nothing)
Phase 2: Team leads present (Socrates and Plato read all positions)
Phase 2.5: Socrates questions each lead. Plato produces evidence audit.
Phase 3: Cross-team challenges proceed with answers and audit visible.
Phase 4: Supervisor synthesizes — must address unanswered questions and unsupported flags.
```

### Examples

```bash
# Auto-detect teams from the question
/quorum "Should we add ICD-10 codes to the TARA registrar?" --org
# → Supervisor auto-detects: Clinical, Security, Legal teams

# Manual teams — you pick the departments
/quorum "Review our BCI plugin privacy posture" \
  --teams "security,legal,clinical,product"

# Teams + size control (4 agents per team)
/quorum "Validate the registrar changes" --teams "coding,security,qa" --size 12

# Ship decision with cross-team tension
/quorum "Should we ship this feature?" --teams "engineering,legal,product"
```

### Team Composition Rules

Each team gets:
- 1 Team Lead (synthesizes, presents, responds to challenges)
- 2-4 Members (do the analysis)
- At least 1 member with a contrarian stance (internal devil's advocate)

The org must include:
- At least 1 dissent team (their job is to challenge)
- No team with more than 40% of total agents
- Teams with genuinely different success metrics

### Optimal Sizes (research-backed)

| Config | Agents | Supervisor Load | Best For |
|--------|--------|----------------|----------|
| Small | 2 teams x 3 + Socrates + Plato = 9 | 4 items | Focused questions, 2 domains |
| Default | 3 teams x 5 + Socrates + Plato = 17 | 5 items | Complex questions, 3+ domains |
| Max | 4 teams x 5 + Socrates + Plato = 22 | 6 items | Large-scale validation |

Never exceed 4 teams. If you need 5+ perspectives, two of them share an incentive — merge them.

---

## Dialectic Mode (`--rigor dialectic`)

Not a panel. Not a debate. A Socratic dialogue between two agents that spirals deeper through contradiction.

### When to use dialectic

- Philosophy, ethics, strategy — questions where "right" depends on values
- Architecture decisions — Rust vs. Go, monolith vs. microservices, build vs. buy
- Any question where your gut says "it's complicated" — dialectic finds out *why*
- You want understanding, not just an answer

### How it works

1. Supervisor identifies the core tension
2. Two agents spawned as **Thesis** and **Antithesis** — genuine intellectual positions, not strawmen
3. Each round goes **deeper, not wider**. No new topics. Every response engages the specific contradiction from the previous round
4. Thesis cannot just reassert — must refine, concede, or reveal a deeper question
5. Supervisor calls it when one of three things happens:
   - **Synthesis** — both sides arrive at a position better than either started with
   - **Bedrock** — the disagreement is irreducible (values, not facts). Now you know what you're actually deciding
   - **Spark** — the dialogue surfaces a question nobody started with. Best possible outcome

### Example

```bash
/quorum "Should we open-source our core product?" --rigor dialectic
```

Instead of 8 agents giving 8 opinions, two agents spend 4 rounds drilling into: control vs. community, moat vs. distribution, short-term revenue vs. long-term ecosystem. The synthesis might be "open-source the runtime, keep the orchestration layer proprietary" — an answer no single agent would have started with.

---

## Converse Mode (`--converse`)

Not parallel analysis. Not Socratic dialogue. An **iterative dissent-driven convergence** — the full panel stays in the room across multiple rounds, attacking proposals, building counter-proposals, and converging on what survives.

### When to use converse

- You need a **solution**, not just analysis — something that's been stress-tested before you build it
- The problem has **multiple valid approaches** and you need to find the most robust one
- You want to answer: "What would actually survive in production?"
- Architecture decisions, build vs. buy, strategy choices, vendor selection
- Any question where confident wrong answers are expensive

### How it differs from other modes

| | Standard | Dialectic | **Converse** |
|--|----------|-----------|-------------|
| Agents | 5-8 parallel | 2 + supervisor | 5-7 iterative |
| Rounds | 1 cross-review | 3-5 deepening | Judge decides (max 6) |
| Critics | 1 Devil's Advocate | 1 Antithesis | 2-3 authentic critics with counter-proposals |
| Goal | Breadth of opinion | Deep understanding | Battle-tested solution |
| Output | Synthesis | Synthesis/Bedrock/Spark | Attack-resistant solution with resistance map |

### The research behind the ratio

The 40% dissent / 60% constructive ratio isn't arbitrary. It's derived from convergent findings across jury deliberation (Nemeth 1977), dissent collaboration (Kahneman 2003), multi-agent AI debate (Du et al. 2023, Liang et al. 2023), and devil's advocate research (Schweiger et al. 1986). The critical insight from Nemeth (2001): **assigned contrarianism makes people MORE entrenched, not less.** Converse mode critics hold authentic positions and must propose alternatives — the Schweiger finding that counter-plans beat pure critique by 34%.

### The five roles

| Role | What they do |
|------|-------------|
| **Proposer** | Goes first. After Round 0, defends and adapts. Not optimistic — just starts the conversation. |
| **Realist** | "This fails because X, and here's what survives X." Constructive pessimism — every criticism includes a survival path. |
| **Breaker** | Red-teams the proposal. Self-rates attacks (CRITICAL/SIGNIFICANT/MINOR). When they say "I can't break this" — that's the strongest signal. |
| **Synthesizer** | "What's still standing?" Speaks at checkpoints. Maps what survived, what collapsed, what was modified. |
| **Judge** | Neutral arbiter. Tracks convergence. Ends the conversation when the group converges, hits irreducible tension, or exhausts returns. |

`--full` adds a **Historian** (precedent and pattern-matching) and **Survivor** (pessimistic but constructive — distinct from Synthesizer).

### How it works

```
Round 0: Proposer presents solution. Historian provides precedent.
Round 1: Realist + Breaker attack. Proposer must respond substantively.
Round 2: Proposer revises or abandons. Critics attack the fixes.
         Synthesizer checkpoint: "What's still alive?"
Round N: Judge decides when to end (max 6). No fixed range — the
         adaptive break IS the feature (Liang et al. 2023).
         Declares: CONVERGED / TENSION / EXHAUSTED
```

### Anti-duplication rule

No repetition. Every round must build on the last. Critics must counter-propose, not just attack. "This won't work" is not allowed — "This won't work because X, and here's what would survive X" is required. No free nihilism.

### Examples

```bash
# Standard converse — 5 agents, 2-3 rounds
/quorum "Best approach to real-time EEG anomaly detection?" --converse

# Full converse — 7 agents with historian, 3-4 rounds
/quorum "Should we build or buy our auth system?" --converse --full

# Converse + research — research first, then converse on findings
/quorum "Most robust BCI authentication method?" --converse --mode research

# Converse + viz — watch the convergence animation
/quorum "Microservices or monolith for our scale?" --converse --full --viz
```

---

## Research + Validation Workflow

Use one swarm to research, then a separate Quorum panel to fact-check what it found. For the strongest independence guarantees, use the [Subagent Validation](#subagent-validation-fresh-context-testing) pattern — it provides structural isolation, not just prompt-level independence.

### When to use validation

- You did research (with Quorum or any other tool) and want independent fact-checking
- You're reviewing a paper draft, literature review, or competitive analysis
- You want to catch hallucinated citations, consensus without evidence, or overclaims
- You need an audit trail separating "what we found" from "what survived scrutiny"

### Pattern 1: Two-Stage (Research, Then Validate)

```bash
# Stage 1 — Gather (expensive: 8+ agents, web search, ~400K tokens, 6-8 min)
/quorum "What are the most promising EEG-based authentication methods?" \
  --mode research --full --output _swarm/eeg-auth-research.md

# Stage 2 — Validate (cheap: 5 agents, no web, ~80K tokens, 2 min)
/quorum "Fact-check this research for hallucinations, unsupported claims, and missing perspectives" \
  --artifact _swarm/eeg-auth-research.md \
  --mode review --rigor high --no-web
```

### Pattern 2: Validate Any External Research

```bash
/quorum "Validate the claims, check citations, flag consensus without evidence" \
  --artifact my-literature-review.md \
  --mode review --rigor high \
  --personas "Fact Checker, Methodology Reviewer, Devil's Advocate, Domain Outsider"
```

### Pattern 3: Resume and Re-Validate

```bash
/quorum "Re-evaluate findings with focus on statistical claims" \
  --resume swrm_20260314_eeg_auth --rigor high
```

`--resume` loads the raw agent reports and research pool. `--artifact` loads only the rendered output.

### Validation Output

| Verdict | Meaning |
|---------|---------|
| **VALIDATED** | Supporting evidence found, no direct refutation |
| **FLAGGED** | Below confidence threshold or panel disagreed — needs human review |
| **BLOCKED** | Consensus: unsupported, contradicted, or likely hallucinated |

Every validation report includes **Panel Provenance** (who validated, their stances) and a **Coverage Notice** (what the panel could not evaluate).

---

## Subagent Validation (Fresh-Context Testing)

When Quorum needs to validate something without bias, it can spawn a Claude Code subagent — a fresh instance with zero knowledge of the main session's conversation, expectations, or conclusions.

### Why This Matters

The main session carries context baggage. After 30 minutes of discussing why a solution "should work," every agent in that session is anchored. A subagent has none of that anchoring. It tests what actually exists, not what the conversation expects to exist.

This is the difference between:
- **Same-session validation:** "I was part of the conversation. I know what the expected answer is. I will unconsciously steer toward confirming it."
- **Subagent validation:** "I have no idea what the expected answer is. I will test and report what I find."

### The Pattern

```
1. Main session designs the test protocol
   - What to test (full context)
   - Exact steps with pass/fail criteria
   - NO expected outcomes (the subagent must not know what "success" looks like)

2. Subagent executes in fresh context
   - Receives only the self-contained prompt
   - Cannot see prior discussion, predictions, or hopes
   - Runs all steps independently
   - Records raw results

3. Subagent reports back
   - Structured PASS/FAIL with evidence
   - Unexpected findings and anomalies
   - What it could not test and why

4. Main session interprets
   - Compares actual vs expected
   - Discrepancies = the signal
   - Acts on findings
```

### When to Use Subagent Validation

| Scenario | Use Subagent? | Why |
|----------|--------------|-----|
| Validating a build/deploy/release | Yes | Fresh context catches what anchored context misses |
| Fact-checking research output | Yes | Reviewer should not know which facts the researcher "wants" to be true |
| Dissent testing / red team | Yes | Attacker should not know the defenses |
| Testing code changes | Yes | Tester should not know which tests "should" pass |
| Quick opinion on a design choice | No | Overhead not worth it for lightweight decisions |
| Reviewing an artifact already in context | No | Main session already has the file loaded |
| Iterative refinement with user | No | Needs conversation history |

### Example: Production Package Validation

```bash
# Stage 1 — Build and publish the package (main session)
# ... build, test, publish ...

# Stage 2 — Validate with fresh context (subagent)
# Main session generates a self-contained prompt:
#   "Install bci-engram from PyPI. Run these 11 test phases.
#    Report PASS/FAIL for each with evidence."
# The subagent does NOT know:
#   - What version was just published
#   - What bugs were just fixed
#   - What the main session expects to pass

# Stage 3 — Interpret results (main session)
# Subagent found a real import bug that the main session
# missed because it was anchored on "we just fixed everything"
```

### Combining with Two-Stage Validation

Subagent validation composes with the existing two-stage research + validation workflow:

```bash
# Stage 1 — Research (inline, main session)
/quorum "Landscape of EEG authentication methods" --mode research --full

# Stage 2 — Validate via subagent (fresh context)
# Quorum spawns a subagent with the research output
# Subagent fact-checks citations, verifies claims, flags hallucinations
# Subagent has no knowledge of which findings the research phase
# was most confident about — it checks everything equally
```

This is stronger than same-session validation (Phase 5 Method 2) because the subagent is structurally independent, not just prompt-independent.

---

## EXPLORE Mode (for meta-questions)

When the Socratic Gate detects a meta-question, reframing request, or exploratory query ("What am I missing?", "What if we're wrong?", "What haven't I thought about?"), it auto-routes to EXPLORE mode.

### How EXPLORE differs from other modes

| Property | Standard Modes | EXPLORE Mode |
|----------|---------------|--------------|
| Agent assignment | Each agent gets a stance on the same question | Each agent gets a *different reframing* of the question |
| Goal | Find the best answer | Find the best question |
| Triage | Prune low-signal agents | Preserve all unique framings |
| Early termination | On consensus | Never — convergence is the enemy |
| Supervisor synthesis | "The answer is X" | "The most productive reframing is X because Y" |
| Default size | Score-based | 6-8 minimum |

### The Provocateur

EXPLORE mode features the **Provocateur** archetype — an agent whose job is not to analyze the question but to find a better one:

- What assumption is everyone making that might be wrong?
- What adjacent problem would be more valuable to solve?
- What would the answer look like if the question itself is the problem?

The Provocateur is exempt from Plato's evidence audit (reframings are not empirical claims) and immune to LOW-signal pruning. Their value is assessed on uniqueness, not evidence quality.

### Example

```bash
/quorum "What am I missing about our approach to neural data privacy?"
```

Instead of 5 agents analyzing the privacy approach as stated, EXPLORE mode spawns 6-8 agents who each reframe the question differently. One might ask "Is this a privacy problem or an ownership problem?" Another: "What if the real risk isn't data theft but data inference?" The supervisor synthesizes which reframing opens the most productive inquiry.

### When to use EXPLORE

- You feel stuck and don't know why
- You suspect you're asking the wrong question
- You want perspectives you haven't considered
- You want to challenge your own assumptions

---

## Combining Modes

Modes compose. Stack them for maximum rigor.

```bash
# Subteam org + high rigor + full mode
/quorum "Should we ship the neural firewall as open-source?" \
  --org --rigor high --full

# Teams + validation of a specific artifact
/quorum "Review this whitepaper for overclaims" \
  --artifact whitepaper-v8.md \
  --teams "security,clinical,legal" --rigor high

# Research + teams (teams do the research in their domains)
/quorum "Current state of BCI authentication" \
  --mode research --teams "neuroscience,security,engineering" --full
```

---

## Human Ratification (`--ratify`)

`--ratify` adds a human-approval gate to any Quorum session. After the panel deliberates and the supervisor drafts a verdict, the session pauses for your sign-off before finalizing. An auditor pass reviews the verdict for internal consistency, unsupported leaps, and missed dissent — then you approve, reject, or send it back for another round.

`--ratify` is orthogonal to depth. It controls **who has final say**, not how many agents run:

| Depth | Without `--ratify` | With `--ratify` |
|-------|-------------------|-----------------|
| `--lite` | 3 agents, supervisor decides | 3 agents, supervisor drafts, auditor reviews, you decide |
| Default | 5 agents, supervisor decides | 5 agents, supervisor drafts, auditor reviews, you decide |
| `--full` | 8 agents, supervisor decides | 8 agents, supervisor drafts, auditor reviews, you decide |
| `--max` | Full org, supervisor decides | Full org, supervisor drafts, auditor reviews, you decide |

### When to Use `--ratify`

**Use it for:**
- High-stakes irreversible decisions (architecture, vendor lock-in, public commitments)
- Before automated execution — approve the PRD before a Ralph loop builds it
- When you have context the panel doesn't (business constraints, political dynamics, timeline pressure)
- Accountability requirements — when you need a human-in-the-loop audit trail

**Skip it for:**
- Quick brainstorming and exploration
- Low-stakes questions where the panel's judgment is sufficient
- Time-sensitive decisions where the ~1.7x token cost isn't justified
- Research and validation workflows (the panel is already checking itself)

### Examples

```bash
# High-stakes architecture decision
/quorum "Monolith or microservices for our payment system?" --max --ratify

# Approve PRD before Ralph loop
/quorum "Build the LiDAR detection pipeline" --max --ratify

# Quick decision with sign-off
/quorum "Should we add Redis caching?" --ratify

# Ship decision with human gate
/quorum "Should we ship v2.0 this week?" --teams "engineering,legal,product" --ratify
```

### Cost Guidance

| Combination | Token Multiplier | When It's Worth It |
|-------------|------------------|--------------------|
| `--ratify` alone | ~1.7x base (auditor pass + potential re-run) | Irreversible decisions, pre-automation approval |
| `--max --ratify` | ~2.4x base | Maximum depth + human gate — bet-the-company decisions |
| `--lite --ratify` | ~1.7x of lite (~85K) | Quick question but you want sign-off |

The auditor pass adds cost because it reviews the full verdict for consistency, checks that dissent was addressed, and may trigger a re-run if the verdict doesn't hold up. A re-run (when the auditor finds issues) roughly doubles the cost of the deliberation phase. Most sessions don't trigger a re-run.

**Rule of thumb:** If the decision is reversible in under a week, skip `--ratify`. If it's not, the token cost is trivial compared to the cost of getting it wrong.

---

## Cost and Performance Guide

| Mode | Agents | Tokens | Time | Best For |
|------|--------|--------|------|----------|
| `--lite` | 3 | ~50K | 1-2 min | Quick opinion |
| Default | 5 | ~150K | 2-4 min | Standard question |
| `--full` | 8 | ~300-500K | 3-8 min | Important decision |
| `--rigor dialectic` | 2 + supervisor | ~200K | 3-6 min | Deep understanding |
| `--converse` | 5 | ~200-300K | 3-6 min | Battle-tested solution (Judge decides rounds) |
| `--converse --full` | 7 | ~300-500K | 5-8 min | Battle-tested + precedent (Judge decides rounds) |
| `--org` (3 teams) | 17 | ~400-600K | 5-10 min | Cross-domain complexity |
| `--org` (4 teams) | 22 | ~500-800K | 8-12 min | Large-scale validation |
| Two-stage validation | 8 + 5 | ~480K total | 8-10 min | Research + fact-check |
| Any mode + `--ratify` | Same | ~1.7x base | +1-2 min | Human-gated decisions |
| `--max --ratify` | Full org | ~2.4x base | +2-3 min | Maximum depth + human approval |

---

## Real-World Examples

### "We used a flat swarm for a technical decision"
```bash
/quorum "Should we use DuckDB-WASM or sql.js for client-side SQL?" --size 6
```
One domain (database engineering), no cross-team tension needed. 6 agents debated performance, bundle size, feature parity, and browser compatibility. Verdict: DuckDB-WASM for analytical queries, sql.js for transactional. Took 3 minutes.

### "We used subteams for a product ship decision"
```bash
/quorum "Should we ship this feature?" --teams "engineering,legal,product"
```
Three departments with different incentives. Engineering said "ready but fragile." Legal said "needs a privacy review gate." Product said "ship it, iterate." Cross-team challenge: Legal asked Engineering about data retention. Engineering revised their position. Supervisor sided with a gated launch. Took 7 minutes.

### "We used dialectic for a strategic crossroads"
```bash
/quorum "Should we open-source our security framework?" --rigor dialectic
```
Two agents debated control vs. community for 4 rounds. Hit bedrock on round 3: the real question was "do we trust the community to contribute, or do we just want the credibility of being open?" Synthesis: open-source the spec, keep the tooling proprietary. Took 5 minutes.

### "We used validation to catch hallucinated citations"
```bash
/quorum "Fact-check citations and statistical claims" \
  --artifact _swarm/literature-review.md --rigor high --no-web
```
5 validators found 3 fabricated citations (papers that don't exist), 2 statistics cited without sources, and 1 claim where the cited paper says the opposite. Panel provenance showed which validator caught what. Took 2 minutes. Saved hours of manual checking.

### "We used org mode for a cross-domain audit"
```bash
/quorum "Audit our BCI plugin for security, clinical accuracy, and legal compliance" --org
```
Supervisor auto-detected 3 teams: Security (red team focus), Clinical (accuracy of diagnostic mappings), Legal (data handling compliance). Socrates asked Security: "Your threat model assumes a local attacker — what about supply chain?" Plato flagged 4 clinical claims as UNSUPPORTED. Cross-team challenge: Clinical told Security their amplitude bounds were too restrictive for therapeutic use. Supervisor recommended tiered bounds. Took 10 minutes.

---

## Structured Seed Data (`--seed`)

Feed structured data directly to the swarm instead of relying on the text prompt alone.

### When to Use

- **Seed data:** Structured input the swarm should analyze (survey results, market signals, vendor responses, news feeds)
- **Artifact:** A document the swarm should review (code, strategy doc, paper draft)
- **Both together:** Feed seed data for context + artifact for review: `/quorum "Review this proposal against market data" --artifact proposal.md --seed market.json`

### Formats

| Format | Example |
|--------|---------|
| JSON | `/quorum "Analyze trends" --seed data/signals.json` |
| CSV | `/quorum "Review responses" --seed vendors.csv --org` |

### How Partition Works

The Seed Data Engine divides entries across agents so no agent sees the full dataset:

- **By index range:** Agent 1 gets entries 1-25, Agent 2 gets 26-50, etc.
- **By category:** If data has natural groups (JSON keys, CSV column values), agents get category-aligned slices
- **In swarm mode:** Entries map into the MECE taxonomy — each territory gets only its relevant entries

Agents cite seed data with `[Seed:23]` or `[Seed:vendor/acme]` format.

---

## Outcome Predictor (`--calibrate`, `--monitor`)

Track whether Quorum's assessments hold up over time.

### How It Works

Every session automatically logs testable claims to `_swarm/ledger.json`:
- Every VALIDATED / FLAGGED / BLOCKED assertion
- Every HIGH / MEDIUM / LOW confidence claim
- Every top-3 priority action

### Calibrating

```bash
/quorum --calibrate                    # Review all pending claims
/quorum --calibrate --session ID       # Review one session only
```

Quorum shows each pending claim and asks: CORRECT, INCORRECT, PARTIALLY_CORRECT, UNKNOWN, or SKIP. Then computes:

- **Overall calibration** — when Quorum says HIGH, how often is it right?
- **Per persona type** — are Technical agents more accurate than Dissent?
- **Per mode** — is review mode more reliable than research mode?
- **Per rigor** — does high rigor actually produce better outcomes?

Perfect calibration target: HIGH confidence should be correct 90%+ of the time.

### Monitoring Position Drift

```bash
/quorum --monitor swrm_20260322_topic  # Re-run with fresh data
```

Re-runs a previous session's question, compares the new swarm's position to the old one, and outputs a **Drift Report**: which claims still hold, which shifted, which reversed — with evidence for each shift.

Use weekly/monthly to track evolving situations.

---

## Visualization (`--viz`)

Export an interactive visualization of any session.

```bash
/quorum "question" --full --viz           # Standard session + viz
/quorum "question" --swarm --predict --viz # Swarm prediction + animated viz
```

### What You Get

Two files in `_swarm/viz/`:
- `SESSION_ID.json` — D3-compatible data (agent graph, interactions, opinion drift)
- `SESSION_ID.html` — self-contained viewer, open in any browser

### The Viewer

- **Agent graph** — force-directed network. Nodes = agents (colored by archetype), edges = interactions. Click any node for details.
- **Opinion drift chart** — line chart showing each agent's confidence across rounds. Biggest movers highlighted.
- **Timeline scrubber** — slide through rounds. Hit Play to animate the simulation at 1-second intervals. Watch opinions form, shift, and crystallize.
- **Cluster highlights** — convex hulls around agents that converged into opinion clusters.

The viewer is fully offline — no CDN, no network requests, everything inlined. Open `_swarm/viz/SESSION_ID.html` and it works.

Swarm mode viz adds: taxonomy tree, territory assignments, cross-territory handoff edges, cascade chain visualization, and sentiment trajectory animation.

---

## Temporal Simulation (`--simulate`)

Speed up time. Instead of debating what's true now, simulate what happens as events unfold.

### How It Works

```bash
/quorum "Impact of EU AI Act on BCI startups" --swarm --predict --simulate "6 months"
```

The supervisor divides "6 months" into 6 monthly steps. Each step:
1. Events are injected (agent-generated + supervisor-curated + 1 wildcard)
2. Agents react within their territories
3. Positions shift based on new conditions
4. Pattern detection tracks cascades and coalitions

### Event Sources

- **Agent-generated (default):** Each agent proposes 1-2 plausible events for the next step. The supervisor picks the most plausible.
- **Seed data:** `--seed events.json` provides a pre-planned event timeline. Use when you want to test a specific scenario ("what if competitor launches first?").
- **Wildcard:** The supervisor injects 1 unexpected event every 3 steps to prevent tunnel vision.

### Examples

```bash
# "What happens over the next 6 months?"
/quorum "EU AI Act impact on BCI" --swarm --predict --simulate "6 months"

# "Test our roadmap against these planned events"
/quorum "Roadmap survival check" --swarm --simulate "1 year" --seed planned-events.json

# "Quick tactical: what happens next month?"
/quorum "Competitor response to our launch" --full --predict --simulate "4 weeks"

# With viz — watch the predicted future unfold
/quorum "BCI market evolution" --swarm --predict --simulate "2 years" --viz
```

### The Viz Scrubber Becomes a Time Machine

With `--viz`, the timeline scrubber shows actual time labels:
- Instead of "Round 3" → "Month 3: EU DPA issues first fine"
- Event markers on the opinion drift chart show what caused position shifts
- Play at 1x/2x/4x to watch months fly by
- Pause at any point to inspect the swarm's state at that moment

### When to Use

| Scenario | Simulate? | Why |
|----------|-----------|-----|
| "What's true right now?" | No | Standard review/research |
| "What will happen over time?" | Yes | Temporal dynamics matter |
| "How does our plan survive contact with reality?" | Yes + seed events | Test specific scenarios |
| "What's the worst case?" | Yes + high wildcard rate | Stress test with unexpected events |
