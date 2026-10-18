#!/usr/bin/env bash
set -euo pipefail

# dmux-dispatch-protocol test harness
# Run: dmux-protocol-test.sh --project <repo-path> [--agent claude|codex|gemini] [--timeout 120]

usage() {
  cat <<'EOF'
dmux-dispatch-protocol test harness

Usage: dmux-protocol-test.sh --project DIR [OPTIONS]

Options:
  --agent AGENT    Agent to test (default: claude)
  --timeout SECS   Max wait for agent completion (default: 120)
  --skip-agent     Skip real agent launch (test infrastructure only)
  -h, --help       Show this help

Tests: script mechanics, worktree lifecycle, scratchpad symlinks,
gitignore, trust auto-approval, agent completion, result validation,
merge cleanliness, cleanup
EOF
  exit 0
}

PROJECT="" AGENT="claude" TIMEOUT=120 SKIP_AGENT=false
# Cleanup scope trackers (a ticket): panes are killed by set-difference against
# this snapshot, and the slug branch is deleted only when this run created it.
PANES_BEFORE="" DISPATCHED=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2 ;;
    --agent) AGENT="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --skip-agent) SKIP_AGENT=true; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown: $1" >&2; exit 1 ;;
  esac
done

[[ -z "$PROJECT" ]] && { echo "Error: --project required" >&2; exit 1; }
[[ ! -d "$PROJECT/.git" ]] && { echo "Error: $PROJECT is not a git repo" >&2; exit 1; }

PROJECT=$(realpath "$PROJECT")
PROJECT_NAME=$(basename "$PROJECT")
SLUG="harness-test"
MAIN_BRANCH=$(git -C "$PROJECT" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||' || git -C "$PROJECT" branch --show-current)
START_COMMIT=$(git -C "$PROJECT" rev-parse HEAD)

PASS=0 FAIL=0 SKIP=0
result() {
  local status=$1 name=$2 detail=${3:-}
  case "$status" in
    PASS) PASS=$((PASS+1)); printf "  \033[32m[PASS]\033[0m %s\n" "$name" ;;
    FAIL) FAIL=$((FAIL+1)); printf "  \033[31m[FAIL]\033[0m %s: %s\n" "$name" "$detail" ;;
    SKIP) SKIP=$((SKIP+1)); printf "  \033[33m[SKIP]\033[0m %s: %s\n" "$name" "$detail" ;;
  esac
}

echo "================================================"
echo "dmux dispatch protocol test harness"
echo "================================================"
echo "Project: $PROJECT ($PROJECT_NAME)"
echo "Agent: $AGENT"
echo "Main branch: $MAIN_BRANCH"
echo "Start commit: $START_COMMIT"
echo "Timeout: ${TIMEOUT}s"
echo ""

# ---- PHASE 1: Prerequisites ----
echo "Phase 1: Prerequisites"
which dmux-dispatch.sh >/dev/null 2>&1 && result PASS "dispatch script on PATH" || result FAIL "dispatch script on PATH" "not found"
which "$AGENT" >/dev/null 2>&1 && result PASS "$AGENT CLI installed" || result FAIL "$AGENT CLI installed" "not found"
SESSION=$(tmux list-sessions -F '#{session_name}' 2>/dev/null | grep "^dmux.*${PROJECT_NAME}" | head -1 || true)
[[ -z "$SESSION" ]] && SESSION=$(tmux list-sessions -F '#{session_name}' 2>/dev/null | grep -m1 '^dmux' || true)
[[ -n "$SESSION" ]] && result PASS "dmux session found ($SESSION)" || result FAIL "dmux session" "no dmux tmux session"

# ---- PHASE 2: Script validation ----
echo ""
echo "Phase 2: Script validation"
# Use capture-then-check pattern to avoid pipefail issues
OUT=$(dmux-dispatch.sh --help 2>&1 || true); echo "$OUT" | grep -q "Usage" && result PASS "help flag" || result FAIL "help flag"
OUT=$(dmux-dispatch.sh 2>&1 || true); echo "$OUT" | grep -q "required" && result PASS "missing args error" || result FAIL "missing args error"
OUT=$(dmux-dispatch.sh --project "$PROJECT" --slug "bad slug" --agent claude --brief /dev/null --dry-run 2>&1 || true); echo "$OUT" | grep -q "lowercase" && result PASS "slug validation (spaces)" || result FAIL "slug validation"
OUT=$(dmux-dispatch.sh --project "$PROJECT" --slug 'test-$(id)' --agent claude --brief /dev/null --dry-run 2>&1 || true); echo "$OUT" | grep -q "lowercase" && result PASS "slug validation (injection)" || result FAIL "slug injection NOT blocked"
OUT=$(dmux-dispatch.sh --project /tmp --slug test --agent claude --brief /dev/null --dry-run 2>&1 || true); echo "$OUT" | grep -q "not a git" && result PASS "git repo validation" || result FAIL "git repo validation"

