#!/usr/bin/env python3
"""Combined router matcher backed by the live context-doc-router hook."""

from _common import load_router, run, text_field


def build_docs(data):
    router = load_router()
    prompt = text_field(data, "prompt")
    cwd = text_field(data, "cwd")
    merged = {}
    for src, sig in (
        (router.cwd_path_docs(cwd), "cwd-path"),
        (router.recent_edit_docs(data.get("transcript_path")), "recent-edits"),
        (router.lex_docs(prompt, cwd), "lex"),
    ):
        for name, score in src.items():
            if name not in merged or score > merged[name][0]:
                merged[name] = (score, sig)
    return [
        {"name": n, "score": s, "signal": sig}
        for n, (s, sig) in sorted(merged.items(), key=lambda kv: -kv[1][0])
    ]


if __name__ == "__main__":
    run("router-combo", build_docs)
