#!/bin/bash
# Quorum Ralph Loop — Autonomous iteration with adversarial review
# Usage: ./ralph.sh [--max N] [--prd PATH] [--review-every N]
#
# Combines:
#   Superpowers discipline → iron-clad task decomposition
#   Quorum review          → multi-persona validation between iterations
#   Ralph persistence      → keep going until machine-verified complete
#
# The loop:
#   1. Agent reads PRD + progress.md + AGENTS.md
#   2. Picks next incomplete task
#   3. Implements with TDD discipline
#   4. Quorum reviews every N tasks (default: 3)
#   5. Learnings accumulate in AGENTS.md
#   6. Loop restarts with fresh context
#   7. Exits only when ALL acceptance criteria pass

set -euo pipefail

# --- Config ---
MAX_ITERATIONS=${MAX_ITERATIONS:-30}
REVIEW_EVERY=${REVIEW_EVERY:-3}
PRD_PATH=""
QUORUM_RIGOR="high"
SLEEP_BETWEEN=3

# --- Parse args ---
while [[ $# -gt 0 ]]; do
  case $1 in
    --max) MAX_ITERATIONS="$2"; shift 2 ;;
    --prd) PRD_PATH="$2"; shift 2 ;;
    --review-every) REVIEW_EVERY="$2"; shift 2 ;;
    --rigor) QUORUM_RIGOR="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# --- Validate ---
if [[ -z "$PRD_PATH" ]]; then
  echo "Usage: ./ralph.sh --prd <path-to-prd.md>"
  echo ""
  echo "Generate a PRD first:"
  echo '  /quorum "your task description" --superpower'
  exit 1
fi

if [[ ! -f "$PRD_PATH" ]]; then
  echo "PRD not found: $PRD_PATH"
  exit 1
fi

# --- Init ---
PROGRESS_FILE="progress.md"
RALPH_DIR=".ralph"
LOG_DIR="$RALPH_DIR/logs"
mkdir -p "$LOG_DIR"

if [[ ! -f "$PROGRESS_FILE" ]]; then
  cat > "$PROGRESS_FILE" << 'INIT'
# Ralph Progress Log

## Codebase Patterns
<!-- Append reusable patterns here — NOT task-specific details -->

---

INIT
  echo "[ralph] Initialized $PROGRESS_FILE"
fi

COMPLETED_TASKS=0
TOTAL_ITERATIONS=0

# --- Prompt ---
PROMPT=$(cat << 'PROMPT_END'
You are an autonomous implementation agent running inside a Ralph loop.
Each iteration gives you a fresh context. Your memory is the filesystem.

## Your Protocol

1. **Read the PRD** — understand all tasks and acceptance criteria
2. **Read progress.md** — know what's already done
3. **Read AGENTS.md / CLAUDE.md** — absorb accumulated learnings
4. **Pick ONE incomplete task** — the highest priority unfinished item
5. **Implement with TDD discipline:**
   - Write a failing test FIRST
   - Run it — confirm it fails for the RIGHT reason
   - Write MINIMAL code to pass
   - Run it — confirm it passes
   - Refactor if needed
   - Commit with descriptive message
6. **Update progress.md** — append what you did, learnings, gotchas
7. **Update AGENTS.md** — ONLY genuinely reusable patterns (not task-specific)
8. **Mark the task complete in the PRD** (change `- [ ]` to `- [x]`)

## Iron Laws

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION
NEVER SKIP THE RED STEP (watching the test fail)
```

If you wrote code before the test: DELETE IT. Start over with the test.
If a test passes immediately: you're testing existing behavior. Fix the test.
If 3+ fix attempts fail: STOP. Question the architecture. Note it in progress.md.

## Completion Signal

When ALL tasks in the PRD are marked `[x]` AND all tests pass:

<promise>COMPLETE</promise>

Do NOT output this signal unless EVERY acceptance criterion is verified.
If any task remains incomplete, just implement the next one and exit normally.

## What NOT to do

- Don't implement multiple tasks per iteration (one task, one commit)
- Don't skip tests for "simple" changes
- Don't modify the PRD structure (only check boxes)
- Don't add features not in the PRD
- Don't guess — if unclear, note the question in progress.md for the next iteration
PROMPT_END
)

# --- Main Loop ---
echo ""
echo "=========================================="
echo "  Quorum Ralph Loop"
echo "  PRD: $PRD_PATH"
echo "  Max iterations: $MAX_ITERATIONS"
echo "  Quorum review every: $REVIEW_EVERY tasks"
echo "=========================================="
echo ""

for i in $(seq 1 "$MAX_ITERATIONS"); do
  echo "[ralph] === Iteration $i / $MAX_ITERATIONS ==="

  LOG_FILE="$LOG_DIR/iteration-$(printf '%03d' "$i").log"

  # Run Claude with the prompt + PRD
  OUTPUT=$(claude --print \
    "$PROMPT

---

## PRD (Product Requirements Document)

$(cat "$PRD_PATH")

---

## Progress Log

$(cat "$PROGRESS_FILE")

---

## Learnings (AGENTS.md)

$(cat AGENTS.md 2>/dev/null || echo 'No learnings yet.')
" 2>&1 | tee "$LOG_FILE" | tee /dev/stderr) || true

  TOTAL_ITERATIONS=$((TOTAL_ITERATIONS + 1))

  # Check for completion
  if echo "$OUTPUT" | grep -q "<promise>COMPLETE</promise>"; then
    echo ""
    echo "=========================================="
    echo "  ALL TASKS COMPLETE"
    echo "  Iterations: $TOTAL_ITERATIONS"
    echo "=========================================="

    # Final Quorum review
    echo "[ralph] Running final Quorum review..."
    claude --print \
      "/quorum \"Final validation: verify all PRD acceptance criteria are met and code quality is production-ready\" --artifact $PRD_PATH --mode review --rigor $QUORUM_RIGOR --no-web" \
      2>&1 | tee "$LOG_DIR/final-review.log"

    echo ""
    echo "[ralph] Done. Review: $LOG_DIR/final-review.log"
    exit 0
  fi

  # Count completed tasks for review cadence
  COMPLETED_TASKS=$(grep -c '\- \[x\]' "$PRD_PATH" 2>/dev/null || echo 0)

  # Quorum review at intervals
  if [[ $((COMPLETED_TASKS % REVIEW_EVERY)) -eq 0 && $COMPLETED_TASKS -gt 0 ]]; then
    echo "[ralph] === Quorum Review (after $COMPLETED_TASKS tasks) ==="

    REVIEW_OUTPUT=$(claude --print \
      "/quorum \"Review implementation quality: check completed tasks against PRD acceptance criteria, flag any regressions, vibecoding, or skipped tests\" --artifact $PRD_PATH --mode review --rigor $QUORUM_RIGOR --no-web --no-save" \
      2>&1 | tee "$LOG_DIR/review-$(printf '%03d' "$i").log") || true

    # Append review findings to progress
    echo "" >> "$PROGRESS_FILE"
    echo "## Quorum Review (iteration $i, $COMPLETED_TASKS tasks done)" >> "$PROGRESS_FILE"
    echo "Review logged to $LOG_DIR/review-$(printf '%03d' "$i").log" >> "$PROGRESS_FILE"
    echo "---" >> "$PROGRESS_FILE"
  fi

  sleep "$SLEEP_BETWEEN"
done

echo ""
echo "=========================================="
echo "  MAX ITERATIONS REACHED ($MAX_ITERATIONS)"
echo "  Completed tasks: $COMPLETED_TASKS"
echo "  Check progress.md for status"
echo "=========================================="
exit 1
