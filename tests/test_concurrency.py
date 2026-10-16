"""One shared retriever must give each concurrent session its own language."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

from hormonai import answer, retrieval

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

QUERIES = [
    ("en", "How long will I be on hormone therapy?"),
    ("fr", "Pendant combien de temps devrai-je suivre une hormonothérapie ?"),
    ("en", "What are the most common side effects?"),
    ("fr", "Quels sont les effets secondaires les plus courants ?"),
]


def _visible(res: answer.AnswerResult) -> tuple:
    return (res.answered, res.answer_text, res.source_indices, res.sources_text)


def test_concurrent_languages_do_not_leak_between_sessions():
    shared = retrieval.HybridFAQRetriever(language="en", data_dir=DATA_DIR, rerank=True,
                                          rerank_top_n=5, shared=True)
    shared.load()

    def ask(lang_query):
        lang, query = lang_query
        return _visible(answer.answer_query(retriever=shared, user_query=query, language=lang))

    expected = [ask(q) for q in QUERIES]
    assert any(e[0] for e in expected)  # the check is meaningful only if something is answered

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(ask, QUERIES * 25))
    assert results == expected * 25
    assert shared.language == "en"  # never mutated
