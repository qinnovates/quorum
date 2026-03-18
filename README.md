# Quorum

**Orchestrate a swarm of AI experts on any question. One command, multiple minds, stress-tested answers.**

Type one command. Quorum spins up a team of specialists — researchers, analysts, skeptics, domain experts — makes them work the problem from every angle, debate each other, validate their claims, and deliver a synthesized verdict you can actually act on.

Like having a room full of smart people argue about your question before anyone gives you the answer.

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
# Install (works with Claude Code and Cowork)
claude install qinnovates/quorum

# Ask any question
/quorum "Should we use PostgreSQL or DynamoDB for our new service?"

# Review a document
/quorum "Review this proposal" --artifact proposal.md

# Deep Socratic exploration
/quorum "Should we open-source our core product?" --rigor dialectic

# Fact-check a prior research swarm
/quorum "Validate this research" --artifact _swarm/report.md --rigor high

# See the plan before running
/quorum "your question" --dry-run
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
/quorum "Should we open-source our core product?" --rigor dialectic
```

### Privacy Controls

| Flag | What It Does |
|---|---|
| `--no-web` | No web searches — everything stays local |
| `--no-save` | Nothing saved to disk |
| `--redact` | Strip URLs, names, PII from saved sessions |
| `--no-cross-ai` | Skip independent validation |

**Maximum privacy:** `/quorum "query" --no-web --no-cross-ai --no-save`

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

Quorum runs a multi-phase pipeline. You don't need to understand this to use it — just type `/quorum "question"` and go. But if you want the details:

**[Full architecture documentation →](docs/ARCHITECTURE.md)**

**Phase summary:**
1. **Setup** — Supervisor analyzes your question, picks the right experts and assigns each a unique angle
2. **Independent work** — All agents work in parallel, no one sees anyone else's output
3. **Triage** — Supervisor reads all reports, drops low-value agents, identifies key disagreements
4. **Cross-review** — Selected agents debate each other directly. Devil's Advocate challenges the majority
5. **Synthesis** — Supervisor authors the final report with editorial judgment
6. **Validation** — Independent reviewer challenges the synthesis
7. **Final report** — What survived, what's disputed, what to do next

## What Makes Quorum Different

Every multi-agent tool in the Claude Code ecosystem does the same thing: splits a task, hands each piece to an agent, collects answers, merges them. More hands, same brain. If all 8 agents hallucinate the same thing, you get a confident, well-formatted wrong answer.

Quorum is the only plugin that asks: *"How do we know this answer is actually right?"*

### Anti-Boxing

When you give an AI a project profile and a classification gate, it starts only pulling from familiar domains, only spawning agents it already knows, only asking questions it can answer. The profile IS the box. The classification gate IS the box. Every efficiency optimization that prunes "low-signal" agents is killing exactly the perspectives that would break the box.

What I call **anti-boxing** is Quorum's structural guarantee that the system keeps reaching outside its own comfort zone. It is not an established term in AI/ML literature. The concepts it draws from have other names — lateral thinking (de Bono), structured dissent (Janis groupthink prevention), adversarial robustness, cognitive diversity in teams — but anti-boxing as a named architectural pattern for multi-agent systems is original to Quorum.

Quorum walks a razor's edge. On one side: hallucination — agents confidently generating plausible nonsense. On the other: an echo chamber (no pun intended) — agents constrained so tightly that they never think outside the project's existing mental model. Both failure modes produce the same result: the user gets back what they already believe, packaged in confidence they didn't earn.

This is the direct practice of Socrates. He did not teach by giving answers. He taught by questioning assumptions — including his own. Quorum embodies this: every swarm includes agents whose job is to challenge, and the system deliberately reaches outside its own comfort zone to find perspectives the user didn't ask for.

**The 6 anti-boxing rules:**

1. **Domain Outsider never from the profile's default domains.** If the profile says "accessibility, engineering, design," the outsider comes from somewhere else. The outsider's value comes from NOT being in the profile.
2. **Classification gate scores the question, not the project.** A business question in a research repo gets business agents, not more researchers.
3. **Condition-based outsider injection.** When the last 3+ runs showed high consensus with low challenge, inject a lateral thinker. The trigger is unexamined confidence, not a counter.
4. **Exploratory queries invert the profile.** When the user asks "What am I missing?" the profile represents exactly the box they need to escape. The swarm spawns from domains the profile doesn't list.
5. **Adversarial agents are immune to pruning.** The Devil's Advocate and Provocateur can never be killed by efficiency rules.
6. **Inverted early termination.** When everyone agrees, scrutiny goes UP, not down. Unanimous consensus is the highest-risk scenario for blind spots.

Constraint kills creativity. Transparency kills hallucination. Quorum chooses transparency.

**What exists today and why it's not enough:**

- **Claude Swarm, Auto-Claude, Claude Squad** — task dispatchers. Agents never challenge each other. No source verification. No debate.
- **CrewAI, AutoGen, LangGraph** — require Python setup, YAML configs, infrastructure. Hours of work before your first question. And agents still don't argue.
- **Cursor, Copilot, Windsurf** — single agent, single perspective, coding only. No second opinion.

**What Quorum adds that none of them have:**

- Agents assigned **opposing positions**, forced to defend them with evidence
- A **Devil's Advocate** who argues against the majority — because the answer that survives pushback is the one worth trusting
- Challenge agents get **less context on purpose** so they can't just agree with everyone
- Research agents search **different sources with different terms** — not the same Google result five times
- The supervisor **judges reasoning quality**, not vote counts — a well-argued minority beats a hand-waving majority
- **Dialectic mode** — two agents drill through contradiction across multiple rounds until they hit bedrock. Doesn't exist anywhere else

The difference: other tools give you more answers. Quorum gives you *better* answers.

## Examples

It's not a developer tool. It's a thinking tool. Any question where you'd want a smart friend to push back before you commit.

**Before a job interview:**
```
/quorum "I'm interviewing at Stripe for senior security engineer. What will they ask that I'm not preparing for?"
```

**Settling an argument:**
```
/quorum "Is a hot dog a sandwich?" --rigor dialectic
```

**Naming your startup:**
```
/quorum "We're building AI tutoring for kids with ADHD. Evaluate these names: FocusOwl, Sparktrain, Brainbuddy" --rigor high
```

**Buying a house:**
```
/quorum "We found a house for $450K, 1960s build, no inspection yet. What should first-time buyers worry about?"
```

**Career crossroads:**
```
/quorum "I'm 35, making $180K in fintech, got offered $140K at a climate startup. Is the pay cut worth it?" --rigor dialectic
```

**Evaluating a business idea:**
```
/quorum "An app that matches dog owners for group walks. Is this a business or a feature?" --full
```

**Planning a difficult conversation:**
```
/quorum "I need to tell my cofounder we should pivot. They've spent 8 months on the current product. How do I frame this?"
```

**Dog health:**
```
/quorum "My 11-year-old golden retriever started limping after a walk. No swelling. What should I know before calling the vet?"
```

**Research deep-dive:**
```
/quorum "What are the most promising approaches to Alzheimer's early detection?" --mode research --full
```

**Validate research (two-stage pattern):**
```bash
# Stage 1 — Research (expensive, runs once)
/quorum "EEG-based authentication methods" --mode research --full --output _swarm/eeg-auth.md

