# Conductor

**Multi-agent intelligence with built-in BS detection for Claude Code.**

Conductor assembles a team of AI experts, makes them challenge each other, validates every claim, catches hallucinations, and tells you what survived the scrutiny.

Works for any domain. Medical questions, business strategy, engineering decisions, policy analysis, creative projects — one command, multiple expert perspectives, validated output.

```
/conductor "your question here"
```

Built by [qinnovate](https://qinnovate.com)

---

## Why Conductor?

When you ask AI a question, you get one perspective. It sounds confident. It might be wrong. You have no way to know.

Conductor fixes this by doing what good teams do naturally:

- **The expert** gives the informed answer
- **The skeptic** argues the other side
- **The junior** asks "wait, why?" and catches unstated assumptions
- **The outsider** brings a completely different lens

Then a supervisor — who sees all perspectives — writes the synthesis, weighing reasoning quality over vote counts. Claims without sources get flagged. Contradictions get surfaced. Easy consensus gets extra scrutiny.

**The result: answers that have been stress-tested before you see them.**

## Quick Start

```bash
# Install
claude install qinnovates/conductor

# Ask any question
/conductor "Should we use PostgreSQL or DynamoDB for our new service?"

# Review a document
/conductor "Review this proposal" --artifact proposal.md

# Deep Socratic exploration
/conductor "Should we open-source our core product?" --rigor dialectic

# See the plan before running
/conductor "your question" --dry-run
```

## Features

### Built-in BS Detection (5 layers)

| Layer | What It Does |
|---|---|
| Source Grading | Every finding rated STRONG / MODERATE / WEAK / UNVERIFIED |
| Contradiction Check | Catches when agents disagree AND when they agree without evidence |
| Hallucination Red Flags | Supervisor checklist for fabricated stats, fake citations, too-clean numbers |
| Independent Validation | Separate reviewer challenges the synthesis |
| Transparent Output | Report shows what's verified, what's unresolved, what couldn't be checked |

**The rule: If it can't be sourced, it gets flagged. If it can't be verified, it says so. If agents disagree, both sides are shown. You decide — not the AI.**

### Challenge Levels (`--rigor`)

| Level | When to Use |
|---|---|
| `low` | Brainstorming — light pushback, creative flow |
| `medium` (default) | Decisions — real debate with evidence |
| `high` | High stakes — stress test, agents actively try to break the conclusion |
| `dialectic` | Deep questions — two agents drill through contradiction Socrates-style until they hit bedrock truth |

### Dialectic Mode (Socratic Deep-Dive)

Instead of 5 agents giving parallel opinions, two agents enter a philosophical dialogue:

- **Thesis** states a position with evidence
- **Antithesis** finds the contradiction, the unstated assumption, the edge case where it breaks
- Each round goes **deeper, not wider** — no new topics, no retreating to generalities
- The supervisor calls it when one of three things happens:
  - **Synthesis** — both sides arrive at a combined position better than either started with
  - **Bedrock** — the disagreement is irreducible, comes down to values. Now you know what you're actually deciding
  - **Spark** — the dialogue surfaces a question nobody started with. The best possible outcome

```
/conductor "Should we open-source our core product?" --rigor dialectic
```

### Privacy Controls

| Flag | What It Does |
|---|---|
| `--no-web` | No web searches — everything stays local |
| `--no-save` | Nothing saved to disk |
| `--redact` | Strip URLs, names, PII from saved sessions |
| `--no-cross-ai` | Skip independent validation |

**Maximum privacy:** `/conductor "query" --no-web --no-cross-ai --no-save`

### All Options

| Flag | Default | Description |
|---|---|---|
| `--size N` | 5 | Number of expert agents (3-20) |
| `--rounds N` | 1 | Debate rounds (1-3) |
| `--full` | — | Full mode: 8 agents, 2 rounds, validation |
| `--lite` | — | Minimal: 3 agents, 1 round |
| `--rigor LEVEL` | medium | low / medium / high / dialectic |
| `--mode MODE` | auto | review / research / hybrid |
| `--artifact PATH` | — | File to review |
| `--format FORMAT` | full | full / brief / actions-only |
| `--dry-run` | — | Show plan without running |
| `--output PATH` | auto | Custom output path |
| `--resume ID` | — | Resume a previous session |

## How It Works

Conductor runs a multi-phase pipeline. You don't need to understand this to use it — just type `/conductor "question"` and go. But if you want the details:

**[Full architecture documentation →](docs/ARCHITECTURE.md)**

**Phase summary:**
1. **Setup** — Supervisor analyzes your question, picks the right experts and assigns each a unique angle
2. **Independent work** — All agents work in parallel, no one sees anyone else's output
3. **Triage** — Supervisor reads all reports, drops low-value agents, identifies key disagreements
4. **Cross-review** — Selected agents debate each other directly. Devil's Advocate challenges the majority
5. **Synthesis** — Supervisor authors the final report with editorial judgment
6. **Validation** — Independent reviewer challenges the synthesis
7. **Final report** — What survived, what's disputed, what to do next

## Examples

**Strategy decision:**
```
/conductor "Should we raise prices 20% or add a premium tier?"
```

**Technical architecture:**
```
/conductor "Evaluate microservices vs monolith for our 50-person engineering team" --full
```

**Research question:**
```
/conductor "What are the most promising approaches to Alzheimer's early detection?" --mode research
```

**Document review:**
```
/conductor "Review this contract for risks" --artifact contract.pdf --rigor high
```

**Life decision:**
```
/conductor "Should I leave my job to start a company?" --rigor dialectic
```

**Quick take:**
```
/conductor "Best Python web framework for a small API?" --lite
```

## Output Format

Every report includes:
- **Executive Summary** — 3-5 sentences, degree of consensus, key finding
- **Supervisor's Assessment** — The conductor's own judgment (most valuable section)
- **Confidence & Verification** — What's backed by evidence vs. supervisor judgment
- **Disagreement Register** — Unresolved disputes with both positions preserved
- **Priority Actions** — Ranked by impact, not by how many agents mentioned them
- **Blind Spots** — What the team collectively could not evaluate

## Documentation

- **[Architecture](docs/ARCHITECTURE.md)** — Full phase-by-phase technical specification
- **[Prompt Templates](docs/PROMPTS.md)** — All agent templates with variable reference
- **[Safety & Privacy](docs/SAFETY.md)** — Guardrails, privacy disclosure, tool permissions

## License

MIT

## Author

Kevin Qi — [qinnovate.com](https://qinnovate.com)
