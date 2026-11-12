#!/usr/bin/env bash
# bash codex/tests/test_install.sh -- covers the link installer.
# HOME is always a throwaway directory: this test must never see the live ~/.codex.
set -uo pipefail

REPO=$(cd "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
SCRATCH_ROOT="${TMPDIR:-/tmp}"
# A failed mktemp used to leave ROOT empty, which made HOME point at a system directory and pointed the whole test
# at the live ~/.codex and at `/out`. Abort instead, and prove the root is where it belongs.
ROOT=$(mktemp -d "$SCRATCH_ROOT/codex-install-test.XXXXXX") || ROOT=""
case "${ROOT:-}" in
    "$SCRATCH_ROOT"/codex-install-test.*) ;;
    *) printf 'BROKEN mktemp -d under %s gave %s\n' "$SCRATCH_ROOT" "${ROOT:-<empty>}" >&2
       exit 3 ;;
esac
export HOME="$ROOT/home"
mkdir -p "$HOME"
fails=0
ok()  { printf 'ok    %s\n' "$1"; }
no()  { printf 'FAIL  %s\n' "$1"; fails=$((fails + 1)); }
is()  { [ "$2" = "$3" ] && ok "$1" || no "$1: got '$2', want '$3'"; }
run() { bash "$REPO/codex/install.sh" "$@" >"$ROOT/out" 2>"$ROOT/err"; echo $?; }

is "check on an empty HOME refuses" "$(run --check)" 1
grep -q 'AGENTS.md' "$ROOT/err" && ok "check names the missing link" || no "check named nothing"

is "install succeeds"        "$(run)" 0
is "AGENTS.md links the constitution" "$(readlink "$HOME/.codex/AGENTS.md")" "$REPO/CLAUDE.md"
is "hooks.json links the repo"        "$(readlink "$HOME/.codex/hooks.json")" "$REPO/codex/hooks.json"
is "hook scripts link the repo"       "$(readlink "$HOME/.codex/hooks")" "$REPO/codex/hooks"
is "seven roles linked"      "$(find "$HOME/.codex/agents" -type l | wc -l)" 7
# Expected count comes from install.sh itself: the codex/skills directories plus the shared
# names it lists (a fixed number went stale twice as skills were added).
shared="$(sed -n 's/^for name in \(.*\); do$/\1/p' "$REPO/codex/install.sh" | wc -w)"
native="$(find "$REPO/codex/skills" -mindepth 1 -maxdepth 1 -type d | wc -l)"
is "every managed skill linked" "$(find "$HOME/.codex/skills" -maxdepth 1 -type l | wc -l)" "$((shared + native))"
is "every link resolves"     "$(find "$HOME/.codex" -xtype l | wc -l)" 0
for retired in ask-better directional-prompting humanizer skill-creator verify-work; do
    [ ! -e "$HOME/.codex/skills/$retired" ] && [ ! -L "$HOME/.codex/skills/$retired" ] \
        && ok "shelved $retired stays absent" || no "shelved $retired was reinstalled"
done

is "check passes after install" "$(run --check)" 0
is "a second install is a no-op" "$(run)" 0
grep -q '^0 link' "$ROOT/out" && ok "second install writes nothing" || no "second install rewrote links"

ln -sfn /dev/null "$HOME/.codex/agents/docs-researcher.toml"
is "check refuses a wrong target" "$(run --check)" 1
is "install repairs it"           "$(run)" 0
is "repair restores the target"   "$(readlink "$HOME/.codex/agents/docs-researcher.toml")" \
   "$REPO/codex/agents/docs-researcher.toml"

# A real file at a managed path is someone's work: report it, never replace it.
mv "$HOME/.codex/skills/triage" "$ROOT/parked-link"
printf 'hand written\n' > "$HOME/.codex/skills/triage"
is "install refuses over a regular file" "$(run)" 1
is "the regular file survives"           "$(cat "$HOME/.codex/skills/triage")" "hand written"
grep -q 'BLOCKED' "$ROOT/err" && ok "the block is reported" || no "the block was silent"
mv "$ROOT/parked-link" "$HOME/.codex/skills/triage"

# Unmanaged entries are none of the installer's business.
mkdir -p "$HOME/.codex/skills/night-check"
run >/dev/null
[ -d "$HOME/.codex/skills/night-check" ] && ok "unmanaged skills stay" || no "unmanaged skill removed"

printf '\n%s failure(s); scratch under %s\n' "$fails" "$ROOT"
[ "$fails" = 0 ]