# Stage 2 — Validate (cheap, re-run as needed)
/quorum "Fact-check for hallucinations and unsupported claims" \
  --artifact _swarm/eeg-auth.md --mode review --rigor high --no-web
```

**Document review:**
```
/quorum "Review this contract for risks I might miss" --artifact contract.pdf --rigor high
```

**Quick opinion:**
```
/quorum "Best Python web framework for a small API?" --lite
```

## Output Format

Every report includes:
- **Executive Summary** — 3-5 sentences, degree of consensus, key finding
- **Supervisor's Assessment** — The quorum's own judgment (most valuable section)
- **Confidence & Verification** — What's backed by evidence vs. supervisor judgment
- **Disagreement Register** — Unresolved disputes with both positions preserved
- **Priority Actions** — Ranked by impact, not by how many agents mentioned them
- **Blind Spots** — What the team collectively could not evaluate

## What's New in v4.1.0

**Divergence Engine + Security Hardening + SKILL.md split (1490 → 250 lines).**

- **Provocateur archetype** — challenges whether the question itself is right
- **EXPLORE mode** — for meta-questions ("What am I missing?"), each agent reframes instead of analyzes
- **Structural protections** — adversarial agents immune to pruning, Socratic follow-ups (2-3 per team), refutation resistance replaces confidence scores
- **Security:** injection defense on all templates, profile poisoning prevention, scoped file access
- **SKILL.md:** split from 1490 to 250 lines. Architecture details moved to docs/. Progressive loading.

[Full changelog →](docs/CHANGELOG.md)

## What's New in v4.0.0

**Adaptive Intelligence.** Quorum now reads your project before configuring. No more flat-5 defaults.

- **Project Profiles** — auto-generated on first run, persists context across runs. Quorum stops re-discovering your project every time.
- **Task Classification Gate** — scores every query on 4 dimensions (domain count, certainty demand, scope, artifact) and auto-selects mode, agent count, structure, and rigor.
- **Config Transparency Block** — shows what Quorum read, what it decided, and why. Approve, edit, or cancel before tokens are spent.
- **Adaptive Output Templates** — 5 output formats matched to task type: AUDIT (checklist), RESEARCH (evidence base), DIALECTIC (insight chain), DECISION (tradeoff table), ORG (executive briefing).

[Full changelog →](docs/CHANGELOG.md)

## What's New in v3.2.0

**Security hardening release.** Removed shell access from agent manifest, added prompt injection defense to all agent templates, defined credential detection patterns, fixed privacy disclosures. [Full changelog →](docs/CHANGELOG.md)

## What's New in v3.1.0

**Quorum as an epistemic quality gate.** Use one swarm to research, then a separate Quorum panel to fact-check what it found.

```bash
# Stage 1 — Gather (expensive, once)
/quorum "EEG auth methods" --mode research --full --output _swarm/eeg-auth.md

