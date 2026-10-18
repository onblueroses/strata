#!/usr/bin/env bash
# bash codex/tests/test_install.sh -- covers the link installer and the privacy hook.
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
is "six skills linked"       "$(find "$HOME/.codex/skills" -maxdepth 1 -type l | wc -l)" 6
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

# --- the privacy hook, against stub gates only: the real gates are not under test here ---
# CODEX_PRIVACY_GATE names a DIRECTORY holding both gate filenames, so a case can watch which
# of the two a payload reaches; each stub records its own name in $GATE_LOG.
GH=gate-gh-public-actions.sh
PP=gate-pre-push.sh
stub() {  # stub <dir>/<gate filename> <exit status> [reason on stderr]
    mkdir -p "${1%/*}"
    { printf '#!/usr/bin/env bash\ncat >/dev/null\n'
      printf 'printf "%%s\\n" "${0##*/}" >> "${GATE_LOG:-/dev/null}"\n'
      [ -n "${3:-}" ] && printf 'printf "%%s\\n" "%s" >&2\n' "$3"
      printf 'exit %s\n' "$2"
    } > "$1"
    chmod 755 "$1"
}
stub "$ROOT/allow/$GH" 0;                 stub "$ROOT/allow/$PP" 0
stub "$ROOT/deny/$GH" 2 'no: reason';     stub "$ROOT/deny/$PP" 0
stub "$ROOT/denypush/$GH" 0;              stub "$ROOT/denypush/$PP" 2 'no: push reason'
stub "$ROOT/broken/$GH" 7;                stub "$ROOT/broken/$PP" 0
stub "$ROOT/halfgh/$GH" 0                 # the pre-push gate is simply not there
stub "$ROOT/slow/$PP" 0
printf '#!/usr/bin/env bash\nsleep 30\n' > "$ROOT/slow/$GH"
chmod 755 "$ROOT/slow/$GH"

hook() {  # hook <stub directory> <payload> -> exit status; $ROOT/gatelog lists the gates run
    : > "$ROOT/gatelog"
    CODEX_PRIVACY_GATE="$1" GATE_LOG="$ROOT/gatelog" \
        python3 "$REPO/codex/hooks/pre_tool_use.py" >"$ROOT/hout" 2>"$ROOT/herr" <<< "$2"
    echo $?
}
ran() { awk 'END {print NR}' "$ROOT/gatelog"; }
payload="{\"tool_input\":{\"command\":\"echo hi\"},\"cwd\":\"$HOME\"}"
pushload="{\"tool_input\":{\"command\":\"git push origin main\"},\"cwd\":\"$HOME\"}"

is "two permitting gates permit"      "$(hook "$ROOT/allow" "$payload")" 0
is "both gates ran"                   "$(ran)" 2
is "a refusing gh gate refuses"       "$(hook "$ROOT/deny" "$payload")" 2
is "the gate's own reason relays"     "$(cat "$ROOT/herr")" "no: reason"
is "the first refusal wins"           "$(ran)" 1
# The defect this pair pins: a git push used to reach only the gh gate, whose git-free
# prefilter allows at once, so no outgoing history was ever scanned for a Codex push.
is "a git push reaches the pre-push gate" "$(hook "$ROOT/denypush" "$pushload")" 2
is "the pre-push gate is the one that ran" "$(tail -1 "$ROOT/gatelog")" "$PP"
is "its reason relays too"            "$(cat "$ROOT/herr")" "no: push reason"
is "a gate with no verdict refuses"   "$(hook "$ROOT/broken" "$payload")" 2
is "a hanging gate refuses"           "$(hook "$ROOT/slow" "$payload")" 2
is "a missing gate refuses"           "$(hook "$ROOT/absent" "$payload")" 2
is "a missing second gate refuses"    "$(hook "$ROOT/halfgh" "$payload")" 2
is "a payload with no cwd refuses"    "$(hook "$ROOT/allow" '{"tool_input":{"command":"x"}}')" 2
# A corrupted event carries no verdict, so it cannot be an authorization.
is "a payload with no command refuses" "$(hook "$ROOT/allow" '{"tool_input":{}}')" 2
is "a non-JSON payload refuses"        "$(hook "$ROOT/allow" 'not json')" 2
is "truncated JSON refuses"            "$(hook "$ROOT/allow" '{"tool_input":{"command":')" 2

printf '\n%s failure(s); scratch under %s\n' "$fails" "$ROOT"
[ "$fails" = 0 ]
