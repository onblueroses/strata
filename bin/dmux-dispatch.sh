#!/usr/bin/env bash
set -euo pipefail

# dmux-dispatch.sh - Create a dmux worktree + tmux pane and launch an agent
# Part of the dmux dispatch protocol. See $STRATA_HOME/reference/dmux-dispatch-protocol.md

usage() {
  cat <<'EOF'
Usage: dmux-dispatch.sh --project DIR --slug NAME --agent AGENT --brief FILE [OPTIONS]

Required:
  --project DIR          Git repository root
  --slug NAME            Worktree/branch name (filesystem-safe)
  --agent AGENT          Agent CLI to launch (claude, codex, gemini, etc.)
  --brief FILE           Path to .task-brief.md file

Options:
  --branch-from BRANCH   Base branch (default: main)
  --permission-mode MODE Permission mode for the agent (default: acceptEdits)
  --session NAME         tmux session name (default: auto-detect dmux session)
  --dry-run              Print commands without executing
  -h, --help             Show this help
EOF
  exit 0
}

# Defaults
BRANCH_FROM="main"
PERMISSION_MODE="acceptEdits"
SESSION=""
DRY_RUN=false
PROJECT="" SLUG="" AGENT="" BRIEF=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)        PROJECT="$2"; shift 2 ;;
    --slug)           SLUG="$2"; shift 2 ;;
    --agent)          AGENT="$2"; shift 2 ;;
    --brief)          BRIEF="$2"; shift 2 ;;
    --branch-from)    BRANCH_FROM="$2"; shift 2 ;;
    --permission-mode) PERMISSION_MODE="$2"; shift 2 ;;
    --session)        SESSION="$2"; shift 2 ;;
    --dry-run)        DRY_RUN=true; shift ;;
    -h|--help)        usage ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# Validate required args
for var in PROJECT SLUG AGENT BRIEF; do
  if [[ -z "${!var}" ]]; then
    echo "Error: --${var,,} is required" >&2
    usage
  fi
done

# Validate slug: only lowercase alphanumeric + hyphens (strict, prevents shell injection)
if [[ ! "$SLUG" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo "Error: Slug must be lowercase alphanumeric with hyphens only (got: '$SLUG')" >&2
  exit 1
fi

if [[ ! -d "$PROJECT/.git" ]] && [[ ! -f "$PROJECT/.git" ]]; then
  echo "Error: $PROJECT is not a git repository" >&2
  exit 1
fi

if [[ ! -f "$BRIEF" ]]; then
  echo "Error: Brief file not found: $BRIEF" >&2
  exit 1
fi

# Auto-detect dmux tmux session if not specified
if [[ -z "$SESSION" ]]; then
  PROJECT_NAME=$(basename "$PROJECT")
  # Try to match a dmux session containing the project name first
  SESSION=$(tmux list-sessions -F '#{session_name}' 2>/dev/null | grep "^dmux.*${PROJECT_NAME}" | head -1 || true)
  # Fallback: any dmux session
  if [[ -z "$SESSION" ]]; then
    SESSION=$(tmux list-sessions -F '#{session_name}' 2>/dev/null | grep -m1 '^dmux' || true)
  fi
  if [[ -z "$SESSION" ]]; then
    echo "Error: No dmux tmux session found. Start dmux first." >&2
    exit 1
  fi
  echo "Using tmux session: $SESSION"
fi

WORKTREE_PATH="$PROJECT/.dmux/worktrees/$SLUG"

# Bootstrap prompt: agent-specific because only Claude has /end skill
BOOTSTRAP_COMMON="You are a dispatched field agent in a dmux worktree. Read .task-brief.md for your mission. Execute the task respecting all constraints. Check .dmux/scratchpad/ if the brief has scratchpad: true. If you discover something siblings should know, write to .dmux/scratchpad/${SLUG}.md."
BOOTSTRAP_CLAUDE="${BOOTSTRAP_COMMON} When done: commit your work, run /end. If blocked, write .task-blocked.md and go idle."
BOOTSTRAP_OTHER="${BOOTSTRAP_COMMON} When done: commit your work, then write .task-result.md with YAML frontmatter (id, status: complete/partial/failed, files_changed, merge_order_hint: no-dependency) and sections: Summary, Decisions, Surprises, Integration Notes. If blocked, write .task-blocked.md (id, status: blocked, blocker) with sections: What's Blocking, Done So Far, What I Need. Then go idle."

# Build agent launch command
case "$AGENT" in
  claude)
    PERM_FLAGS=""
    [[ "$PERMISSION_MODE" == "acceptEdits" ]] && PERM_FLAGS=" --permission-mode acceptEdits"
    [[ "$PERMISSION_MODE" == "bypassPermissions" ]] && PERM_FLAGS=" --dangerously-skip-permissions"
    [[ "$PERMISSION_MODE" == "plan" ]] && PERM_FLAGS=" --permission-mode plan"
    AGENT_CMD="claude \"$BOOTSTRAP_CLAUDE\"$PERM_FLAGS"
    ;;
  codex)
    PERM_FLAGS=""
    [[ "$PERMISSION_MODE" == "acceptEdits" ]] && PERM_FLAGS=" --full-auto"
    [[ "$PERMISSION_MODE" == "bypassPermissions" ]] && PERM_FLAGS=" --dangerously-bypass-approvals-and-sandbox"
    AGENT_CMD="codex \"$BOOTSTRAP_OTHER\"$PERM_FLAGS"
    ;;
  gemini)
    PERM_FLAGS=""
    [[ "$PERMISSION_MODE" == "acceptEdits" ]] && PERM_FLAGS=" --approval-mode auto_edit"
    [[ "$PERMISSION_MODE" == "bypassPermissions" ]] && PERM_FLAGS=" --approval-mode yolo"
    AGENT_CMD="gemini --prompt-interactive \"$BOOTSTRAP_OTHER\"$PERM_FLAGS"
    ;;
  *)
    AGENT_CMD="$AGENT \"$BOOTSTRAP_OTHER\""
    ;;