# ---- PHASE 3: Worktree + scratchpad + gitignore ----
echo ""
echo "Phase 3: Infrastructure"

# Create brief
BRIEF_DIR="$PROJECT/.dmux/tasks"
mkdir -p "$BRIEF_DIR"
cat > "$BRIEF_DIR/$SLUG.md" << EOF
---
id: harness-$SLUG
parent_session: harness
dispatched: $(date -u +%Y-%m-%dT%H:%M:%SZ)
agent: $AGENT
permission_mode: acceptEdits
entity: $PROJECT_NAME
branch_from: $MAIN_BRANCH
scratchpad: true
siblings: []
---

## Objective
Harness test. Create harness-output.txt with "harness-pass". Write to scratchpad. Commit. Run /end.

## Constraints
- Only create harness-output.txt
- Do not modify existing files except .gitignore
- Write "harness note" to .dmux/scratchpad/$SLUG.md

## Acceptance Criteria
- [ ] harness-output.txt exists
- [ ] .dmux/scratchpad/$SLUG.md exists
- [ ] Changes committed
EOF
[[ -f "$BRIEF_DIR/$SLUG.md" ]] && result PASS "brief created" || result FAIL "brief creation"

# Dispatch (dry-run first)
DRY_OUTPUT=$(dmux-dispatch.sh --project "$PROJECT" --slug "$SLUG" --agent "$AGENT" --brief "$BRIEF_DIR/$SLUG.md" --branch-from "$MAIN_BRANCH" --dry-run 2>&1)
echo "$DRY_OUTPUT" | grep -q "=== Dispatched" && result PASS "dry-run dispatch" || result FAIL "dry-run dispatch"
echo "$DRY_OUTPUT" | grep -q "ln -sfn" && result PASS "scratchpad symlink in dry-run" || result FAIL "scratchpad symlink missing"
echo "$DRY_OUTPUT" | grep -q "task-brief.md" && result PASS "gitignore entries in dry-run" || result FAIL "gitignore missing"

if $SKIP_AGENT; then
  # Infrastructure-only: create worktree manually, verify symlink + gitignore.
  # A pre-existing slug branch is deleted only when already contained in the
  # main branch; unmerged commits abort instead of being discarded (a ticket).
  if git -C "$PROJECT" show-ref --verify --quiet "refs/heads/$SLUG"; then
    if git -C "$PROJECT" merge-base --is-ancestor "refs/heads/$SLUG" "$MAIN_BRANCH"; then
      git -C "$PROJECT" branch -D "$SLUG" 2>/dev/null || true
    else
      echo "Error: branch '$SLUG' exists with commits not in '$MAIN_BRANCH'; delete it manually first" >&2
      exit 1
    fi
  fi
  mkdir -p "$PROJECT/.dmux/worktrees" "$PROJECT/.dmux/scratchpad"
  git -C "$PROJECT" worktree add "$PROJECT/.dmux/worktrees/$SLUG" -b "$SLUG" "$MAIN_BRANCH" 2>/dev/null
  DISPATCHED=true
  cp "$BRIEF_DIR/$SLUG.md" "$PROJECT/.dmux/worktrees/$SLUG/.task-brief.md"
  mkdir -p "$PROJECT/.dmux/worktrees/$SLUG/.dmux"
  ln -sfn "$PROJECT/.dmux/scratchpad" "$PROJECT/.dmux/worktrees/$SLUG/.dmux/scratchpad"
  printf '%s\n' '.task-brief.md' '.task-result.md' '.task-blocked.md' '.dmux/' >> "$PROJECT/.dmux/worktrees/$SLUG/.gitignore"

  # Verify
  [[ -L "$PROJECT/.dmux/worktrees/$SLUG/.dmux/scratchpad" ]] && result PASS "scratchpad symlink" || result FAIL "scratchpad symlink"
  echo "test note" > "$PROJECT/.dmux/worktrees/$SLUG/.dmux/scratchpad/$SLUG.md"
  [[ -f "$PROJECT/.dmux/scratchpad/$SLUG.md" ]] && result PASS "scratchpad write-through" || result FAIL "scratchpad write-through"
  grep -q '.task-brief.md' "$PROJECT/.dmux/worktrees/$SLUG/.gitignore" && result PASS "gitignore has protocol entries" || result FAIL "gitignore"
  GIT_STATUS=$(git -C "$PROJECT/.dmux/worktrees/$SLUG" status --short | grep -v '.gitignore' | grep -c 'task-brief\|\.dmux' || true)
  [[ "$GIT_STATUS" -eq 0 ]] && result PASS "protocol files hidden from git" || result FAIL "protocol files visible" "$GIT_STATUS files"

  result SKIP "real agent launch" "--skip-agent"
  result SKIP "trust auto-approval" "--skip-agent"
  result SKIP "agent completion" "--skip-agent"
  result SKIP "task result" "--skip-agent"
