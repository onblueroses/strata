from __future__ import annotations

from memory import engine


def test_top_terms_caps_long_query_evidence() -> None:
    generic_terms = [f"generic{index}" for index in range(12)]
    corpus = [
        {
            "id": "target",
            "title": "",
            "description": "",
            "body": "quartzforge ioncalibration",
        },
        *[
            {
                "id": f"filler-{index:02d}",
                "title": "",
                "description": "",
                "body": " ".join(generic_terms[index % 3 :] + ["ordinary"] * 20),
            }
            for index in range(20)
        ],
    ]
    positive = engine.search(
        "quartzforge ioncalibration", corpus=corpus, use_embeddings=False
    )[0]
    negative = engine.search(
        " ".join(generic_terms * 5), corpus=corpus, use_embeddings=False
    )[0]
    assert positive["id"] == "target"
    assert float(positive["top_terms_score"]) > 0.0
    assert float(negative["score"]) > float(negative["top_terms_score"])
    assert float(negative["top_terms_score"]) < float(positive["top_terms_score"])


def test_top_terms_score_uses_at_most_two_distinct_terms() -> None:
    corpus = [{"id": "doc", "body": "alpha beta gamma delta"}]
    index = engine.BM25Index(corpus)
    contributions = index.query_term_contributions("alpha beta gamma delta", "doc")
    expected = sum(sorted(contributions.values(), reverse=True)[:2])
    assert index.top_term_contributions("alpha beta gamma delta", "doc") == expected
