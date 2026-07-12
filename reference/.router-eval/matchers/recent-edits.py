#!/usr/bin/env python3
"""recent-edits matcher backed by the live context-doc-router hook."""

from _common import docs_from_scores, load_router, run


def build_docs(data):
    router = load_router()
    return docs_from_scores(
        router.recent_edit_docs(data.get("transcript_path")), "recent-edits"
    )


if __name__ == "__main__":
    run("recent-edits", build_docs)
