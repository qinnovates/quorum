# Quorum Usage Guide

> When to use what — flat swarms, subteams, dialectic, and validation workflows.

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
| Fact-check prior research | `/quorum "validate" --artifact report.md --rigor high` | Validation workflow |

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

### Mandatory adversarial agents (scales with size)

| Swarm Size | Adversarial Agents |
|---|---|
| 3-5 (`--lite`) | Devil's Advocate |
| 6-8 | Devil's Advocate + Naive User |
| 9+ | Devil's Advocate + Naive User + Domain Outsider |

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
- At least 1 adversarial team (their job is to challenge)
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

## Research + Validation Workflow

Use one swarm to research, then a separate Quorum panel to fact-check what it found.

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

## Cost and Performance Guide

| Mode | Agents | Tokens | Time | Best For |
|------|--------|--------|------|----------|
| `--lite` | 3 | ~50K | 1-2 min | Quick opinion |
| Default | 5 | ~150K | 2-4 min | Standard question |
| `--full` | 8 | ~300-500K | 3-8 min | Important decision |
| `--rigor dialectic` | 2 + supervisor | ~200K | 3-6 min | Deep understanding |
| `--org` (3 teams) | 17 | ~400-600K | 5-10 min | Cross-domain complexity |
| `--org` (4 teams) | 22 | ~500-800K | 8-12 min | Large-scale validation |
| Two-stage validation | 8 + 5 | ~480K total | 8-10 min | Research + fact-check |

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
