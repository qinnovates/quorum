## Hackathon Mode (Auto-Detected)

When you say "build", "implement", "create", "scaffold", "write a", "set up", or "add feature", the supervisor auto-triggers the hackathon pipeline. No flag needed.

```bash
/quorum "Build a REST API for user auth with JWT" --max
```

**What happens:**

1. Supervisor detects implementation intent ("Build") → triggers hackathon pipeline
2. **Decomposition agent** generates a PRD with TDD enforcement:
   - Exact file paths for every file created or modified
   - Bite-sized tasks (one action each, 2-5 minutes)
   - Each task: write failing test → verify fail → implement → verify pass → commit
   - Machine-verifiable acceptance criteria (not "works correctly" but "returns 200 with valid JWT containing user_id claim")
3. **Challenge-driven convergence** stress-tests the PRD (only with `--max`):
   - Architect: "Are the boundaries right? Missing abstractions?"
   - Breaker: "Which acceptance criteria are ambiguous? Edge cases?"
   - TDD Enforcer: "Is every task actually testable? Assertions specific enough?"
   - Pragmatist: "Is this over-engineered? Can tasks be eliminated?"
   - Judge: Computes convergence score. Declares READY or sends back for revision.
4. **Output:** `_swarm/prd-{name}.md` — battle-tested PRD ready for implementation

**Executing the PRD.** Quorum stops at the PRD. It does not run an autonomous build loop of its own. To execute the tasks, open the PRD in Claude Code and choose a permission mode yourself:

- **Default mode:** Claude proposes each edit and command and waits for your approval. Safest; slowest.
- **Auto mode:** Claude works through the PRD's tasks (test → fail → implement → pass → commit) without asking before each action. Switch with Shift+Tab, or start with `claude --permission-mode auto`.

> **Consent warning.** Auto mode means you are approving every edit and command in advance, not one at a time. Before you turn it on: read the PRD (`--ratify` exists for exactly this); work on a fresh branch or worktree with nothing uncommitted that you care about; keep the task list scoped to what you reviewed; and stay close enough to stop it (Esc). Quorum will never switch modes for you. The choice to run unattended is yours to make, every time.

Earlier versions shipped a shell script (the "Ralph loop") that called `claude --print` in a loop with no approval step. It was removed in v7.3.1: Claude Code's permission modes do the same job, with the consent decision made explicitly by the user instead of by a script.

**With vs without `--max`:**

| | `/quorum "Build X"` | `/quorum "Build X" --max` |
|--|---------------------|--------------------------|
| PRD generation | 5 agents (lighter) | 7-15 agents (full decomposition) |
| Stress-test | No challenge review | Full convergence (Architect + Breaker + TDD Enforcer + Pragmatist + Judge) |
| Output quality | Good for small features | Battle-tested for production systems |

**Trigger keywords:** `build`, `implement`, `create`, `add feature`, `scaffold`, `write a`, `set up` — anything that signals "I want code output, not analysis."

No `--hackathon` flag exists. Same capability, zero cognitive load.
