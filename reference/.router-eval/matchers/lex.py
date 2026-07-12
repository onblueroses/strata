#!/usr/bin/env python3
"""lex matcher backed by the live context-doc-router hook."""

from _common import docs_from_scores, load_router, run, text_field


def build_docs(data):
    router = load_router()
    return docs_from_scores(
        router.lex_docs(text_field(data, "prompt"), text_field(data, "cwd")), "lex"
    )


if __name__ == "__main__":
    run("lex", build_docs)
