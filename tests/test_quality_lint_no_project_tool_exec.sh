#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="${HOOK:-$ROOT_DIR/hooks/quality-lint-on-write.sh}"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

bash_bin="$(command -v bash)"
tmpbin="$tmpdir/bin"
mkdir -p "$tmpbin"

link_required_tool() {
    local tool="$1"
    local target

    target="$(command -v "$tool")"
    ln -s "$target" "$tmpbin/$tool"
}

for tool in basename cat dirname jq tr; do
    link_required_tool "$tool"
done

run_hook() {
    local file_path="$1"

    PATH="$tmpbin" jq -n --arg file_path "$file_path" '{tool_input: {file_path: $file_path}}' \
        | PATH="$tmpbin" "$bash_bin" "$HOOK"
}

assert_allowed() {
    local file_path="$1"

    if ! run_hook "$file_path" >/dev/null 2>&1; then
        echo "expected hook to allow $file_path" >&2
        exit 1
    fi
}

assert_not_reached() {
    local marker="$1"
    local label="$2"

    if [ -e "$marker" ]; then
        echo "expected $label not to be executed automatically" >&2
        exit 1
    fi
}

benign_file="$tmpdir/plain.js"
printf 'const value = 1;\n' >"$benign_file"
assert_allowed "$benign_file"

eslint_marker="$tmpdir/eslint-ran"
js_project="$tmpdir/js-project"
mkdir -p "$js_project/node_modules/.bin"
printf '{"scripts":{"lint":"eslint ."}}\n' >"$js_project/package.json"
printf 'const value = 1;\n' >"$js_project/index.js"

cat >"$js_project/node_modules/.bin/eslint" <<EOF
#!$bash_bin
printf 'ran\n' >"$eslint_marker"
exit 0
EOF
chmod +x "$js_project/node_modules/.bin/eslint"

assert_allowed "$js_project/index.js"
assert_not_reached "$eslint_marker" "repo-local eslint"

cargo_marker="$tmpdir/cargo-ran"
rust_project="$tmpdir/rust-project"
mkdir -p "$rust_project/src"
printf '[package]\nname = "fixture"\nversion = "0.1.0"\nedition = "2021"\n' >"$rust_project/Cargo.toml"
printf 'pub fn value() -> i32 { 1 }\n' >"$rust_project/src/lib.rs"

cat >"$tmpbin/cargo" <<EOF
#!$bash_bin
printf 'ran\n' >"$cargo_marker"
exit 0
EOF
chmod +x "$tmpbin/cargo"

assert_allowed "$rust_project/src/lib.rs"
assert_not_reached "$cargo_marker" "cargo clippy"
