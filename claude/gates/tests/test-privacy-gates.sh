#!/usr/bin/env bash
# test-privacy-gates.sh - the two privacy gates and the scanner they share.
#
# Every case is named for the reason it must fail, and the suite ends with a negative control:
# one matcher is removed from the fixture inventory and the case that depends on it must then
# PASS. Green without that control is not evidence -- the refusal could be coming from a typo
# in the fixture rather than from the matcher under test.
#
# The inventory here is a fixture with generic values. The real one is never copied in: a test
# that carries live tokens publishes them to every reader of the repo.
#
# Usage: test-privacy-gates.sh [--verbose]   exit 0 all green, 1 any case failed.
set -uo pipefail

# Every git command below belongs to a scratch repository. Run from a hook, this suite inherits
# GIT_DIR, GIT_INDEX_FILE and their kin, and then each of those commands lands in the live
# repository instead (the 2026-10-01 fixture incident). Clear them here too, whatever the caller did.
# shellcheck disable=SC2046
unset $(git rev-parse --local-env-vars)

ROOT="${GATE_TEST_ROOT:-$(cd "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)}"
VERBOSE=0
[ "${1:-}" = --verbose ] && VERBOSE=1
SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/privacy-gates-XXXXXX")" || exit 3
printf 'scratch: %s\n' "$SCRATCH"

PASS=0; FAIL=0; FAILED=()
ok() { PASS=$((PASS + 1)); [ "$VERBOSE" -eq 1 ] && printf '  PASS %s\n' "$1"; return 0; }
bad() { FAIL=$((FAIL + 1)); FAILED+=("$1"); printf '  FAIL %s :: %s\n' "$1" "$2"; return 0; }

