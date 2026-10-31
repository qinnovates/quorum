## Reviewers Mode (--reviewers)

Top-down sequential review pipeline. Unlike default Quorum (horizontal debate), `--reviewers` runs phases in cascade — each phase's output feeds the next. Personas are dynamically assembled based on the prompt topic, not hardcoded.

```bash
# Review a plan through domain-appropriate phases
/quorum "Review this API design for production readiness" --reviewers --artifact api-spec.md

# Review an app design top-down
/quorum "Is this iOS app architecture ready to ship?" --reviewers --artifact ARCHITECTURE.md

# Review a security posture
/quorum "Evaluate our auth implementation" --reviewers --artifact auth-flow.md
```

### How --reviewers Works

**Phase 0: Intake & Assembly**

The supervisor reads the prompt and assembles 3-5 review phases with topic-appropriate personas. No fixed roster — the reviewer panel is built per prompt.

| Prompt Domain | Example Phases |
|---------------|---------------|
| App/product | Strategist → UX Researcher → Architect → QA → Security |
| Security | Threat Modeler → Architect → Penetration Tester → Compliance |
| Research/paper | Methodology Reviewer → Domain Expert → Statistician → Ethics |
| Infrastructure | SRE → Architect → Security → Cost Analyst |
| Business/pitch | Market Analyst → Product Strategist → Financial Modeler → Legal |

The supervisor states the assembled phases and personas before proceeding. If `--artifact` is provided, the artifact is loaded as shared context for all phases.

**Phase 1-N: Sequential Review (each phase)**

Each phase runs one reviewer agent who:
1. Receives: the original prompt + artifact + ALL prior phase outputs
2. Produces: a structured review with findings, scored by severity
3. Classifies each finding as:
   - **Mechanical** — objective, auto-decidable (missing null check, wrong status code, typo)
   - **Taste** — subjective, requires human judgment (naming convention, abstraction level, scope boundary)

**Decision Principles (auto-applied to mechanical findings):**

| Principle | Rule |
|-----------|------|
| Completeness | Ship the whole thing. Partial fixes create more work than they save. |
| Blast radius | If effort < 1 day and it's in the blast radius, fix it now. |
| Pragmatic | When two approaches are equivalent, pick the cleaner one. |
| DRY | Reject duplicated functionality. Reuse what exists. |
| Explicit over clever | Prefer the obvious fix over the abstraction. |
| Bias toward action | Merge over endless review cycles. |

Mechanical findings are auto-resolved using these principles. The decision and rationale are logged but not surfaced for approval.

**Final Gate: Taste Decisions Only**

After all phases complete, the supervisor presents:

```
REVIEWERS COMPLETE — 4 phases, 23 findings

Auto-resolved (mechanical): 18
  - Phase 1 (Strategist): 3 findings, all resolved
  - Phase 2 (Architect): 8 findings, 7 resolved
  - Phase 3 (Security): 5 findings, all resolved
  - Phase 4 (QA): 4 findings, 3 resolved

Taste decisions (need your call): 5
  1. [Architect] Use repository pattern vs direct DB access
     → Recommendation: repository (Principle: DRY) — but close call, direct is simpler for this scope
  2. [Security] Rate limit at 100/min vs 1000/min
     → Recommendation: 100/min (Principle: Pragmatic) — tighter is safer, can loosen later
  3. ...

Cross-phase themes:
  - Phases 2+3 both flagged: auth token lifetime too long (15min → 5min suggested)
  - Phase 4 found: 2 untested edge cases from Phase 2's architecture

Options: [Approve all] [Override specific] [Send back to phase N] [Reject]
```

### --reviewers vs Default vs --max

| | Default (horizontal) | --max (challenger) | --reviewers (vertical) |
|--|---------------------|--------------------|-----------------------|
| Topology | Flat panel | Iterative convergence | Sequential cascade |
| Agent relationship | Peers debate | Challengers vs defenders | Each builds on previous |
| Decision style | Emerges from debate | Survives sustained attack | Auto-decided, taste surfaced |
| Best for | Ambiguous questions | Stress-testing decisions | Reviewing concrete artifacts |
| Output | Synthesized verdict | Converged/tension/exhausted | Approved with overrides |

### Examples

```bash
# Product review — assembles: Strategist → Designer → Engineer → QA
/quorum "Is this MVP spec ready to build?" --reviewers --artifact MVP-SPEC.md

# Security review — assembles: Threat Modeler → Code Auditor → Compliance → Incident Responder
/quorum "Review our payment flow for PCI compliance" --reviewers --artifact payment-flow.md

# Paper review — assembles: Methodology → Domain Expert → Writing Quality → Ethics
/quorum "Is this paper ready for submission?" --reviewers --artifact paper-draft.md --no-web

# Architecture review — assembles: System Designer → Performance → Security → Maintainability
/quorum "Review this microservices migration plan" --reviewers --artifact migration-plan.md
```
