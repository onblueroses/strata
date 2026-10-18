#!/usr/bin/env bash
# Generated from proved Bend policy; edit Policy.bend, then run build.sh.
# Source SHA256: 0f9b4d2df3ebcbda5ff3735cbcb15cf7439588b450d6d1ace0aa315c2fd4073c
# Runtime uses Bash builtins only.

privacy_plan() {
    [ "$#" -eq 3 ] || refuse decision-input "BLOCKED (privacy decision): invalid privacy_plan input."
    case "${1:-}:${2:-}:${3:-}" in
        0:0:0|0:0:1|1:0:0|1:0:1|1:1:0|1:1:1) CLASSES=skip ;;
        0:1:0) CLASSES=all ;;
        0:1:1) CLASSES=secrets ;;
        *) refuse decision-input "BLOCKED (privacy decision): invalid policy evidence." ;;
    esac
}

privacy_verdict() {
    [ "$#" -eq 3 ] || refuse decision-input "BLOCKED (privacy decision): invalid privacy_verdict input."
    case "${1:-}:${2:-}:${3:-}" in
        skip:none:0|skip:none:1|skip:none:2|skip:none:3|skip:secrets:0|skip:secrets:1|skip:secrets:2|skip:secrets:3|skip:all:0|skip:all:1|skip:all:2|skip:all:3|secrets:secrets:1|all:all:1) PRIVACY_VERDICT=allow ;;
        secrets:none:0|secrets:none:1|secrets:none:2|secrets:none:3|secrets:secrets:0|secrets:secrets:3|secrets:all:0|secrets:all:1|secrets:all:2|secrets:all:3|all:none:0|all:none:1|all:none:2|all:none:3|all:secrets:0|all:secrets:1|all:secrets:2|all:secrets:3|all:all:0|all:all:3) PRIVACY_VERDICT=failure ;;
        secrets:secrets:2|all:all:2) PRIVACY_VERDICT=finding ;;
        *) refuse decision-input "BLOCKED (privacy decision): invalid policy evidence." ;;
    esac
}

privacy_target() {
    [ "$#" -eq 2 ] || refuse decision-input "BLOCKED (privacy decision): invalid privacy_target input."
    case "${1:-}:${2:-}" in
        0:0|0:1|1:0) PROVEN_PRIVATE=0 ;;
        1:1) PROVEN_PRIVATE=1 ;;
        *) refuse decision-input "BLOCKED (privacy decision): invalid policy evidence." ;;
    esac
}

privacy_finish() {
    [ "$#" -eq 2 ] || refuse decision-input "BLOCKED (privacy decision): invalid scan outcome."
    local scan coverage=none report="$2"
    SCAN_FINDINGS="$report"
    case "$report" in
        privacy-scan-v1:all) coverage=all; SCAN_FINDINGS="" ;;
        $'privacy-scan-v1:all\n'*) coverage=all; SCAN_FINDINGS="${report#*$'\n'}" ;;
        privacy-scan-v1:secrets) coverage=secrets; SCAN_FINDINGS="" ;;
        $'privacy-scan-v1:secrets\n'*) coverage=secrets; SCAN_FINDINGS="${report#*$'\n'}" ;;
    esac
    case "$1" in 0) scan=1 ;; 10) scan=2 ;; *) scan=3 ;; esac
    privacy_verdict "${CLASSES:-}" "$coverage" "$scan"
}
