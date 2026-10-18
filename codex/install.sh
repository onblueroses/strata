#!/usr/bin/env bash
# Link the Codex operating layer into $CODEX_HOME. Every managed path is a symlink
# into this repo, so git is the only source of truth: no copies, no manifest, no
# hashes, no rollback. Repairing drift is one rerun; auditing it is `--check`.
#
#   codex/install.sh            create or repair every link
#   codex/install.sh --check    report missing or wrong links, exit 1 if any
#
# A regular file sitting at a managed path is someone's work, never ours: it is
# reported and left exactly as found.
set -uo pipefail

REPO=$(cd "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
CODEX_HOME=${CODEX_HOME:-${HOME:?HOME must be set}/.codex}
CHECK=0
case "${1:-}" in
    --check) CHECK=1 ;;
    "") ;;
    *) echo "usage: install.sh [--check]" >&2; exit 64 ;;
esac

status=0
changed=0

link() {
    local path=$1 target=$2 current=""
    if [ ! -e "$target" ]; then
        printf 'MISSING SOURCE  %s (wanted by %s)\n' "$target" "$path" >&2
        status=1
        return
    fi
    if [ -L "$path" ]; then
        current=$(readlink "$path")
        [ "$current" = "$target" ] && return 0
    elif [ -e "$path" ]; then
        printf 'BLOCKED         %s is a regular file, not a link to %s; left as found\n' \
            "$path" "$target" >&2
        status=1
        return
    fi
    if [ "$CHECK" = 1 ]; then
        printf 'WRONG           %s -> %s (want %s)\n' "$path" "${current:-nothing}" "$target" >&2
        status=1
        return
    fi
    if ! mkdir -p "${path%/*}" || ! ln -sfn "$target" "$path"; then
        printf 'FAILED          %s -> %s\n' "$path" "$target" >&2
        status=1
        return
    fi
    printf 'linked          %s -> %s\n' "$path" "$target"
    changed=$((changed + 1))
}

# One constitution for every runtime.
link "$CODEX_HOME/AGENTS.md" "$REPO/CLAUDE.md"

# Hooks: the file itself is a link, so a hook edit in the repo is live at once.
link "$CODEX_HOME/hooks.json" "$REPO/codex/hooks.json"
link "$CODEX_HOME/hooks" "$REPO/codex/hooks"

# The native role matrix.
for source in "$REPO"/codex/agents/*.toml; do
    link "$CODEX_HOME/agents/${source##*/}" "$source"
done

# Codex-native lifecycle skills, then the shared skills Codex also runs.
# Anything else already in $CODEX_HOME/skills stays untouched.
for source in "$REPO"/codex/skills/*/; do
    source=${source%/}
    link "$CODEX_HOME/skills/${source##*/}" "$source"
done
for name in cold-email outreach-atlas research-viz triage; do
    link "$CODEX_HOME/skills/$name" "$REPO/skills/$name"
done

if [ "$CHECK" = 1 ]; then
    [ "$status" = 0 ] && echo "every managed link under $CODEX_HOME is correct"
else
    echo "$changed link(s) written under $CODEX_HOME"
fi
exit "$status"