esac

run_or_print() {
  if $DRY_RUN; then
    echo "[dry-run] $*"
  else
    eval "$@"
  fi
}

echo "=== dmux-dispatch: $SLUG ($AGENT) ==="

# 1. Prune stale worktrees
run_or_print "cd \"$PROJECT\" && git worktree prune 2>/dev/null || true"

# 2. Create worktree
if [[ -d "$WORKTREE_PATH" ]]; then
  echo "Worktree already exists at $WORKTREE_PATH"
else
  # Clean up stale branch from previous dispatch if it exists
  if ! $DRY_RUN; then
    cd "$PROJECT" && git branch -D "$SLUG" 2>/dev/null || true
  else
    echo "[dry-run] cd \"$PROJECT\" && git branch -D \"$SLUG\" 2>/dev/null || true"
  fi
  run_or_print "mkdir -p \"$(dirname "$WORKTREE_PATH")\""
  run_or_print "cd \"$PROJECT\" && git worktree add \"$WORKTREE_PATH\" -b \"$SLUG\" \"$BRANCH_FROM\""
fi

# 3. Copy brief into worktree
run_or_print "cp \"$BRIEF\" \"$WORKTREE_PATH/.task-brief.md\""

# 4. Ensure scratchpad directory exists and is shared across worktrees
run_or_print "mkdir -p \"$PROJECT/.dmux/scratchpad\""
# Symlink worktree's .dmux/scratchpad to the shared one so siblings can read each other's notes
if [[ ! -L "$WORKTREE_PATH/.dmux/scratchpad" ]]; then
  run_or_print "mkdir -p \"$WORKTREE_PATH/.dmux\""
  run_or_print "ln -sfn \"$PROJECT/.dmux/scratchpad\" \"$WORKTREE_PATH/.dmux/scratchpad\""
fi

# 4b. Add protocol files to worktree .gitignore (prevent committing briefs/results to branches)
if ! grep -q '.task-brief.md' "$WORKTREE_PATH/.gitignore" 2>/dev/null; then
  run_or_print "printf '%s\n' '.task-brief.md' '.task-result.md' '.task-blocked.md' '.dmux/' >> \"$WORKTREE_PATH/.gitignore\""
fi

# 5. Create tmux pane and launch agent
if $DRY_RUN; then
  echo "[dry-run] tmux split-window -t $SESSION -h -c \"$WORKTREE_PATH\" \"$AGENT_CMD\""
else
  tmux split-window -t "$SESSION" -h -c "$WORKTREE_PATH" "$AGENT_CMD"
  NEWEST_PANE=$(tmux list-panes -t "$SESSION" -F '#{pane_id}' | tail -1)
  # Keep pane alive after agent exits (for inspection, especially non-interactive agents like codex --full-auto)
  tmux set-option -p -t "$NEWEST_PANE" remain-on-exit on 2>/dev/null || true
  # Auto-approve trust dialogs for ALL agents (Claude, Codex, Gemini each have different prompts)
  # Poll pane content for up to 15 seconds, send Enter when trust prompt detected
  (
    sleep 2
    for i in $(seq 1 60); do
      CONTENT=$(tmux capture-pane -t "$NEWEST_PANE" -p 2>/dev/null || true)
      # Match trust prompts from any agent:
      #   Claude: "trust this folder", "Yes, I trust"
      #   Codex:  "trust the contents of this directory", "Yes, continue"
      #   Gemini: "trust this workspace", "trust the files"
      if echo "$CONTENT" | grep -qi "trust.*folder\|trust.*workspace\|trust.*directory\|trust.*contents\|Yes, I trust\|Yes, continue"; then
        sleep 0.5
        tmux send-keys -t "$NEWEST_PANE" Enter 2>/dev/null || true
        break
      fi
      # If agent is already past trust dialog and running
      if echo "$CONTENT" | grep -qE "^>|Claude Code|codex|Gemini" 2>/dev/null; then
        break
      fi
      sleep 0.25
    done
  ) &
fi

echo "=== Dispatched: $SLUG -> $WORKTREE_PATH ==="