else
  # ---- PHASE 4: Real agent dispatch ----
  echo ""
  echo "Phase 4: Real agent dispatch"
  PANES_BEFORE=$(tmux list-panes -t "$SESSION" -F '#{pane_id}' 2>/dev/null || true)
  DISPATCH_OUTPUT=$(dmux-dispatch.sh --project "$PROJECT" --slug "$SLUG" --agent "$AGENT" --brief "$BRIEF_DIR/$SLUG.md" --branch-from "$MAIN_BRANCH" --permission-mode "acceptEdits" 2>&1)
  if echo "$DISPATCH_OUTPUT" | grep -q "=== Dispatched"; then
    result PASS "real dispatch"
    DISPATCHED=true
  else
    result FAIL "real dispatch"
  fi
  
  [[ -L "$PROJECT/.dmux/worktrees/$SLUG/.dmux/scratchpad" ]] && result PASS "scratchpad symlink" || result FAIL "scratchpad symlink"
  grep -q '.task-brief.md' "$PROJECT/.dmux/worktrees/$SLUG/.gitignore" 2>/dev/null && result PASS "gitignore entries" || result FAIL "gitignore"

  # ---- PHASE 5: Monitor and wait ----
  echo ""
  echo "Phase 5: Agent monitoring (timeout: ${TIMEOUT}s)"
  ELAPSED=0
  TRUST_CLEARED=false
  AGENT_RUNNING=false
  RESULT_WRITTEN=false
  
  while [[ $ELAPSED -lt $TIMEOUT ]]; do
    sleep 5
    ELAPSED=$((ELAPSED + 5))
    
    # Check for .task-result.md
    if [[ -f "$PROJECT/.dmux/worktrees/$SLUG/.task-result.md" ]]; then
      RESULT_WRITTEN=true
      echo "  [${ELAPSED}s] .task-result.md detected!"
      break
    fi
    
    # Check pane content for progress
    NEWEST_PANE=$(tmux list-panes -t "$SESSION" -F '#{pane_id}' | tail -1)
    CONTENT=$(tmux capture-pane -t "$NEWEST_PANE" -p 2>/dev/null || true)
    
    if ! $TRUST_CLEARED && ! echo "$CONTENT" | grep -qi "trust"; then
      TRUST_CLEARED=true
    fi
    
    if echo "$CONTENT" | grep -q "Claude Code\|Opus\|Sonnet\|accept edits"; then
      AGENT_RUNNING=true
    fi
    
    printf "  [${ELAPSED}s] trust=%s agent=%s result=%s\n" "$TRUST_CLEARED" "$AGENT_RUNNING" "$RESULT_WRITTEN"
  done
  
  $RESULT_WRITTEN && result PASS "agent completed within timeout" || result FAIL "agent timeout" "${ELAPSED}s elapsed"
fi

# ---- PHASE 6: Result validation ----
echo ""
echo "Phase 6: Result validation"

if [[ -f "$PROJECT/.dmux/worktrees/$SLUG/.task-result.md" ]]; then
  # Frontmatter is flat key: value lines; a sed scan needs no PyYAML (which is
  # user-site installed here and vanishes under a harness HOME override).
  RESULT_STATUS=$(sed -n '2,/^---$/{s/^status:[[:space:]]*//p}' "$PROJECT/.dmux/worktrees/$SLUG/.task-result.md" | head -1)
  [[ -z "$RESULT_STATUS" ]] && RESULT_STATUS="parse-error"
  [[ "$RESULT_STATUS" == "complete" ]] && result PASS "result status: complete" || result FAIL "result status" "$RESULT_STATUS"
  
  grep -q "## Summary" "$PROJECT/.dmux/worktrees/$SLUG/.task-result.md" && result PASS "result has Summary section" || result FAIL "missing Summary"
  grep -q "## Surprises" "$PROJECT/.dmux/worktrees/$SLUG/.task-result.md" && result PASS "result has Surprises section" || result FAIL "missing Surprises"
elif ! $SKIP_AGENT; then
  result FAIL "no .task-result.md"
