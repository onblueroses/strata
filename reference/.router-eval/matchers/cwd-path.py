#!/usr/bin/env python3
"""cwd-path matcher backed by the live context-doc-router hook."""

from _common import docs_from_scores, load_router, run, text_field


def build_docs(data):
    router = load_router()
    return docs_from_scores(router.cwd_path_docs(text_field(data, "cwd")), "cwd-path")


if __name__ == "__main__":
    run("cwd-path", build_docs)