# --- a HOME with a fixture inventory and a stub gh ------------------------------------------
H="$SCRATCH/home"
MESH_ONE="10.9."; MESH_ONE+="4.4"
MESH_PIN="10.9."; MESH_PIN+="1.2"
MESH_OTHER="10.9."; MESH_OTHER+="1.3"
OUTSIDE_IP="10.200."; OUTSIDE_IP+="4.4"
MESH_SUFFIX=".mesh.example"
PHONE_PREFIX="+44"
AT="@"
mkdir -p "$H/.claude/config" "$H/.claude/hooks/lib" "$H/.claude/telemetry" "$SCRATCH/bin"
cp "$ROOT/hooks/run-gates.sh" "$H/.claude/hooks/" || exit 3
cp "$ROOT/hooks/lib/privacy-scan.py" "$H/.claude/hooks/lib/" || exit 3
printf '#!/usr/bin/env bash\nexit 0\n' > "$H/.claude/telemetry/telemetry-emit.sh"
TOKENS="$H/.claude/config/private-tokens.txt"
cat > "$TOKENS" <<'INVENTORY'
# fixture inventory: generic values only, never the live one
lit Acme Widgets
demo widgets.example
re \bZeta[0-9]{4}\b
# structural shapes, fixture values only: an overlay range, its DNS suffix, a phone shape
re (^|[^0-9.])10\.9\.[0-9]{1,3}\.[0-9]{1,3}([^0-9.]|$)
re [a-z0-9]([a-z0-9-]*[a-z0-9])?\.mesh\.example
re (^|[^0-9A-Za-z+])\+[1-9][0-9]{0,2}[ /.()-]?[0-9][ /.()0-9]{6,}[0-9]
INVENTORY
# Answers `private` for one target only, so "proven private" and "could not tell" are separate
# outcomes rather than the same one.
cat > "$SCRATCH/bin/gh" <<'STUB'
#!/usr/bin/env bash
for a in "$@"; do case "$a" in *privately-held*) printf 'PRIVATE\n'; exit 0 ;; esac; done
printf 'PUBLIC\n'
STUB
chmod +x "$SCRATCH/bin/gh"
# A second stub, where the CWD repo answers `private` and a NAMED target answers for itself.
# Without it no case can tell visibility taken from the target apart from visibility taken from
# wherever the command happened to run, which is the confusion that published four shapes.
mkdir -p "$SCRATCH/bin-privcwd"
cat > "$SCRATCH/bin-privcwd/gh" <<'STUB'
#!/usr/bin/env bash
for a in "$@"; do
    case "$a" in
        -*) ;;
        */*) case "$a" in *privately-held*) printf 'PRIVATE\n' ;; *) printf 'PUBLIC\n' ;; esac
             exit 0 ;;
    esac
done
printf 'PRIVATE\n'
STUB
chmod +x "$SCRATCH/bin-privcwd/gh"

# Built at run time: a secret-shaped LITERAL in this file would refuse the repo's own push.
SECRET="ghp_$(printf 'A%.0s' $(seq 36))"
AWSKEY="AKIA$(printf 'A%.0s' $(seq 16))"
feed() {  # feed <command> <cwd> -> the PreToolUse stdin JSON
    jq -nc --arg c "$1" --arg d "$2" \
        '{session_id:"privacy-gates-test",tool_name:"Bash",cwd:$d,tool_input:{command:$c}}'
}
gh_case() {  # gh_case <name> <expected rc> <command>
    local out rc
    out="$(feed "$3" "$SCRATCH" | HOME="$H" PRIVACY_SCANNER="$H/.claude/hooks/lib/privacy-scan.py" PATH="$SCRATCH/bin:$PATH" \
        bash "$ROOT/hooks/gate-gh-public-actions.sh" 2>&1)"; rc=$?
    [ "$rc" = "$2" ] && ok "$1" || bad "$1" "expected rc=$2, got rc=$rc :: ${out:0:140}"
}
ghp_case() {  # ghp_case <name> <expected rc> <command> -- with the CWD repo proven private
    local out rc
    out="$(feed "$3" "$SCRATCH" | HOME="$H" PRIVACY_SCANNER="$H/.claude/hooks/lib/privacy-scan.py" PATH="$SCRATCH/bin-privcwd:$PATH" \
        bash "$ROOT/hooks/gate-gh-public-actions.sh" 2>&1)"; rc=$?
    [ "$rc" = "$2" ] && ok "$1" || bad "$1" "expected rc=$2, got rc=$rc :: ${out:0:140}"
}
pp_case() {  # pp_case <name> <expected rc> <command> [cwd] [extra PATH dir]
    local out rc
    out="$(feed "$3" "${4:-$REPO}" | HOME="$H" PRIVACY_SCANNER="$H/.claude/hooks/lib/privacy-scan.py" PATH="${5:+$5:}$SCRATCH/bin:$PATH" \
        bash "$ROOT/hooks/gate-pre-push.sh" 2>&1)"; rc=$?
    [ "$rc" = "$2" ] && ok "$1" || bad "$1" "expected rc=$2, got rc=$rc :: ${out:0:140}"
}
scan() {  # scan <file> -> $SCAN_RC and $SCAN_OUT, straight from the shared scanner
    SCAN_OUT="$(PRIVACY_TOKENS_FILE="$TOKENS" /usr/bin/python3 \
        "$ROOT/hooks/lib/privacy-scan.py" --classes all < "$1" 2>&1)"; SCAN_RC=$?
}

# --- gh: one refuse and one clean case per token class ---------------------------------------
W='gh issue create --repo public/repo --title t --body'
gh_case lit-in-body-published-to-a-public-repo        2 "$W 'we use Acme Widgets'"
gh_case lit-absent-body-is-not-refused                0 "$W 'we use a generic vendor'"
gh_case prefix-long-repo-dirty-refuses 2 "gh --repo public/repo issue create --body 'Acme Widgets'"
gh_case prefix-long-repo-clean-passes 0 "gh --repo public/repo issue create --body generic"
gh_case prefix-equals-repo-dirty-refuses 2 "gh --repo=public/repo issue create --body 'Acme Widgets'"
gh_case prefix-short-repo-dirty-refuses 2 "gh -R public/repo issue create --body 'Acme Widgets'"
gh_case prefix-attached-repo-dirty-refuses 2 "gh -Rpublic/repo issue create --body 'Acme Widgets'"
gh_case prefix-attached-repo-clean-passes 0 "gh -Rpublic/repo issue create --body generic"
gh_case prefix-repo-read-passes 0 "gh --repo public/repo issue view 1 --json body"
gh_case prefix-repo-api-field-refuses 2 "gh -Rpublic/repo api repos/public/repo/issues -f title='Acme Widgets'"
gh_case write-after-literal-heredoc-still-refuses 2 "python3 - <<'PY'
print(\"quoted diagnostic: 'gh issue create'\")
PY
gh issue create --body 'Acme Widgets'"
gh_case write-before-literal-heredoc-still-refuses 2 "gh issue create --body 'Acme Widgets'; python3 - <<'PY'
print(\"quoted diagnostic: 'gh issue create'\")
PY"
gh_case unresolved-literal-heredoc-write-refuses 2 "gh issue create --body generic; python3 - <<'PY'
print(\"gh diagnostic\")"
gh_case demo-term-published-to-a-public-repo          2 "$W 'see widgets.example for the demo'"
gh_case demo-absent-body-is-not-refused               0 "$W 'see the demo host'"
gh_case regex-token-published-to-a-public-repo        2 "$W 'ticket Zeta4711 is open'"
gh_case regex-near-miss-is-not-refused                0 "$W 'ticket Zeta47 is open'"
gh_case secret-published-to-a-public-repo             2 "$W 'token $SECRET'"
gh_case secret-shaped-but-short-is-not-refused        0 "$W 'token ghp_short'"
gh_case aws-long-term-key-id-is-refused               2 "$W 'key $AWSKEY'"
gh_case presigned-url-temporary-key-id-passes         0 "$W 'https://s3.example/x.pdf?AWSAccessKeyId=ASIAAAAAAAAAAAAAAAAA&Expires=1&Signature=abc'"
gh_case address-in-the-overlay-range           2 "$W 'host at ${MESH_ONE} answers'"
gh_case address-outside-the-mesh-range                0 "$W 'host at ${OUTSIDE_IP} answers'"
gh_case overlay-dns-name-published                       2 "$W 'ssh box-one.tailnet-x${MESH_SUFFIX}'"
gh_case ordinary-hostname-is-not-refused              0 "$W 'ssh box-one.internal.example'"
gh_case international-phone-number-published                 2 "$W 'reach us on ${PHONE_PREFIX} 151 23456789'"
gh_case digit-run-that-is-not-a-phone-number          0 "$W 'build 4915123456789 shipped'"
# Provider shapes the retired scanner covered and the rewrite dropped. Built at run time for
# the reason SECRET is: as literals they would be findings in this file.
SLACKHOOK="https://hooks.slack.com/services/T$(printf 'A%.0s' $(seq 8))/B$(printf 'B%.0s' $(seq 8))/$(printf 'c%.0s' $(seq 24))"
DISCORDHOOK="https://discord.com/api/webhooks/$(printf '9%.0s' $(seq 18))/$(printf 'k%.0s' $(seq 40))"
SENTRYDSN="https://$(printf 'a%.0s' $(seq 32))@o0.ingest.sentry.io/1"
LIVEURL="https://user:s3cr3t$(printf 'v%.0s' $(seq 8))@example.com/"
gh_case slack-webhook-url-is-a-secret                 2 "$W 'posts to $SLACKHOOK'"
gh_case discord-webhook-url-is-a-secret               2 "$W 'posts to $DISCORDHOOK'"
gh_case sentry-dsn-is-a-secret                        2 "$W 'reports to $SENTRYDSN'"
gh_case userinfo-url-with-a-live-password             2 "$W 'connects as $LIVEURL'"
# The exclusion that retired this pattern once: a documentation URL is not a credential.
gh_case userinfo-url-with-a-placeholder-password      0 "$W 'connects as https://user:password${AT}docs.invalid/path'"

# --- gh: every content path that can carry a body --------------------------------------------
printf 'host at %s answers\n' "$MESH_ONE" > "$SCRATCH/dirty.md"
printf 'nothing private here\n' > "$SCRATCH/clean.md"
gh_case body-file-contents-are-scanned          2 "gh issue create --repo public/repo -t t --body-file $SCRATCH/dirty.md"
gh_case body-file-clean-contents-pass           0 "gh issue create --repo public/repo -t t --body-file $SCRATCH/clean.md"
cp "$SCRATCH/dirty.md" "$SCRATCH/body file.md"
cp "$SCRATCH/clean.md" "$SCRATCH/clean file.md"
gh_case quoted-space-file-dirty-refuses 2 "gh issue create --repo public/repo --body-file '$SCRATCH/body file.md'"
gh_case quoted-space-file-clean-passes 0 "gh issue create --repo public/repo --body-file '$SCRATCH/clean file.md'"
gh_case quoted-space-field-file-refuses 2 "gh api graphql -F 'query=@$SCRATCH/body file.md'"
gh_case raw-field-at-is-literal 0 "gh api graphql -f 'query=@$SCRATCH/dirty.md'"
gh_case raw-long-field-at-is-literal 0 "gh api graphql --raw-field 'query=@$SCRATCH/dirty.md'"
gh_case home-content-file-expansion-refuses 2 'gh issue create --body-file "$HOME/.claude/config/private-tokens.txt"'
gh_case dynamic-inline-body-refuses 2 'gh issue create --body "$PAYLOAD"'
gh_case dynamic-inline-substitution-refuses 2 'gh issue create --body "$(cat note.md)"'
gh_case literal-graphql-variables-pass 0 "gh api graphql -f query='query(\$id: ID!) { node(id: \$id) { id } }'"
gh_case escaped-dollar-literal-passes 0 'gh issue create --body "\$PAYLOAD"'
python3 - "$SCRATCH" <<'FILES'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
line = b'generic filler text with no match generic filler text with no match\n'
data = (line * (1048576 // len(line) + 1))[:1048576]
(p / 'limit-clean.txt').write_bytes(data)
(p / 'oversize-clean.txt').write_bytes(data + b'x')
(p / 'oversize-tail.txt').write_bytes(data + b'Acme Widgets')
FILES
gh_case exact-limit-clean-content-passes 0 "gh issue create --body-file $SCRATCH/limit-clean.txt"
gh_case oversize-clean-is-not-completely-scanned 2 "gh issue create --body-file $SCRATCH/oversize-clean.txt"
gh_case oversize-private-tail-never-cleared 2 "gh issue create --body-file $SCRATCH/oversize-tail.txt"
gh_case api-field-file-contents-are-scanned     2 "gh api graphql -F query=@$SCRATCH/dirty.md"
gh_case api-inline-field-is-scanned             2 "gh api repos/public/repo/issues -XPOST -f title='Acme Widgets'"
gh_case gist-positional-file-is-scanned         2 "gh gist create $SCRATCH/dirty.md"
gh_case prose-gist-does-not-make-positionals-files 0 "gh issue create --repo public/repo -t t --body 'see the gist about it' $SCRATCH/dirty.md"
gh_case release-notes-file-is-scanned           2 "gh release create v1 --notes-file $SCRATCH/dirty.md"
# Explicit references must be scanned completely; an unresolved reference is not clean.
gh_case unresolved-explicit-body-file-refuses   2 "gh issue create --repo public/repo -t t --body-file $SCRATCH/gone.md"
# `cd <dir> && gh ...`: PreToolUse fires before the command, so the reported cwd is still the
# session's and a relative reference resolved against it silently publishes unscanned.
mkdir -p "$SCRATCH/sub"; cp "$SCRATCH/dirty.md" "$SCRATCH/sub/nested.md"
gh_case relative-file-after-cd-is-resolved      2 "cd $SCRATCH/sub && gh api graphql -F query=@nested.md"
gh_case unresolved-relative-field-file-refuses 2 'gh api graphql -F query=@nested.md'
gh_case relative-file-resolves-against-the-cwd  2 'gh api graphql -F query=@dirty.md'
# `--body-file -` and `--input -` read STDIN, so the redirection IS the content.
gh_case body-file-from-a-redirection            2 "gh issue create --repo public/repo -t t --body-file - < $SCRATCH/dirty.md"
gh_case api-input-from-a-redirection            2 "gh api repos/public/repo/issues --input - < $SCRATCH/dirty.md"
gh_case redirection-with-no-space               2 "gh issue create --repo public/repo -t t --body-file - <$SCRATCH/dirty.md"
# `--input <file>` extraction: removing it left a dirty API payload green (review, 2026-09-01).
gh_case api-input-file-is-scanned               2 "gh api repos/public/repo/issues --input $SCRATCH/dirty.md"
# `gh release create|upload <tag> <assets...>`: the assets are published files, the tag is not.
gh_case release-create-asset-is-scanned         2 "gh release create v1 $SCRATCH/dirty.md"
gh_case release-upload-asset-is-scanned         2 "gh release upload v1 $SCRATCH/dirty.md"
gh_case release-asset-label-suffix-is-stripped  2 "gh release upload v1 $SCRATCH/dirty.md#label"
gh_case release-clean-asset-passes              0 "gh release create v1 $SCRATCH/clean.md"
# Every verb in VERBS that carries a body: dropping one from the list left it unscanned.
gh_case pr-comment-body-is-scanned              2 "gh pr comment 7 --repo public/repo --body 'we use Acme Widgets'"
gh_case pr-review-body-is-scanned               2 "gh pr review 7 --repo public/repo --body 'we use Acme Widgets'"
gh_case issue-edit-body-is-scanned              2 "gh issue edit 7 --repo public/repo --body 'we use Acme Widgets'"
# A reader that fails is not a file that held nothing: the status has to reach the verdict.
cp "$H/.claude/hooks/lib/privacy-scan.py" "$SCRATCH/scanner-real.py"
cat > "$H/.claude/hooks/lib/privacy-scan.py" <<'READER_CONTROL'
import builtins, os, runpy
original = builtins.open
def fail(path, *args, **kwargs):
    if str(path) == os.environ["PRIVACY_FAIL_FILE"]:
        raise OSError("injected content read failure")
    return original(path, *args, **kwargs)
builtins.open = fail
runpy.run_path(os.environ["PRIVACY_SCANNER_REAL"], run_name="__main__")
READER_CONTROL
NOHEAD_OUT="$(feed "gh issue create --repo public/repo -t t --body-file $SCRATCH/clean.md" "$SCRATCH" \
    | HOME="$H" PRIVACY_SCANNER="$H/.claude/hooks/lib/privacy-scan.py" PATH="$SCRATCH/bin:$PATH" PRIVACY_FAIL_FILE="$SCRATCH/clean.md" PRIVACY_SCANNER_REAL="$SCRATCH/scanner-real.py" \
      bash "$ROOT/hooks/gate-gh-public-actions.sh" 2>&1)"; NOHEAD_RC=$?
[ "$NOHEAD_RC" = 2 ] && ok content-read-failure-is-not-a-clean-scan \
    || bad content-read-failure-is-not-a-clean-scan "expected rc=2, got rc=$NOHEAD_RC :: ${NOHEAD_OUT:0:140}"
cp "$SCRATCH/scanner-real.py" "$H/.claude/hooks/lib/privacy-scan.py"
# The checker must consume the scanner's reported class, not infer it from its
# own requested plan or an exit-0 alone.
cat > "$H/.claude/hooks/lib/privacy-scan.py" <<'WRONG_EVIDENCE'
print("privacy-scan-v1:secrets")
WRONG_EVIDENCE
gh_case all-plan-rejects-secrets-only-clean-report 2 'gh issue create --repo public/repo --body generic'
cat > "$H/.claude/hooks/lib/privacy-scan.py" <<'WRONG_EVIDENCE'
print("privacy-scan-v1:all")
WRONG_EVIDENCE
gh_case secrets-plan-rejects-all-clean-report 2 'gh issue create --repo privately-held/repo --body generic'
cat > "$H/.claude/hooks/lib/privacy-scan.py" <<'WRONG_EVIDENCE'
print("clean")
WRONG_EVIDENCE
gh_case clean-with-no-scanner-evidence-refuses 2 'gh issue create --repo public/repo --body generic'
cp "$SCRATCH/scanner-real.py" "$H/.claude/hooks/lib/privacy-scan.py"

# --- gh: the write target, with the CWD repo proven private ----------------------------------
ghp_case api-endpoint-names-the-target          2 "gh api repos/public/repo/issues -f body='widgets.example'"
ghp_case api-endpoint-on-a-private-repo         0 "gh api repos/privately-held/repo/issues -f body='widgets.example'"
ghp_case api-without-a-repos-path-is-unproven   2 "gh api graphql -f query='widgets.example'"
ghp_case attached-R-names-the-target            2 "gh issue create -Rpublic/repo -t t --body 'widgets.example'"
ghp_case attached-R-on-a-private-repo           0 "gh issue create -Rprivately-held/repo -t t --body 'widgets.example'"
ghp_case repo-equals-form-names-the-target      2 "gh issue create --repo=public/repo -t t --body 'widgets.example'"
ghp_case a-gist-is-never-proven-private         2 "gh gist create -d 'widgets.example' $SCRATCH/clean.md"
ghp_case a-public-target-later-in-the-chain     2 "gh issue create -Rprivately-held/repo -t t --body 'widgets.example' && gh issue create -Rpublic/repo -t t --body x"
ghp_case no-target-falls-back-to-the-cwd-repo   0 "gh issue create -t t --body 'widgets.example'"

# --- gh: reads, help, overrides, and the private target --------------------------------------
gh_case read-does-not-reach-the-scanner         0 'gh issue list --repo public/repo'
gh_case api-get-does-not-reach-the-scanner      0 'gh api /user'
gh_case help-publishes-nothing                  0 'gh issue create --help'
# `--help` and the override are CONTROL tokens, not words: as substrings, either one in a body
# turned a public write into a permit (review, 2026-09-01).
gh_case help-inside-a-body-still-refuses        2 "$W 'widgets.example: run tool --help for usage'"
gh_case ack-inside-a-body-still-refuses         2 "$W 'widgets.example, while documenting PRIVACY_ACK=1'"
gh_case identifier-to-a-proven-private-repo     0 "gh issue create --repo privately-held/repo -t t --body 'we use Acme Widgets'"
gh_case secret-to-a-proven-private-repo         2 "gh issue create --repo privately-held/repo -t t --body 'token $SECRET'"
gh_case explicit-ack-overrides-the-refusal      0 "PRIVACY_ACK=1 $W 'we use Acme Widgets'"
# A command that only QUOTES a gh write is not one; the same text matched anywhere refused every
# diagnostic about this gate (measured 2026-09-01 while rewriting it).
gh_case quoted-gh-write-is-not-a-write          0 "echo \"$W 'we use Acme Widgets'\""

mv "$TOKENS" "$TOKENS.away"
gh_case missing-inventory-refuses-a-write       2 "$W 'we use a generic vendor'"
gh_case missing-inventory-lets-a-read-through   0 'gh issue list --repo public/repo'
mv "$TOKENS.away" "$TOKENS"

# --- pre-push: a real repo with a bare remote ------------------------------------------------
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=fixture.invalid
export GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=fixture.invalid
REPO="$SCRATCH/repo"
git init -q --bare "$SCRATCH/remote.git"
git init -q --bare "$SCRATCH/privately-held.git"
git init -q -b main "$REPO"
gitr() { git -C "$REPO" "$@"; }
# The gate classifies the CONFIGURED push URLs, so the fixture cannot use `pushurl` to reach
# the bare repos -- that is the field under test. `url.<bare>.pushInsteadOf` redirects the real
# push instead, leaving remote.<r>.url exactly as production shows it: a public forge, a
# proven-private forge repo, or a box of the operator's own.
gitr remote add origin https://github.com/public/repo.git
gitr config "url.$SCRATCH/remote.git.pushInsteadOf" https://github.com/public/repo.git
gitr remote add secure https://github.com/privately-held/repo.git
gitr config "url.$SCRATCH/privately-held.git.pushInsteadOf" https://github.com/privately-held/repo.git
git init -q --bare "$SCRATCH/box.git"
gitr remote add box "$SCRATCH/box.git"
printf 'hello\n' > "$REPO/a.txt"; gitr add a.txt; gitr commit -qm initial
gitr push -q origin main; gitr push -q secure main; gitr push -q box main
gitr branch -q --set-upstream-to=origin/main main

pp_case non-push-command-is-untouched     0 'git status'
# A command the tokenizer cannot read is refused only when it could push.
pp_case untokenizable-non-push-passes     0 "git status; echo 'unclosed"
pp_case untokenizable-push-still-refuses  2 "git push; echo 'unclosed"
pp_case clean-history-passes              0 'git push'
printf 'we use Acme Widgets\n' >> "$REPO/a.txt"; gitr commit -qam "add a line"
pp_case identifier-in-the-outgoing-diff   2 'git push'
pp_case identifier-via-git-C-form         2 "git -C $REPO push" "$SCRATCH"
pp_case identifier-via-cd-and-push-form   2 "cd $REPO && git push" "$SCRATCH"
pp_case identifier-behind-a-redirect      2 'git push 2>&1 | tail -3'
# The tokenizer splits `2>&1` into the word `2` and the operator `>&`, so the fd number was read
# as the remote (a private remote got the public scan, 2026-09-30) or, after a named remote, as a
# refspec that resolves to nothing, which scanned NOTHING and let the push through.
pp_case fd-number-is-not-a-refspec         2 'git push origin 2>&1 | tail -3'
pp_case fd-number-is-not-a-refspec-nospace 2 'git push origin main 2>/dev/null'
pp_case redirect-target-is-not-a-refspec   2 'git push origin > /dev/null'
# Same rule on this side, and the case that caught it: a diagnostic quoting a push, next to a
# `git -C <other>` read, scanned the wrong repo and refused a command that pushed nothing.
pp_case quoted-push-is-not-a-push         0 "grep -n 'git push' $REPO/a.txt"
pp_case quoted-push-beside-a-git-read     0 "git -C $REPO log -1 --format=%s && echo 'git push'"
pp_case explicit-ack-overrides-the-push   0 'PRIVACY_ACK=1 git push'
pp_case identifier-to-a-private-remote    0 'git push secure main'
gitr remote add selfhost https://forge.example/org/project.git
gitr remote add lookalike https://github.com.evil.example/org/project.git
gitr remote add pathspoof https://forge.example/github.com/private/project.git
gitr remote add unpinned ssh://git${AT}unlisted.tailnet${MESH_SUFFIX}/owner/repo.git
gitr remote add local-relative ../box.git
mkdir -p "$SCRATCH/bin-all-private"
printf '#!/bin/sh\nprintf "PRIVATE\\n"\n' > "$SCRATCH/bin-all-private/gh"
chmod +x "$SCRATCH/bin-all-private/gh"
# Even an affirmative gh stub cannot make an unrecognized URL a known forge.
pp_case unknown-self-hosted-forge-is-unproven 2 'git push selfhost main' "$REPO" "$SCRATCH/bin-all-private"
pp_case forge-lookalike-host-is-unproven 2 'git push lookalike main' "$REPO" "$SCRATCH/bin-all-private"
pp_case forge-name-in-url-path-is-unproven 2 'git push pathspoof main' "$REPO" "$SCRATCH/bin-all-private"
pp_case unpinned-overlay-host-is-unproven 2 'git push unpinned main'
pp_case local-relative-path-remains-private 0 'git push local-relative main'
mkdir -p "$H/.config/privacy" "$SCRATCH/bin-ssh"
printf 'known-vps\t%s\n' "$MESH_PIN" > "$H/.config/privacy/private-push-destinations.txt"
printf '# fixture overlay: one range, one suffix\n10.9.0.0/16\n%s\n' "$MESH_SUFFIX" > "$H/.config/privacy/private-push-networks.txt"
cat > "$SCRATCH/bin-ssh/ssh" <<'SSH_CONFIG'
#!/bin/sh
printf 'hostname 10.9.%s\nproxycommand none\nproxyjump none\n' '1.2'
SSH_CONFIG
chmod +x "$SCRATCH/bin-ssh/ssh"
gitr remote add pinned ssh://git@known-vps/owner/repo.git
pp_case pinned-overlay-alias-remains-private 0 'git push pinned main' "$REPO" "$SCRATCH/bin-ssh"
# An scp-style destination with no user (`alias:path`) named outright: it was read as an unknown
# remote name, so a pinned box got the public scan (2026-09-30). Remote names cannot hold `:`.
pp_case pinned-scp-url-without-user-is-private 0 'git push known-vps:owner/repo.git main' "$REPO" "$SCRATCH/bin-ssh"
pp_case unpinned-scp-url-without-user-is-unproven 2 'git push other-box:owner/repo.git main' "$REPO" "$SCRATCH/bin-ssh"
pp_case overridden-ssh-transport-is-unproven 2 'GIT_SSH_COMMAND=/bin/false git push pinned main' "$REPO" "$SCRATCH/bin-ssh"
printf 'known-vps\t%s\n' "$MESH_OTHER" > "$H/.config/privacy/private-push-destinations.txt"
pp_case changed-alias-mapping-is-unproven 2 'git push pinned main' "$REPO" "$SCRATCH/bin-ssh"
printf 'known-vps\t%s\n' "$MESH_PIN" > "$H/.config/privacy/private-push-destinations.txt"
cat > "$SCRATCH/bin-ssh/ssh" <<'SSH_CONFIG'
#!/bin/sh
printf 'hostname 100.%s\nproxycommand ssh -W %%h:%%p relay\nproxyjump none\n' '87.1.2'
SSH_CONFIG
pp_case proxy-transport-is-unproven 2 'git push pinned main' "$REPO" "$SCRATCH/bin-ssh"
cat > "$H/.claude/hooks/lib/privacy-scan.py" <<'WRONG_EVIDENCE'
print("privacy-scan-v1:secrets")
WRONG_EVIDENCE
pp_case push-all-plan-rejects-secrets-clean-report 2 'git push origin main'
cat > "$H/.claude/hooks/lib/privacy-scan.py" <<'WRONG_EVIDENCE'
print("privacy-scan-v1:all")
WRONG_EVIDENCE
pp_case push-secrets-plan-rejects-all-clean-report 2 'git push secure main'
cat > "$H/.claude/hooks/lib/privacy-scan.py" <<'WRONG_EVIDENCE'
print("clean")
WRONG_EVIDENCE
pp_case push-clean-with-no-evidence-refuses 2 'git push origin main'
cp "$SCRATCH/scanner-real.py" "$H/.claude/hooks/lib/privacy-scan.py"
pp_case private-then-public-pushes-refuse 2 'git push secure main && git push origin main'
pp_case dry-run-then-real-push-refuses 2 'git push --dry-run secure main && git push origin main'
pp_case delete-then-real-push-refuses 2 'git push secure --delete feature && git push origin main'
pp_case quoted-push-is-not-second-command 0 "git push secure main && echo 'git push origin main'"
pp_case no-space-two-pushes-refuse 2 "git push secure main&&git push origin main"
pp_case quoted-chain-diagnostic-is-not-a-push 0 "echo 'git push secure main && git push origin main'"
pp_case quoted-heredoc-chain-diagnostic-is-not-a-push 0 "python3 - <<'PY'
cases = ['git push secure main && git push origin main',
         'git push --dry-run secure main && git push origin main']
print(cases)
PY"
pp_case heredoc-unbalanced-shell-quote-is-literal 0 "python3 - <<'PY'
print(\"unbalanced shell quote: ' git push origin main\")
PY"
mkdir -p "$SCRATCH/bin-failedprivate"
printf '#!/usr/bin/env bash\nprintf "PRIVATE\\n"\nexit 1\n' > "$SCRATCH/bin-failedprivate/gh"
chmod +x "$SCRATCH/bin-failedprivate/gh"
pp_case failed-private-lookup-is-unproven 2 'git push secure main' "$REPO" "$SCRATCH/bin-failedprivate"
# The push is the first `push` after a `git`, not the last `push` word in the text: a recorded
# command ended in prose (`echo push cat`) and the gate read `cat` as the remote (2026-07-17).
pp_case prose-push-after-the-real-push    0 'git push secure main; echo push cat'
gitr reset -q --hard origin/main
pp_case clean-self-hosted-forge-passes 0 'git push selfhost main'
gitr commit -q --allow-empty -m "mentions Acme Widgets in the subject"
pp_case identifier-in-the-commit-message  2 'git push'
gitr reset -q --hard origin/main
printf 'token %s\n' "$SECRET" >> "$REPO/a.txt"; gitr commit -qam "add a token"
pp_case secret-to-a-private-remote        2 'git push secure main'
pp_case secret-to-a-box-of-our-own        2 'git push box main'
# The operator, 2026-10-01: scraped pages under a raw/ directory may carry other sites' keys to a
# proven-private destination, and only there; the path is read from git's own diff headers.
gitr reset -q --hard origin/main
mkdir -p "$REPO/scrape/raw" "$REPO/scrape/rawdata"
printf 'maps key %s\n' "$SECRET" > "$REPO/scrape/raw/page.html"; gitr add scrape; gitr commit -qm scrape
pp_case secret-under-raw-to-a-private-remote 0 'git push secure main'
pp_case secret-under-raw-to-a-box-of-our-own 0 'git push box main'
pp_case secret-under-raw-to-a-public-remote  2 'git push origin main'
printf 'token %s\n' "$SECRET" > "$REPO/scrape/z.txt"; gitr add scrape; gitr commit -qm "after raw"
pp_case exemption-ends-at-the-next-file      2 'git push secure main'
gitr reset -q --hard HEAD~1
printf 'token %s\n' "$SECRET" > "$REPO/scrape/rawdata/x.txt"; gitr add scrape; gitr commit -qm rawdata
pp_case rawdata-is-not-raw                   2 'git push secure main'
gitr config diff.dstPrefix raw/
pp_case repo-diff-prefix-cannot-forge-raw    2 'git push secure main'
gitr config --unset diff.dstPrefix
gitr reset -q --hard HEAD~1
# Indented messages: a message cannot pose as a diff header and switch the exemption on.
gitr commit -q --allow-empty -m "subject" -m "diff --git a/raw/x b/raw/x
+++ b/raw/x
@@ -0,0 +1 @@
token $SECRET"
pp_case message-posing-as-raw-diff-refuses   2 'git push secure main'
gitr reset -q --hard HEAD~1
gitr tag -a v-spoof -m "diff --git a/raw/x b/raw/x
+++ b/raw/x
@@ -0,0 +1 @@
token $SECRET"
pp_case tag-posing-as-raw-diff-refuses       2 'git push secure refs/tags/v-spoof'
gitr tag -d v-spoof >/dev/null
# The pathspec hides raw/ diffs only: a commit touching nothing else still has its message read.
printf 'page\n' > "$REPO/scrape/raw/other.html"; gitr add scrape; gitr commit -qm "token $SECRET"
pp_case raw-only-commit-message-is-scanned   2 'git push secure main'
gitr reset -q --hard HEAD~1
gitr reset -q --hard origin/main
printf 'we use Acme Widgets\n' >> "$REPO/a.txt"; gitr commit -qam "identifier"
pp_case identifier-to-a-box-of-our-own    0 'git push box main'
gitr reset -q --hard origin/main
gitr checkout -q -b feature
printf 'host at %s answers\n' "$MESH_ONE" > "$REPO/b.txt"; gitr add b.txt; gitr commit -qm feature
pp_case branch-with-no-tracking-ref       2 'git push origin feature'
pp_case branch-delete-sends-no-commits    0 'git push origin --delete feature'

# --- pre-push: the refspec shapes that decide what is actually sent ---------------------------
# Each of these sent commits the gate never looked at, because the refspec did not survive
# parsing: a leading `+`, the all-branch forms, tags, and the exact matching refspec.
pp_case plain-refspec-is-the-control      2 'git push origin feature:dest'
pp_case forced-refspec-sends-the-same     2 'git push origin +feature:dest'
pp_case dry-run-publishes-nothing         0 'git push --dry-run origin feature:dest'
pp_case dash-n-publishes-nothing          0 'git push -n origin feature:dest'
gitr checkout -q main
pp_case clean-head-alone-passes           0 'git push origin main'
pp_case all-branches-reach-the-side-one   2 'git push origin --all'
# The exact `:` refspec sends only branches the remote already holds under the same name, so
# the unheld dirty `feature` is not pushed; once the remote holds a clean `feature`, it is.
pp_case matching-refspec-skips-unheld-branches 0 'git push origin :'
gitr push -q origin origin/main:refs/heads/feature
pp_case matching-refspec-scans-held-branches   2 'git push origin :'
# An annotated tag carries its message in the tag object, which `git log -p` never walks.
gitr tag -a v-fixture -m 'this release ships with Acme Widgets'
pp_case tag-message-via-tags-flag         2 'git push origin --tags'
pp_case tag-message-via-explicit-ref      2 'git push origin refs/tags/v-fixture'
gitr tag -d v-fixture >/dev/null

# --- pre-push: the destination is where the commits LAND --------------------------------------
gitr remote add crossed "$SCRATCH/box.git"
printf 'we use Acme Widgets\n' >> "$REPO/a.txt"; gitr commit -qam "destination fixture"
pp_case identifier-to-a-box-fetch-url     0 'git push crossed main'
gitr config remote.crossed.pushurl https://github.com/public/repo.git
pp_case identifier-to-a-public-pushurl    2 'git push crossed main'
pp_case a-remote-name-that-resolves-to-nothing 2 'git push nosuchremote main'
# A `timeout` that cannot run came back as a git verdict and read as "not a repository", so a
# dirty push left unscanned with rc 0 (review, 2026-09-01).
mkdir -p "$SCRATCH/bin-notimeout"
printf '#!/usr/bin/env bash\nexit 127\n' > "$SCRATCH/bin-notimeout/timeout"
chmod +x "$SCRATCH/bin-notimeout/timeout"
pp_case unusable-timeout-is-not-a-verdict 2 'git push' "$REPO" "$SCRATCH/bin-notimeout"
gitr reset -q --hard origin/main

# --- the scanner itself -----------------------------------------------------------------------
# Gate statuses cannot see masking, the finding cap, or throughput: all three stayed green
# through deliberate mutations of the scanner (review, 2026-09-01).
printf 'we use Acme Widgets in this line\n' > "$SCRATCH/one.txt"
scan "$SCRATCH/one.txt"
[ "$SCAN_RC" = 10 ] && ok scanner-reports-a-finding || bad scanner-reports-a-finding "rc=$SCAN_RC"
case "$SCAN_OUT" in
    *'***'*) ok scanner-masks-the-match ;;
    *) bad scanner-masks-the-match "no *** in ${SCAN_OUT:0:100}" ;;
esac
case "$SCAN_OUT" in
    *'Acme Widgets'*) bad scanner-never-reprints-the-token "the finding line carries it" ;;
    *) ok scanner-never-reprints-the-token ;;
esac
seq 25 | sed 's/^/line &: we use Acme Widgets/' > "$SCRATCH/many.txt"
scan "$SCRATCH/many.txt"
CAPPED="$(printf '%s\n' "$SCAN_OUT" | grep -c '^line ')"
[ "$CAPPED" = 20 ] && ok scanner-caps-at-twenty-findings \
    || bad scanner-caps-at-twenty-findings "25 dirty lines gave $CAPPED findings, not 20"
yes 'filler line with nothing private in it at all' 2>/dev/null | head -c 204800 > "$SCRATCH/big.txt"
scan "$SCRATCH/big.txt"
[ "$SCAN_RC" = 0 ] && ok scanner-drains-200kb-clean \
    || bad scanner-drains-200kb-clean "rc=$SCAN_RC :: ${SCAN_OUT:0:100}"
# Past the cap the scanner must keep READING: an early close SIGPIPEs the producer (status 141
# on the group's last command), and the calling gate reads a failed producer as an unfinished scan.
DRAIN="$( { seq 25 | sed 's/^/we use Acme Widgets /'; head -c 300000 /dev/zero | tr '\0' a | fold -w 200; } \
    | PRIVACY_TOKENS_FILE="$TOKENS" /usr/bin/python3 "$ROOT/hooks/lib/privacy-scan.py" --classes all >/dev/null 2>&1; \
    echo "${PIPESTATUS[0]}:${PIPESTATUS[1]}" )"
[ "$DRAIN" = "0:10" ] && ok scanner-drains-after-the-cap \
    || bad scanner-drains-after-the-cap "producer:scanner = $DRAIN, want 0:10"

# --- pre-push: the refspec and destination forms the second review found (2026-09-01) --------
R2="$SCRATCH/repo2"; git init -q -b main "$R2"; g2() { git -C "$R2" "$@"; }
git init -q --bare "$SCRATCH/remote2.git"
g2 remote add origin https://github.com/public/repo2
g2 config url."$SCRATCH/remote2.git".pushInsteadOf https://github.com/public/repo2
printf 'hello\n' > "$R2/a.txt"; g2 add a.txt; g2 commit -qm initial; g2 push -q origin main
# An alias whose insteadOf expansion is a public forge URL; nothing is ever pushed to it here.
g2 remote add corp corp:repo2
g2 config url.https://github.com/public/.insteadOf corp:
printf 'we use Acme Widgets\n' >> "$R2/a.txt"; g2 commit -qam dirty
pp_case alias-expanding-to-a-forge-is-not-private 2 'git push corp main' "$R2"
g2 reset -q --hard origin/main
printf 'we use Acme Widgets\n' > "$R2/c.txt"; g2 add c.txt; g2 commit -qm leak
g2 update-ref refs/custom/leak HEAD; g2 reset -q --hard origin/main
pp_case mirror-sends-custom-refs-too          2 'git push origin --mirror' "$R2"
g2 checkout -q -b feature; printf 'we use Acme Widgets\n' > "$R2/f.txt"; g2 add f.txt; g2 commit -qm feature
g2 checkout -q main
pp_case matching-colon-skips-unheld-branches  0 'git push origin :' "$R2"
g2 checkout -q -b side; g2 commit -q --allow-empty -m side; g2 tag -a -m 'we use Acme Widgets' dirtytag
g2 checkout -q main
pp_case follow-tags-ignores-unreachable-tags  0 'git push origin --follow-tags' "$R2"
pp_case tags-flag-sends-every-tag             2 'git push origin --tags' "$R2"

# --- negative controls ------------------------------------------------------------------------
# Take the `lit` matcher out and the case that names it must pass. Without this the suite cannot
# tell a working matcher from a fixture that happens to contain the string twice. The push
# control needs an OUTGOING commit that carries the literal: at `main == origin/main` there is
# nothing to scan and the control passed for no reason at all (review, 2026-09-01).
printf 'we use Acme Widgets\n' >> "$REPO/a.txt"; gitr commit -qam "negative control commit"
gh_case control-lit-refuses-while-the-matcher-stands  2 "$W 'we use Acme Widgets'"
pp_case control-push-refuses-while-the-matcher-stands 2 'git push'
grep -v '^lit ' "$TOKENS" > "$TOKENS.trimmed" && mv "$TOKENS.trimmed" "$TOKENS"
gh_case control-lit-passes-once-the-matcher-is-gone 0 "$W 'we use Acme Widgets'"
pp_case control-push-passes-once-the-matcher-is-gone 0 'git push'
pp_case control-failed-lookup-clean-content-passes 0 'git push secure main' "$REPO" "$SCRATCH/bin-failedprivate"

printf '\n%d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] || { printf 'failed: %s\n' "${FAILED[*]}"; exit 1; }
# A stable success signal for red-suite's contract runner: rc 0 alone would also pass a child
# that silently ran nothing, and a case count would break on every routine addition.
printf 'privacy-gates: refusals and their negative controls both fired\n'
