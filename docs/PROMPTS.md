# Quorum Prompt Templates

Prompt template reference for Quorum. These templates define how each agent type thinks and responds.

---

## Table of Contents

1. [Research Agent Template](#research-agent-template)
2. [Analysis Agent Template](#analysis-agent-template)
3. [Cross-Review Template](#cross-review-template)
4. [Devil's Advocate Template](#devils-advocate-template)
5. [Dialectic Agent Template](#dialectic-agent-template)
6. [Validation Gate Prompt](#validation-gate-prompt)

---

## Research Agent Template

### When Used

**Phase 1 (Independent Work)** in RESEARCH and HYBRID modes only. Each research agent receives this template with a unique search partition so that agents cover different sources, facets, or date ranges without overlap.

### Template

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
- UNVERIFIED: Claim made without a locatable source — flag explicitly

## Conflicts Found
Where sources disagree — state both positions

## Gaps
What you searched for but couldn't find (important for knowing what we don't know)

## Source Log
Every source searched, search terms used, number of relevant results
```

### Variables

| Variable | Description | Source |
|----------|-------------|--------|
| `{{TOPIC}}` | The user's original question or research topic. | Passed directly from the `/quorum` invocation. |
| `{{ASSIGNED_SOURCES}}` | The specific databases or search engines this agent should use (e.g., "PubMed, Cochrane" or "IEEE, arXiv"). | Set by the Supervisor in Phase 0, Step 3 based on domain classification and partition strategy. No two research agents share the same source list. |
| `{{ASSIGNED_FACET}}` | The sub-topic or angle this agent should focus on (e.g., "mechanisms," "treatments," "risks/side effects"). | Set by the Supervisor in Phase 0, Step 3. Used to prevent agents from duplicating coverage. |
| `{{ASSIGNED_DATE_RANGE}}` | An optional year range filter (e.g., "2020-2026" or "pre-2010 seminal work"). | Set by the Supervisor in Phase 0, Step 3. Omitted or marked "if applicable" when time partitioning is not needed. |

### Tips

- Partition by **source** when the topic spans databases with different coverage (e.g., PubMed for clinical, arXiv for computational).
- Partition by **facet** when the topic has clear sub-questions (e.g., efficacy vs. safety vs. cost).
- Partition by **date range** when historical context matters alongside cutting-edge findings.
- You can combine strategies: one agent gets "PubMed, mechanisms, 2020-2026" while another gets "Google Scholar, risks, all time."
- Keep `ASSIGNED_SOURCES` to 2-3 databases per agent. More than that dilutes focus.
- The "Gaps" section is critical. Knowing what was *not* found is often more valuable than what was found.

---

## Analysis Agent Template

### When Used

**Phase 1 (Independent Work)** in all modes (REVIEW, RESEARCH, HYBRID). Each analysis agent receives this template with a unique persona, stance, and seed questions. In RESEARCH/HYBRID modes, agents also receive the Research Pool after Phase 2 triage.

### Template

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
## Blind Spots (what you can't evaluate — mandatory, no one is an expert in everything)
```

### Variables

| Variable | Description | Source |
|----------|-------------|--------|
| `{{PERSONA_NAME}}` | The agent's role name (e.g., "Dr. Sarah Chen," "Chief Security Architect," "Veterinary Nutritionist"). | Assigned by the Supervisor in Phase 0, Step 3 based on domain classification and diversity requirements. |
| `{{PERSONA_DESCRIPTION}}` | A brief description of the persona's expertise and perspective (e.g., "a board-certified veterinary internist with 20 years of clinical practice"). | Written by the Supervisor to give the agent a clear identity and authority scope. |
| `{{STANCE_DIRECTIVE}}` | An explicit position or angle the agent should argue from (e.g., "You believe regulatory caution is paramount" or "You prioritize engineering feasibility over theoretical elegance"). | Assigned by the Supervisor to ensure intellectual diversity. At least 2 agents must have opposing stances. |
| `{{CONTENT}}` | The full text of the artifact being reviewed (document, code, strategy, etc.). | Provided by the user via `--artifact PATH`. The Supervisor reads the file and injects its contents here. Only present in REVIEW and HYBRID modes. |
| `{{RESEARCH_POOL}}` | The deduplicated evidence base compiled from all research agents after Phase 2 triage. | Built by the Supervisor in Phase 2. Only present in RESEARCH and HYBRID modes. Not available during initial Phase 1 runs in RESEARCH mode (agents get it before Phase 3 cross-review). |
| `{{TOPIC}}` | The user's original question or research topic. | Passed directly from the `/quorum` invocation. |
| `{{SEED_QUESTION_1}}`, `{{SEED_QUESTION_2}}` | Unique focus questions that direct this agent's attention to a specific angle no other agent covers. | Written by the Supervisor in Phase 0, Step 3. Each agent gets different seed questions to prevent redundant analysis. |

### Tips

- Make `STANCE_DIRECTIVE` specific. "You are skeptical" is weak. "You believe the proposed timeline is unrealistic because similar projects historically take 2x longer" is strong.
- Seed questions should be things the Supervisor genuinely wants answered, not filler. If you cannot think of 2 unique questions for an agent, you probably do not need that agent.
- The `Blind Spots` section is mandatory for a reason: it prevents agents from overstepping their expertise. Read this section carefully during triage.
- The `{{#if}}` blocks are conditional: `ARTIFACT` is only included when the user provides `--artifact`, and `RESEARCH_POOL` is only included in research/hybrid modes.
- Persona names can be fictional but the description should reflect real expertise areas. The more specific the description, the more focused the output.

---

## Cross-Review Template

### When Used

**Phase 3 (Cross-Review)** in all modes. After Phase 2 triage, the Supervisor pairs agents into debate pairs. Each agent in a pair reads the other's Phase 1 report and writes a structured rebuttal. This template is sent to each agent in a pair.

### Template

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

### Variables

| Variable | Description | Source |
|----------|-------------|--------|
| `{{OWN_REVIEW}}` | This agent's own Phase 1 report (their full structured output from the Analysis Agent Template). | Retrieved from Phase 1 results by the Supervisor. |
| `{{OTHER_NAME}}` | The persona name of the paired agent (e.g., "Chief Security Architect"). | Taken from the paired agent's `PERSONA_NAME` assignment. |
| `{{OTHER_DESC}}` | The persona description of the paired agent (e.g., "a red team specialist focused on adversarial attack surfaces"). | Taken from the paired agent's `PERSONA_DESCRIPTION` assignment. |
| `{{OTHER_REVIEW}}` | The paired agent's full Phase 1 report. | Retrieved from Phase 1 results by the Supervisor. |

### Tips

- The Supervisor should pair agents whose disagreements are genuinely rooted in different frameworks or priorities, not just different phrasing of the same conclusion.
- The "What They Caught That You Missed" section enforces intellectual honesty. If an agent claims the other missed nothing, that is itself a signal of low-quality engagement.
- This template works best when agents have opposing `STANCE_DIRECTIVE` values from Phase 1. Pairing two agents who agree produces low-signal output.
- Keep the cross-review to one round per pair. Multiple rounds of back-and-forth between the same pair produce diminishing returns. The dialectic mode exists for iterative deepening.
- The Supervisor should read cross-reviews looking for *changed positions*. When an agent revises a recommendation after seeing counter-evidence, that is the highest-value signal in the swarm.

---

## Devil's Advocate Template

### When Used

**Phase 3 (Cross-Review)** in all modes. The Devil's Advocate is a mandatory adversarial agent (present in every swarm regardless of size). After Phase 2, the Supervisor distills the majority positions from all agent reports and sends them to the Devil's Advocate, whose job is to construct the strongest possible counter-argument for each.

### Template

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

### Variables

| Variable | Description | Source |
|----------|-------------|--------|
| `{{POSITIONS}}` | A numbered list of the majority positions extracted from Phase 1/2 agent reports. Each position is a concise statement of what most agents agreed on. | Written by the Supervisor during Phase 2 triage. The Supervisor distills the consensus findings into clear, arguable propositions. |

### Tips

- The Supervisor should write `POSITIONS` as clear, specific claims -- not vague summaries. "EEG-based authentication achieves 95%+ accuracy in lab settings" is arguable. "EEG authentication looks promising" is not.
- The self-rating (STRONG/MODERATE/WEAK) is critical. It prevents the Devil's Advocate from treating every counter-argument as equally valid. A WEAK self-rating means the agent is saying "I tried, but the majority is probably right on this one."
- The final instruction ("Do not manufacture disagreement") is load-bearing. Without it, adversarial agents tend to produce contrarian noise. Real dissent is valuable; manufactured dissent wastes tokens.
- The Devil's Advocate sees less context than analysis agents (no artifact, minimal background). This is intentional: it reduces anchoring bias and forces counter-arguments to stand on their own logic.
- If the Devil's Advocate rates all counter-arguments as WEAK, that is a strong signal that the consensus is robust. Note this in the synthesis.

---

## Dialectic Agent Template

### When Used

**Phases 1-3 in dialectic mode only** (`--rigor dialectic`). In dialectic mode, the standard multi-agent architecture is replaced by a two-voice Socratic dialogue between Thesis and Antithesis agents. This template is used for every round of the dialogue (3-5 rounds, decided by the Supervisor). The `{{PREVIOUS_RESPONSE}}` variable is empty for Round 1's opening statement.

### Template

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
## Your Response (engage their specific point — no retreating to generalities)
## The Contradiction You See (in their position OR your own — be honest)
## What's Getting Clearer (what the dialogue is revealing that wasn't visible at the start)
## Confidence in Your Position (1-10, and what would move it)
```

### Variables

| Variable | Description | Source |
|----------|-------------|--------|
| `{{POSITION_NAME}}` | A label for this agent's role in the dialogue (e.g., "Thesis: Open-Source Advocate" or "Antithesis: Proprietary Control Defender"). | Assigned by the Supervisor when framing the dialectic in Phase 0. |
| `{{TOPIC}}` | The user's original question or research topic. | Passed directly from the `/quorum` invocation. |
| `{{THESIS_OR_ANTITHESIS}}` | A clear statement of this agent's starting position (e.g., "Open-sourcing the core product will accelerate adoption and build an ecosystem moat that outweighs revenue risk"). | Written by the Supervisor. Must be the strongest intellectually honest version of this side, not a strawman. |
| `{{WHY_THIS_POSITION_IS_INTELLECTUALLY_HONEST}}` | The philosophical or empirical grounding for the position (e.g., "Network effects in developer tools consistently favor open ecosystems -- Linux, Kubernetes, VS Code all followed this pattern"). | Written by the Supervisor. This prevents agents from arguing positions they cannot genuinely defend. |
| `{{PREVIOUS_RESPONSE}}` | The other agent's most recent response in the dialogue. Empty or marked "This is the opening round" for Round 1. | Taken from the previous round's output by the Supervisor. Each round, the Supervisor passes one agent's response to the other. |

### Tips

- The Supervisor's most important job in dialectic mode is framing the **core tension** correctly. A well-framed tension produces a dialogue that naturally deepens. A poorly framed one produces agents talking past each other.
- Both positions must be intellectually honest. If the Supervisor cannot write a genuine `WHY_THIS_POSITION_IS_INTELLECTUALLY_HONEST` for one side, the topic may not be suited for dialectic mode.
- Watch the "Confidence in Your Position" scores across rounds. If both agents' confidence drops, the dialogue is surfacing genuine complexity. If one drops to 2-3 while the other stays at 8+, a clear winner is emerging.
- The "What's Getting Clearer" section is where the real value lives. It captures emergent insights that neither agent started with.
- The Supervisor should stop the dialogue when one of three outcomes occurs: synthesis (both agents converge), bedrock (irreducible value disagreement), or spark (a new question or insight emerges that reframes the problem).
- For Round 1, set `{{PREVIOUS_RESPONSE}}` to something like "This is the opening round. State your position with your strongest argument and the evidence behind it." This gives the first agent a clear starting instruction.

---

## Validation Gate Prompt

### When Used

**Phase 5 (Independent Validation)** in all modes unless `--no-cross-ai` is set. After the Supervisor writes the internal synthesis in Phase 4, the synthesis is sent to an independent reviewer (via web search fact-checking or a separate agent) who had no involvement in producing it. This template frames that independent review.

### Template

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

### Variables

| Variable | Description | Source |
|----------|-------------|--------|
| `{{N}}` | Total number of agents in the swarm. | Calculated by the Supervisor from the swarm configuration (default 5, or set via `--size`). |
| `{{R_COUNT}}` | Number of research agents in the swarm. | Calculated by the Supervisor based on mode (0 in REVIEW mode, ~30% in RESEARCH mode, ~20% in HYBRID mode). |
| `{{A_COUNT}}` | Number of analysis agents in the swarm. | Calculated by the Supervisor based on mode and total swarm size after subtracting research and adversarial agents. |
| `{{TOPIC}}` | The user's original question or research topic. | Passed directly from the `/quorum` invocation. |

### Tips

- The synthesis text itself (the document being reviewed) is appended after this prompt but is not a template variable. The Supervisor pastes the Phase 4 synthesis below the template when spawning the validation agent.
- The "no stake in these conclusions" framing is intentional. It gives the reviewer permission to disagree with everything. Without it, reviewers tend to defer to the swarm's consensus.
- "Be adversarial" is the key instruction. A validation gate that rubber-stamps the synthesis adds no value. The best validation gates produce 2-3 concrete challenges that force the swarm to sharpen its conclusions in Phase 6.
- Item 5 ("One thing you'd add") is designed to catch blind spots. The swarm may have excellent coverage of what it looked at but completely missed an adjacent consideration.
- When using web search fact-checking (Method 1) instead of a separate agent, the Supervisor should focus on verifying the top 3 consensus claims, checking any specific statistics or dates, and searching for counter-evidence to the strongest conclusions.
- The validation gate should always run for high-stakes questions. Only skip it (`--no-cross-ai`) for quick brainstorming or low-stakes queries where speed matters more than rigor.