# Stage 2 — Validate (cheap, re-run as needed)
/quorum "Fact-check for hallucinations" --artifact _swarm/eeg-auth.md --rigor high --no-web
```

**Three-tier verdicts:** Every validated claim exits as **VALIDATED** (evidence found), **FLAGGED** (needs human review), or **BLOCKED** (unsupported/contradicted). Panel provenance and coverage notices included in every report.

Works on any research — not just Quorum output. Feed it a paper draft, competitor analysis, literature review, anything.

[Full release notes →](https://github.com/qinnovates/quorum/releases/tag/v3.1.0)

## On Hallucination

No LLM is hallucination-proof. Not GPT-4. Not Claude. Not any model running inside Quorum. Hallucination is not a bug — it is a structural property of how these systems work.

Every transformer output is a probability sample from a learned distribution, not a fact lookup (Vaswani et al. 2017). The model's weights are a lossy compression of training data — and lossy decompression produces artifacts (Deletang et al. 2024). In images, those artifacts are JPEG blocks. In language models, they are hallucinations. The math does not permit zero error.

This is not unique to machines. Artificial neural networks were modeled after biological neurons (McCulloch & Pitts 1943). Biological brains also confabulate — reconstructing memories from statistical patterns rather than retrieving stored records (Bartlett 1932, Schacter 1999, Loftus & Palmer 1974). Both systems fill gaps with plausible guesses. The difference is that we built the LLM, so we can study the mechanism.

Quorum's 5-layer validation pipeline, adversarial agents, and evidence audits reduce hallucination. They make it *visible*. They do not eliminate it. Every Quorum report is a starting point for human judgment, not a replacement for it.

Models will get more accurate. The rates will shrink. They will not reach zero, because probability in an indeterministic world means errors are structural, not temporary. That is what keeps us learning.

**[Full scientific explanation with citations →](docs/SAFETY.md#0-on-hallucination-why-no-llm-is-hallucination-proof)**

## Documentation

- **[Usage Guide](docs/GUIDE.md)** — When to use flat swarms vs subteams vs dialectic vs validation. Decision matrix, real-world examples, cost guide
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
