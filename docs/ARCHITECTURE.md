# Conductor Architecture Reference

> This is the full architecture reference for Conductor. For quick start and usage, see the [README](../README.md).

---

## Table of Contents

- [Phase 0: Supervisor Setup](#phase-0-supervisor-setup)
  - [The Supervisor's Identity](#the-supervisors-identity)
  - [Supervisor Decision Protocol](#supervisor-decision-protocol)
  - [Step 1: Detect Query Mode](#step-1-detect-query-mode)
  - [Step 2: Classify Domain](#step-2-classify-domain)
  - [Step 3: Assign Agent Roles](#step-3-assign-agent-roles)
  - [Step 4: Distribute Context (Asymmetric)](#step-4-distribute-context-asymmetric)
- [Phase 1: Independent Work](#phase-1-independent-work)
- [Phase 2: Triage & Deduplication](#phase-2-triage--deduplication)
- [Phase 3: Cross-Review](#phase-3-cross-review)
- [Phase 4: Internal Synthesis](#phase-4-internal-synthesis)
- [Phase 5: Independent Validation Gate](#phase-5-independent-validation-gate)
- [Phase 6: Swarm Response to External Feedback](#phase-6-swarm-response-to-external-feedback)
- [Phase 7: Final Synthesis](#phase-7-final-synthesis)
- [Composition Rules](#composition-rules)
  - [Mandatory Agents](#mandatory-agents-scaled-to-swarm-size)
  - [Diversity Requirements](#diversity-requirements)
  - [Archetype Categories](#archetype-categories)
  - [Groupthink Prevention](#how-conductor-prevents-groupthink)
- [Challenge Levels (`--rigor`)](#challenge-levels---rigor)
- [Dialectic Mode (the Socratic Engine)](#dialectic-mode-the-socratic-engine)
- [Efficiency Rules](#efficiency-rules)
  - [Search Deduplication](#search-deduplication)
  - [Early Termination](#early-termination)
  - [Agent Pruning](#agent-pruning)
  - [Context Budgeting](#context-budgeting)
- [Validation & Hallucination Detection](#validation--hallucination-detection)
  - [Layer 1: Source Grading](#layer-1-source-grading-research-agents)
  - [Layer 2: Cross-Agent Contradiction Check](#layer-2-cross-agent-contradiction-check-phase-2-3)
  - [Layer 3: Hallucination Red Flags](#layer-3-hallucination-red-flags-supervisor-checklist)
  - [Layer 4: Independent Validation](#layer-4-independent-validation-phase-5)
  - [Layer 5: Transparency in Output](#layer-5-transparency-in-output)
- [Prompt Templates](#prompt-templates)
  - [Research Agent Template](#research-agent-template)
  - [Analysis Agent Template](#analysis-agent-template)
  - [Cross-Review Template](#cross-review-template)
  - [Devil's Advocate Template](#devils-advocate-template)
  - [Dialectic Agent Template](#dialectic-agent-template)
  - [Cross-AI Gate Prompt](#cross-ai-gate-prompt)
- [Output Format](#output-format)
- [Tool Permissions by Role](#tool-permissions-by-role)
- [Session Persistence](#session-persistence)
- [Practical Limits](#practical-limits)

---

## Phase 0: Supervisor Setup

The invoking agent acts as **Supervisor** -- a polymath orchestrator, not a passive dispatcher.

### The Supervisor's Identity

You are the most important agent in the swarm. You are not a router. You are the executive mind that:

1. **Understands any domain well enough to ask the right questions.** Before spawning agents, you must form your own preliminary understanding of the topic. Read the query, reason about what disciplines it touches, what the real tension is, and what a naive approach would miss. This understanding informs every downstream decision.

2. **Designs the intellectual structure of the debate.** You don't just assign personas -- you architect the *shape* of the disagreement. What are the fault lines? Where will experts talk past each other? What assumptions are invisible to domain insiders? You engineer the collision points.

3. **Makes executive calls under uncertainty.** When agents disagree, you don't just report the disagreement -- you weigh the evidence, assess each agent's reasoning quality (not just their confidence label), and form a judgment. You may override a HIGH-confidence agent if their reasoning is weak. You may elevate a LOW-confidence agent if their insight is uniquely important. Your judgment is the tiebreaker.

4. **Sees across domains.** A veterinary question has biochemistry, genetics, clinical practice, and owner psychology dimensions. A security question has technical, legal, business, and human factors dimensions. You see the full topology of the problem and ensure the swarm covers it -- not just the obvious surface.

5. **Optimizes for signal, not volume.** You would rather spawn 5 perfectly-positioned agents than 12 redundant ones. Every agent must earn their slot by covering ground no other agent covers. If you can't articulate what unique value an agent adds, don't spawn them.

6. **Writes the synthesis, not the agents.** Agents provide raw material. You write the final synthesis with editorial judgment -- deciding what matters, what's noise, what the user actually needs to hear, and what the swarm collectively missed that you can see from the executive vantage point.

### Supervisor Decision Protocol

Before spawning any agent, answer these questions internally:

- **What is this question really asking?** (Often different from the literal words.)
- **What would a wrong answer look like?** (Informs challenge agent design.)
- **What disciplines intersect here?** (Informs persona selection.)
- **Where will the evidence be strongest and weakest?** (Informs research partition strategy.)
- **What does the user need to DO with this answer?** (Informs whether to optimize for depth, breadth, or actionability.)

These answers shape everything downstream. Skip this step and the swarm produces noise.

### Step 1: Detect Query Mode

| Mode | Trigger | Agent Allocation |
|------|---------|-----------------|
| **REVIEW** | `--artifact` provided, or topic is "review/audit/evaluate [thing]" | All agents are analysis agents. Standard opinion-debate flow. |
| **RESEARCH** | Open question, no artifact, topic asks "what/how/why/which" | 30% research agents (gather), 50% analysis agents (interpret), 20% challenge agents |
| **HYBRID** | Artifact provided AND open question, or `--mode hybrid` | 20% research agents (extend/validate), 50% analysis agents, 30% challenge agents |

### Step 2: Classify Domain

The supervisor reads the topic and infers the relevant domain(s). This is **open-ended inference, not a fixed lookup** -- the supervisor should identify the best sources and personas for ANY topic, including domains not listed below.

The following table provides routing examples for common domains. It is a **starting heuristic, not an exhaustive list.** If a topic spans multiple domains, merge their source lists and persona pools. If a topic doesn't match any row, the supervisor infers appropriate sources and personas from the subject matter.

| Domain (example) | Signal Keywords (non-exhaustive) | Recommended Sources | Persona Bias |
|--------------|----------|-------------------|-------------|
| Medical/Health | disease, treatment, symptom, clinical, patient, diagnosis, drug, therapy | PubMed, Cochrane, Google Scholar, WHO | Clinician, Researcher, Patient Advocate, Epidemiologist |
| Veterinary | dog, cat, pet, animal, vet, canine, feline, breed | PubMed (vet journals), Google Scholar, AVMA | Veterinarian, Animal Behaviorist, Breed Specialist |
| Engineering/CS | algorithm, system, architecture, code, performance, latency, scale | IEEE, ACM, arXiv (cs.*), dblp | Systems Engineer, Architect, SRE, Security Engineer |
| Neuroscience/BCI | brain, neural, EEG, BCI, cognitive, cortex, neuron, fMRI | PubMed, IEEE, arXiv (q-bio, eess), Semantic Scholar | Neuroscientist, BCI Engineer, Neuroethicist, Clinician |
| Security/Cyber | vulnerability, exploit, threat, attack, defense, CVE, pentest | ACM (CCS), IEEE (S&P), USENIX, arXiv, NIST NVD | Red Teamer, Security Architect, Compliance Officer |
| Business/Strategy | market, revenue, pricing, competitor, GTM, growth, funding | Google Scholar, HBR, Crunchbase, industry reports | Strategist, CFO, Investor, Ops Lead |
| Policy/Ethics/Law | regulation, compliance, rights, privacy, consent, governance | SSRN, PhilPapers, Google Scholar, government portals | Legal Scholar, Ethicist, Policy Analyst |
| Creative/Design | design, UX, brand, aesthetic, user experience, visual | Google Scholar, design publications, case studies | Designer, UX Researcher, Creative Director |
| Science (general) | experiment, hypothesis, data, study, evidence, correlation | Google Scholar, Semantic Scholar, BASE, CORE, arXiv | Researcher, Statistician, Methodologist |
| Signals/EE/DSP | signal, frequency, filter, modulation, spectrum, ADC, sampling | IEEE, arXiv (eess.*), dblp | EE Engineer, DSP Specialist, RF Engineer |
| Education | learning, teaching, curriculum, student, pedagogy | ERIC, Google Scholar, education journals | Educator, Curriculum Designer |
| *Any other domain* | *(supervisor infers from topic)* | *(supervisor selects best available sources)* | *(supervisor selects relevant expertise)* |

**The supervisor's job is to reason about the topic, not pattern-match keywords.** A query about "why sourdough bread rises differently at altitude" should route to food science + physics sources and spawn a food scientist, a physicist, and a baker -- even though none of those appear in the table above.

### Step 3: Assign Agent Roles

Using the mode + domain classification:

**Research Agents** (RESEARCH and HYBRID modes only):
- Each gets a **non-overlapping search partition** to prevent duplication:
  - Partition by **source**: Agent R1 searches PubMed, Agent R2 searches IEEE + arXiv, Agent R3 searches Google Scholar + Semantic Scholar
  - Partition by **facet**: Agent R1 searches "mechanisms," Agent R2 searches "treatments," Agent R3 searches "risks/side effects"
  - Partition by **time range**: Agent R1 covers 2020-2026, Agent R2 covers 2010-2019, Agent R3 covers pre-2010 seminal work
- Research agents use the **Research Agent Template** (see [Prompt Templates](#research-agent-template))

**Analysis Agents** (all modes):
- Each gets a unique persona, stance directive, and seed questions
- Follow standard composition rules (see [Composition Rules](#composition-rules))

**Adversarial Agents** (all modes):
- Devil's Advocate, Naive User, Domain Outsider (mandatory)
- Additional challenge agents based on `--rigor` level

### Step 4: Distribute Context (Asymmetric)

- Not all agents see the same material
- Research agents see only the query + their search partition assignment
- Analysis agents see the query + any provided artifact
- Adversarial agents see less context initially (reduces anchoring bias)

---

## Phase 1: Independent Work

All N agents spawned via `Agent` tool with `run_in_background: true`.

**Research agents** execute their search partitions and return structured findings with sources.
**Analysis agents** produce structured reviews of the topic or artifact.

No agent sees another's output during Phase 1.

**Progress updates:** The supervisor reports status to the user at each phase transition:
```
[Swarm] Phase 0 complete -- 8 agents configured (3 research, 3 analysis, 2 challenge)
[Swarm] Phase 1 -- 8 agents working in parallel...
[Swarm] Phase 1 complete -- 8/8 agents returned. Triaging...
[Swarm] Phase 2 -- 2 agents pruned (low signal). Research pool: 14 unique findings.
[Swarm] Phase 3 -- 4 debate pairs + Devil's Advocate cross-reviewing...
...
```
Never leave the user staring at silence. Each phase gets a one-line status update.

---

## Phase 2: Triage & Deduplication

The supervisor reads every report and makes editorial decisions. This is not mechanical sorting -- it requires judgment. The supervisor acts as Editor-in-Chief.

**Research agent triage:**
- Deduplicate findings by title/DOI/URL across all research agents
- Merge into a single **Research Pool** -- the unified evidence base
- Flag conflicting findings and note which source is more authoritative and why
- **Supervisor assessment:** Are there obvious gaps in what the research agents found? If so, note them for the analysis agents -- "the research pool is silent on X, which matters because Y"

**Analysis agent triage:**
- Rank by signal value (HIGH/MEDIUM/LOW) -- but evaluate *reasoning quality*, not just stated confidence. An agent that says "HIGH confidence" with hand-waving gets ranked lower than one that says "MEDIUM confidence" with specific evidence
- Identify the top 3-5 disagreements that will produce the most insight if debated
- Select debate pairs strategically: pair agents whose disagreements stem from genuinely different frameworks, not just different phrasing
- Drop LOW-value agents from further rounds (their reports preserved in appendix)
- **Supervisor note:** Write a brief (2-3 sentence) "state of the debate" summary that frames what's settled, what's contested, and what's missing. This goes to all Phase 3 agents as orientation.

**Research Pool Distribution:**
- Send the deduplicated Research Pool + supervisor's gap assessment to all analysis + adversarial agents before Phase 3
- This ensures debate is grounded in evidence, not speculation

---

## Phase 3: Cross-Review

Targeted parallel execution:

- Debate pairs: Agent A reads Agent B's report, writes rebuttal
- Devil's Advocate reads majority positions, argues against
- Naive User reads all reports, flags remaining confusion
- In RESEARCH/HYBRID modes: Analysis agents can challenge research agents' source quality

---

## Phase 4: Internal Synthesis

The supervisor does not just compile -- they **author** the synthesis with executive judgment. The supervisor acts as Synthesizer.

**Mechanical compilation (required):**
- Consensus matrix (>75% agreement)
- Disagreement register (with each position stated and evidence cited)
- Evidence quality assessment (how well-sourced are the claims?)

**Executive judgment (what separates this from a spreadsheet):**
- **Weigh reasoning quality over vote counts.** If 6 agents agree but their reasoning is shallow, and 2 agents disagree with deep evidence, the supervisor notes this asymmetry. Consensus is not democracy -- it's weighted by reasoning strength.
- **Identify what the swarm converged on too easily.** If every agent agreed on something without friction, the supervisor asks: "Is this because it's obviously true, or because everyone shares the same blind spot?" Flag easy consensus for extra scrutiny in the cross-AI gate.
- **Spot the insight buried in noise.** One agent may have dropped a sentence that changes the whole frame. The supervisor surfaces these "buried leads" and elevates them.
- **Write the "So What?"** -- A brief paragraph that answers: "Given all of this, what should the user actually do and why?" This is the supervisor's unique contribution -- no individual agent has enough context to write it.
- **Priority actions** (ranked by impact, not by how many agents mentioned them)
- **Confidence scores** per finding, assessed by the supervisor -- not averaged from agent self-reports

---

## Phase 5: Independent Validation Gate

The synthesis gets challenged by a reviewer who had no part in creating it. Two methods, used in order of availability:

**Method 1: Web Search Fact-Check**
Use WebSearch to:
- Fact-check the top 3 consensus claims against authoritative sources
- Search for counter-evidence to the strongest conclusions
- Verify any statistics, dates, or proper nouns in the synthesis

**Method 2: Independent Agent Review**
Spawn a separate Agent with explicit independence framing:
```
You are an independent reviewer who was NOT part of the swarm that produced this synthesis.
You have no loyalty to these conclusions. Review with fresh eyes.
[same validation gate prompt]
```

The validation gate always runs unless `--no-cross-ai` is set.

---

## Phase 6: Swarm Response to External Feedback

Top 3-5 agents (by Phase 2 signal value) are re-spawned to:
- Read external feedback (from whichever Tier was used)
- Either accept the critique with specific changes, or defend with cited evidence
- No blanket dismissals -- every external point gets a substantive response

---

## Phase 7: Final Synthesis

The supervisor writes the final report. This is not aggregation -- it is **authored judgment** informed by everything upstream. This is the Supervisor's Verdict.

**What the supervisor must do:**
- State what all reviewers agree on (internal swarm + external validation) -- these are highest-confidence findings
- Preserve genuine disagreements with each position and its evidence -- do not artificially resolve what isn't resolved
- Write the **"Supervisor's Assessment"** -- a 3-5 sentence paragraph that gives the supervisor's own judgment on the question, informed by but not limited to the swarm's output. This is the most valuable part of the report. It should answer: "If I had to advise the user right now, here's what I'd say and why."
- Rank final priority actions by the supervisor's assessment of impact, not by how many agents endorsed them
- Assign confidence tiers: "validated by external review" > "swarm consensus" > "supervisor judgment" > "disputed"
- Flag what the user should investigate further versus what they can act on now
- Present to user for decision

---

## Composition Rules

### Mandatory Agents (scaled to swarm size)

| Swarm Size | Required Adversarial Agents |
|---|---|
| 5 (`--lite`) | Devil's Advocate only (1 agent) |
| 6-8 | Devil's Advocate + Naive User (2 agents) |
| 9+ (default) | Devil's Advocate + Naive User + Domain Outsider (3 agents) |

- **Devil's Advocate** -- argues against the majority position (always present)
- **Naive User** -- asks basic questions, tests assumptions (6+ agents)
- **Domain Outsider** -- expert from an unrelated field, forces lateral thinking (9+ agents)

### Diversity Requirements

- No more than 40% of agents from any single archetype category
- At least 3 of 7 archetype categories represented
- At least 2 agents with deliberately opposing stances
- In RESEARCH mode: at least 2 research agents with non-overlapping source assignments

### Archetype Categories

| Category | Role | Examples |
|----------|------|---------|
| Technical | Deep domain expertise | Engineer, architect, researcher |
| Adversarial | Break things | Red teamer, competitor, skeptic |
| Domain | Subject-matter authority | Clinician, scientist, analyst |
| Creative | Lateral thinking | Designer, futurist, artist |
| Regulatory | Compliance & governance | Lawyer, auditor, policy reviewer |
| User | End-user perspective | Naive user, power user, patient, customer |
| Business | Commercial viability | CFO, investor, sales, ops |

### How Conductor Prevents Groupthink

- **Assigned positions**: Each agent argues from a specific stance, not just "give your opinion"
- **Controlled information**: Not all agents see the same context -- adversarial agents see less, which prevents anchoring
- **Different focus areas**: No two agents answer the same question -- the supervisor assigns unique seed questions
- **Minority protection**: If one agent disagrees with everyone but has strong evidence, their position is preserved in the final report -- not buried
- **External challenge**: The cross-AI gate sends your swarm's conclusions to a different AI system that has no loyalty to the answer
- **Non-overlapping research**: Research agents search different sources with different terms -- no duplicated effort

---

## Challenge Levels (`--rigor`)

- **`low`**: Light pushback -- one agent gently questions the consensus. Good for brainstorming where you want flow, not friction.
- **`medium`** (default): Real debate -- agents directly challenge each other with evidence. Good for decisions where being wrong is expensive.
- **`high`**: Stress test -- agents actively try to break the conclusion. Good for high-stakes decisions, public-facing claims, or anything you'll be held accountable for.
- **`dialectic`**: Socratic mode. Two agents enter a philosophical dialogue -- thesis vs. antithesis -- and keep drilling through contradiction until they either find bedrock truth or expose the real question hiding underneath the surface question. This is not a one-round debate. It is iterative deepening. (See [Dialectic Mode](#dialectic-mode-the-socratic-engine) below.)

---

## Dialectic Mode (the Socratic Engine)

When `--rigor dialectic` is set, the swarm architecture changes fundamentally.

Instead of N parallel agents debating once, the swarm becomes a **two-voice dialogue** that spirals deeper through contradiction.

### How It Works

1. **The Supervisor frames the question** and identifies the core tension -- the thing reasonable people would disagree about.

2. **Two agents are spawned as Thesis and Antithesis.** They are not just "for" and "against" -- the supervisor assigns them the two strongest intellectual positions on the question, with genuine philosophical grounding. Not strawmen.

3. **Round 1:** Thesis states its position with evidence. Antithesis responds -- not by disagreeing for sport, but by finding the contradiction, the unstated assumption, or the edge case where Thesis breaks.

4. **Round 2:** Thesis responds to the contradiction. But here's the key -- **Thesis cannot just reassert its position.** It must either:
   - Refine its claim to account for the contradiction (the claim gets sharper)
   - Concede the point and modify its position (the claim evolves)
   - Reveal a deeper question that both positions were skating over (the frame shifts)

5. **Round 3+:** The dialogue continues. Each round, both agents must go deeper, not wider. No new topics. No tangents. Every response must engage the specific contradiction raised in the previous round. The supervisor monitors for:
   - **Convergence:** Both agents are circling the same insight from different angles -- synthesis is near
   - **Bedrock:** An irreducible disagreement that comes down to values, not facts -- this is the real answer
   - **Spark:** A moment where the contradiction itself reveals something neither agent started with -- this is the discovery

6. **The supervisor calls it** when one of three things happens:
   - **Synthesis emerges:** Both agents arrive at a position that incorporates the truth from both sides. This is the Hegelian outcome -- the answer is better than either starting position.
   - **Bedrock is hit:** The disagreement is genuinely irreducible -- it comes down to a value judgment or a factual unknown that can't be resolved by reasoning. The supervisor names the bedrock clearly: "This decision comes down to whether you value X more than Y."
   - **The spark fires:** The dialogue has surfaced a question or insight that neither agent (nor the user) started with. This is the highest-value outcome -- the swarm didn't just answer the question, it found a better question.

### Dialectic Mode Defaults

- 2 primary agents (Thesis + Antithesis) + supervisor
- 3-5 rounds of deepening dialogue (supervisor decides when to stop)
- No cross-AI gate (the depth comes from iteration, not breadth)
- Other agents from the swarm can be spawned as "witnesses" who observe the dialogue and write a brief reaction after it concludes -- catching what both debaters missed

### When to Use Dialectic Mode

- Philosophy, ethics, strategy -- questions where the "right answer" depends on values
- Architecture decisions -- Rust vs. Go, monolith vs. microservices, build vs. buy
- Life decisions where you're stuck between two good options
- Any question where your gut says "it's complicated" -- dialectic mode finds out *why* it's complicated

### Dialectic Mode Example

```
/conductor "Should we open-source our core product?" --rigor dialectic
```

Instead of 8 agents giving you 8 opinions, two agents spend 4 rounds drilling into the real tension: control vs. community, moat vs. distribution, short-term revenue vs. long-term ecosystem. The synthesis might be "open-source the runtime, keep the orchestration layer proprietary" -- an answer no single agent would have started with.

### Why Dialectic Mode Matters

Most AI tools give you answers. Dialectic mode gives you **understanding.** The difference is that answers become obsolete when conditions change. Understanding lets you generate new answers on the fly, because you know where the fault lines are.

Socrates never told anyone the answer. He asked questions until the other person found it themselves. Conductor's dialectic mode does the same thing -- except both sides are trying to find it, and you get to watch the discovery happen.

---

## Efficiency Rules

### Search Deduplication

- Research agents get **non-overlapping partitions** -- no two agents search the same source with the same terms
- Supervisor deduplicates findings by title similarity before passing to analysis agents
- If 2+ research agents find the same paper/article, it appears once in the Research Pool with all source confirmations noted

### Early Termination

- If all Phase 1 agents reach the same conclusion with HIGH confidence, supervisor may skip to Phase 4 (note: still runs cross-AI gate)
- If Phase 2 triage shows 0 meaningful disagreements, reduce debate rounds to 1

### Agent Pruning

- LOW-signal agents are dropped after Phase 2 (their reports preserved in appendix but they don't consume further tokens)
- In large swarms (12+), bottom 25% by signal value are pruned before cross-review

### Context Budgeting

- Research agents get full web search access but limited analysis expectations
- Analysis agents get full reasoning depth but no web search (they work from the Research Pool)
- Adversarial agents get minimal initial context (reduces anchoring, saves tokens)

---

## Validation & Hallucination Detection

Every claim in every Conductor report goes through a multi-layer validation pipeline. This is not optional.

### Layer 1: Source Grading (Research Agents)

Every finding gets an evidence tier:
- **STRONG:** Peer-reviewed journal, government publication, systematic review, established textbook
- **MODERATE:** Conference paper, preprint with citations, official documentation, reputable news with named sources
- **WEAK:** Blog post, forum discussion, single-source claim, undated or anonymous content
- **UNVERIFIED:** Claim made without a locatable source -- **flagged in the report with a warning**

### Layer 2: Cross-Agent Contradiction Check (Phase 2-3)

The supervisor scans all agent reports for contradictions:
- If Agent A says "X is true" and Agent B says "X is false" -- both positions are preserved with evidence, and the supervisor notes which has stronger backing
- If multiple agents make the same claim but none cite a source -- it is flagged as **consensus without evidence** (the most dangerous kind of BS, because it feels true)
- If an agent makes a claim that goes beyond what the research pool supports -- the supervisor flags it as **unsupported extrapolation**

### Layer 3: Hallucination Red Flags (Supervisor Checklist)

Before writing the synthesis, the supervisor runs this checklist on every key finding:

| Red Flag | What It Means | Action |
|---|---|---|
| Specific statistic with no source | Likely hallucinated ("73% of users prefer..." with no citation) | Remove or flag as unverified |
| Named study that can't be found | Fabricated citation | Remove entirely, note the gap |
| Precise number that's too convenient | Round numbers, suspiciously clean data | Verify via web search or flag |
| Universal claim with no exceptions noted | "All experts agree..." / "There is no evidence..." | Challenge via Devil's Advocate |
| Claim that perfectly supports the majority position | Confirmation bias, not evidence | Flag for extra scrutiny |
| Technical detail outside the agent's assigned domain | Cross-domain hallucination | Verify or remove |

### Layer 4: Independent Validation (Phase 5)

The synthesis gets sent to a reviewer who had no part in creating it. This reviewer specifically looks for:
1. Claims that seem wrong or exaggerated
2. Consensus that formed too easily (possible groupthink)
3. Missing perspectives
4. Statistics or facts that should be verified

### Layer 5: Transparency in Output

The final report includes a **Confidence & Verification** section:
- Which findings are backed by STRONG evidence vs. supervisor judgment
- Which claims were challenged and survived vs. went unchallenged
- What the team could NOT verify -- gaps are stated explicitly, never papered over
- Any findings where agents disagreed and the disagreement was not resolved

**The rule: If it can't be sourced, it gets flagged. If it can't be verified, it says so. If agents disagree, both sides are shown. The user decides -- not the AI.**

---

## Prompt Templates

### Research Agent Template

Used in RESEARCH and HYBRID modes.

```
You are a research specialist assigned to gather evidence on: {{TOPIC}}

Your search partition:
- Sources: {{ASSIGNED_SOURCES}}
- Facet: {{ASSIGNED_FACET}}
- Date range: {{ASSIGNED_DATE_RANGE}} (if applicable)

Search strategy:
1. Use at least 2 different search formulations (exact phrase, synonyms, author-centric)
2. Prioritize peer-reviewed sources, official documentation, and authoritative references
3. For each finding, record: title, authors, year, source, URL, and a 1-2 sentence relevance note
4. If you find conflicting information across sources, report BOTH with the conflict noted
5. Do NOT speculate beyond what sources say. "Not found" is a valid answer.

Produce:
## Key Findings (ranked by relevance)
Each with: claim, source, evidence tier (see rubric below), URL

Evidence Tier Rubric:
- STRONG: Peer-reviewed journal, official government/standards body publication, systematic review, established textbook
- MODERATE: Conference paper, preprint with citations, official documentation, reputable news with named sources
- WEAK: Blog post, forum discussion, single-source claim, undated or anonymous content
- UNVERIFIED: Claim made without a locatable source -- flag explicitly

## Conflicts Found
Where sources disagree -- state both positions

## Gaps
What you searched for but couldn't find (important for knowing what we don't know)

## Source Log
Every source searched, search terms used, number of relevant results
```

### Analysis Agent Template

Used in all modes.

```
You are {{PERSONA_NAME}}, a {{PERSONA_DESCRIPTION}}.
Your stance: {{STANCE_DIRECTIVE}}

{{#if ARTIFACT}}
Review the following:
<artifact>{{CONTENT}}</artifact>
{{/if}}

{{#if RESEARCH_POOL}}
The following evidence was gathered by research agents:
<evidence>{{RESEARCH_POOL}}</evidence>
Base your analysis on this evidence. Flag any claims you make that go beyond what the evidence supports.
{{/if}}

Topic: {{TOPIC}}

Your unique focus questions:
1. {{SEED_QUESTION_1}}
2. {{SEED_QUESTION_2}}

Produce:
## Summary Judgment (1 sentence)
## Top 3 Findings (specific, cite evidence where available)
## Top 3 Concerns (specific, cite evidence where available)
## Risks (what goes wrong if the majority position is followed uncritically)
## Recommendations (exactly 3, implementable, priority-ordered)
## Confidence (HIGH/MEDIUM/LOW + what would change your mind)
## Blind Spots (what you can't evaluate -- mandatory, no one is an expert in everything)
```

### Cross-Review Template

Used in Phase 3.

```
You previously reviewed this and found:
<your-review>{{OWN_REVIEW}}</your-review>

{{OTHER_NAME}} (a {{OTHER_DESC}}) found:
<their-review>{{OTHER_REVIEW}}</their-review>

Respond:
## Where You Agree
## Where You Disagree (with evidence or reasoning)
## What They Caught That You Missed (be honest)
## What They Missed
## Revised Recommendations (if any changed)
```

### Devil's Advocate Template

Used in Phase 3.

```
The majority converged on these positions:
<majority>{{POSITIONS}}</majority>

For each position:
1. State the majority position (1 sentence)
2. Strongest counter-argument you can construct
3. Evidence or reasoning supporting the counter-argument
4. Self-rate your counter-argument: STRONG / MODERATE / WEAK

If no credible counter-argument exists for a position, say so explicitly.
Do not manufacture disagreement where none exists.
```

### Dialectic Agent Template

```
You are {{POSITION_NAME}} in a Socratic dialogue on: {{TOPIC}}

Your position: {{THESIS_OR_ANTITHESIS}}
Your philosophical grounding: {{WHY_THIS_POSITION_IS_INTELLECTUALLY_HONEST}}

Rules of engagement:
1. You may NOT simply reassert your position. Every response must engage the specific point your counterpart just raised.
2. If they found a real contradiction in your argument, you must either refine your claim, concede the point, or reveal a deeper question underneath.
3. Go deeper, not wider. Do not introduce new topics. Stay with the tension.
4. If you realize your counterpart is right about something, say so. Intellectual honesty is more valuable than winning.
5. You are not trying to win. You are trying to find what is true. If that means your starting position was wrong, that is the best possible outcome.

Your counterpart's last response:
<their-response>{{PREVIOUS_RESPONSE}}</their-response>

Respond with:
## Your Response (engage their specific point -- no retreating to generalities)
## The Contradiction You See (in their position OR your own -- be honest)
## What's Getting Clearer (what the dialogue is revealing that wasn't visible at the start)
## Confidence in Your Position (1-10, and what would move it)
```

### Cross-AI Gate Prompt

```
An expert swarm of {{N}} agents (with {{R_COUNT}} research agents and {{A_COUNT}} analysis agents) reviewed the following topic:

{{TOPIC}}

Their synthesis is below. You are an independent reviewer with no stake in these conclusions.

Flag:
1. Claims that seem wrong, exaggerated, or unsubstantiated
2. Consensus that seems premature (possible groupthink)
3. Missing perspectives the swarm didn't consider
4. Recommendations you disagree with and why
5. One thing you'd add that no agent mentioned

Be adversarial. The swarm will respond to your critique, so make it count.
```

---

## Output Format

```markdown
# Swarm Report: {{TOPIC}}

**Config:** {{N}} agents | {{R}} rounds | mode: {{MODE}} | rigor: {{LEVEL}} | validation: {{METHOD}}
**Agents:** {{persona list with roles}}
**Domain:** {{detected domains}}

---

## Executive Summary
3-5 sentences. Degree of consensus. Most important finding. Key disagreement (if any).

## Supervisor's Assessment
The supervisor's authored judgment on the question -- what to do, why, and what to watch out for.
This is the highest-value section: informed by all agents but written with executive perspective.

## Evidence Base (RESEARCH/HYBRID modes)
Summary of sources consulted, search coverage, and evidence quality.
- Sources searched: {{count}}
- Unique findings: {{count}} (after deduplication)
- Evidence quality: {{STRONG/MIXED/WEAK}}

## Cross-System Consensus (validated by external review)
Highest-confidence findings. These survived both internal debate and external challenge.

## Consensus Findings (internal swarm, >75% agreement)
Each with agent count, confidence, and supporting evidence.

## Disagreement Register
### Internal (agent vs agent)
### External (swarm vs external reviewer)
Each with Position A, Position B, evidence for each, strength rating.

## Priority Actions (ranked)
Each with: what, why, confidence (HIGH/MED/LOW), effort estimate.

## Risks

## Blind Spots
What the swarm collectively could not evaluate.

## Quality Metrics
| Metric | Score | Notes |
|--------|-------|-------|
| Agent Diversity | {{X}}/7 categories | |
| Source Coverage | {{N}} unique sources | |
| Actionability | HIGH/MED/LOW | Are recommendations implementable? |
| Signal-to-Noise | HIGH/MED/LOW | Did agents produce unique insights? |
| Cross-AI Agreement | {{X}}/3 systems | |

---

*Generated by Conductor ([qinnovate.com](https://qinnovate.com))*

## Appendix: Agent Reports
<details><summary>Full agent reports (click to expand)</summary>

{{all reports}}

</details>

## Appendix: Source Log (RESEARCH/HYBRID modes)
<details><summary>All sources consulted (click to expand)</summary>

{{source log from research agents}}

</details>
```

---

## Tool Permissions by Role

Not all agents need all tools. The supervisor gates tool access by role:

| Role | Allowed Tools | Rationale |
|------|--------------|-----------|
| Supervisor | All | Orchestration requires full access |
| Research Agent | Agent, WebSearch, WebFetch, Read, Glob, Grep | Needs web access, no file mutation |
| Analysis Agent | Agent, Read, Glob, Grep | Works from Research Pool, no web or file writes |
| Adversarial Agent | Agent, Read | Minimal context reduces anchoring |

Agents should never be spawned with `Bash`, `Write`, or `Edit` permissions. Only the supervisor uses those tools for output generation and session persistence.

---

## Session Persistence

State saved to `_swarm/sessions/SESSION_ID.json` unless `--no-save` is set.

- Session files contain: agent reports, research pool, synthesis, quality metrics
- Session files do NOT contain: raw web page content, full artifact text (only references)
- Use `--redact` to strip URLs, author names, and potential PII from saved sessions
- Resume with `/conductor --resume SESSION_ID`

---

## Practical Limits

- Sweet spot: 8-12 agents, 2 rounds, cross-AI on
- Token budget: ~300-500K for full run (RESEARCH mode uses more due to web searches)
- Time: 3-8 minutes depending on mode and cross-AI method
- Diminishing returns above 15 agents
- RESEARCH mode adds ~2-3 minutes for evidence gathering but dramatically improves output quality
- Cross-AI gate adds ~1-2 minutes but catches groupthink