fi

# Check work product
if [[ -f "$PROJECT/.dmux/worktrees/$SLUG/harness-output.txt" ]]; then
  result PASS "work product created"
elif $SKIP_AGENT; then
  result SKIP "work product" "--skip-agent"
else
  result FAIL "work product missing"
fi

# Check scratchpad
if [[ -f "$PROJECT/.dmux/scratchpad/$SLUG.md" ]]; then
  result PASS "scratchpad note in SHARED location"
else
  result FAIL "scratchpad note missing from shared location"
fi

# Check commits
COMMIT_COUNT=$(git -C "$PROJECT" log --oneline "$MAIN_BRANCH..$SLUG" 2>/dev/null | wc -l)
if [[ "$COMMIT_COUNT" -gt 0 ]]; then
  result PASS "branch has commits ($COMMIT_COUNT)"
  # Check no protocol files in commits
  PROTO_IN_DIFF=$(git -C "$PROJECT" diff --name-only "$MAIN_BRANCH..$SLUG" 2>/dev/null | grep -c 'task-brief\|task-result\|task-blocked\|\.dmux/' || true)
  [[ "$PROTO_IN_DIFF" -eq 0 ]] && result PASS "no protocol files in commits" || result FAIL "protocol files in commits" "$PROTO_IN_DIFF files"
elif $SKIP_AGENT; then
  result SKIP "commits" "--skip-agent"
else
  result FAIL "no commits on branch"
fi

# ---- PHASE 7: Merge test ----
echo ""
echo "Phase 7: Merge cleanliness"
if [[ "$COMMIT_COUNT" -gt 0 ]]; then
  # Merge in a scratch clone: the user's checkout (possibly dirty) is never
  # mutated, so no reset --hard is needed afterwards (a ticket).
  MERGE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/dmux-harness-merge.XXXXXX")
  if git clone -q --no-hardlinks "$PROJECT" "$MERGE_DIR/clone" 2>/dev/null \
    && git -C "$MERGE_DIR/clone" checkout -q "$MAIN_BRANCH" 2>/dev/null \
    && git -C "$MERGE_DIR/clone" merge "origin/$SLUG" --no-edit >/dev/null 2>&1; then
    result PASS "merge succeeded"
  else
    result FAIL "merge failed"
  fi
  [[ ! -f "$MERGE_DIR/clone/.task-brief.md" ]] && result PASS "no .task-brief.md on main" || result FAIL ".task-brief.md leaked"
  [[ ! -f "$MERGE_DIR/clone/.task-result.md" ]] && result PASS "no .task-result.md on main" || result FAIL ".task-result.md leaked"
  rm -rf -- "$MERGE_DIR"
else
  result SKIP "merge test" "no commits"
fi

# ---- PHASE 8: Cleanup ----
echo ""
echo "Phase 8: Cleanup"
# Kill only the panes this run created (set difference against the
# pre-dispatch snapshot); unrelated agent panes stay alive (a ticket).
if ! $SKIP_AGENT && [[ -n "$SESSION" ]]; then
  PANES_AFTER=$(tmux list-panes -t "$SESSION" -F '#{pane_id}' 2>/dev/null || true)
  for pid in $(comm -13 <(printf '%s\n' "$PANES_BEFORE" | sort) <(printf '%s\n' "$PANES_AFTER" | sort)); do
    tmux kill-pane -t "$pid" 2>/dev/null || true
  done
fi
git -C "$PROJECT" worktree remove --force "$PROJECT/.dmux/worktrees/$SLUG" 2>/dev/null || true
if $DISPATCHED; then
  git -C "$PROJECT" branch -D "$SLUG" 2>/dev/null || true
fi
# Remove exactly what this run created; pre-existing dmux state stays (a ticket).
rm -f -- "$BRIEF_DIR/$SLUG.md" "$PROJECT/.dmux/scratchpad/$SLUG.md"
rm -rf -- "$PROJECT/.dmux/worktrees/$SLUG"
rmdir "$PROJECT/.dmux/tasks" "$PROJECT/.dmux/scratchpad" "$PROJECT/.dmux/worktrees" "$PROJECT/.dmux" 2>/dev/null || true
result PASS "cleanup complete"

# ---- SUMMARY ----
echo ""
echo "================================================"
TOTAL=$((PASS + FAIL + SKIP))
printf "Results: \033[32m%d passed\033[0m, \033[31m%d failed\033[0m, \033[33m%d skipped\033[0m (of %d)\n" $PASS $FAIL $SKIP $TOTAL
echo "================================================"

[[ $FAIL -eq 0 ]] && exit 0 || exit 1
