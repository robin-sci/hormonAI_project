"""Characterization (snapshot) tests for the answering pipeline.

Runs the real indexes in data/ and the real answer_query() with deterministic
fake models (see fakes.py) across several configurations, and compares every
patient-visible output with tests/snapshots/pipeline.json.

These tests record CURRENT behaviour, including known bugs: their job is to
prove that refactoring changes nothing. When a change is meant to alter
behaviour, regenerate the snapshot and review the diff:

    UPDATE_SNAPSHOT=1 python -m pytest tests/test_snapshot.py
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Dict, List

import pytest

from hormonai import answer, llm, retrieval, text
from fakes import fake_llm_generate, unreachable_llm_generate

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(TESTS_DIR), "data")
SNAPSHOT_PATH = os.path.join(TESTS_DIR, "snapshots", "pipeline.json")

EXTRA_QUERIES = [
    {"id": "edge-empty", "lang": "en", "query": ""},
    {"id": "edge-space", "lang": "fr", "query": "   "},
    {"id": "edge-long", "lang": "en", "query": "Can I take tamoxifen with food? " * 40},
    {"id": "edge-stats-bait", "lang": "en", "query": "What percentage of men get prostate cancer?"},
    {"id": "edge-heart-rate", "lang": "en", "query": "Does tamoxifen affect my heart rate?"},
    {"id": "edge-fr-accents", "lang": "fr", "query": "ménopause, ostéoporose et récidive : quelle fréquence ?"},
    {"id": "edge-fr-pills", "lang": "fr", "query": "Combien de comprimés par jour ?"},
    {"id": "edge-crossling", "lang": "fr", "query": "What are the side effects of letrozole?"},
    {"id": "edge-mortality", "lang": "en", "query": "Does hormone therapy reduce the risk of dying from breast cancer?"},
]

# (name, shared, rerank, use_llm, llm_mode, thresholds)
CONFIGS = [
    ("shared-rerank", True, True, False, None, {}),
    ("shared-dense", True, False, False, None, {}),
    ("shared-dense-permissive", True, False, False, None,
     {"sem_accept_threshold": 0.0, "dense_floor": 0.0}),
    ("shared-dense-lexical-net", True, False, False, None,
     {"sem_accept_threshold": 0.99, "dense_floor": 0.0}),
    ("lang-rerank", False, True, False, None, {}),
    ("lang-dense-permissive", False, False, False, None,
     {"sem_accept_threshold": 0.0, "dense_floor": 0.0}),
    ("shared-rerank-llm", True, True, True, "ok", {}),
    ("shared-rerank-llm-down", True, True, True, "down", {}),
]

RESULT_FIELDS = [
    "answered", "answer_text", "source_title", "source_index", "source_indices",
    "sources_text", "llm_status", "llm_error",
]


def _queries() -> List[Dict[str, str]]:
    with open(os.path.join(TESTS_DIR, "eval_set.jsonl"), encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return [{"id": r["id"], "lang": r["lang"], "query": r["query"]} for r in rows] + EXTRA_QUERIES


@lru_cache(maxsize=None)
def _retriever(shared: bool, lang: str, rerank: bool) -> retrieval.HybridFAQRetriever:
    r = retrieval.HybridFAQRetriever(
        language=lang, data_dir=DATA_DIR, rerank=rerank, rerank_top_n=5, shared=shared,
    )
    r.load()
    return r


def _strip_timing(debug: Any) -> Any:
    if isinstance(debug, dict):
        return {k: _strip_timing(v) for k, v in debug.items() if k != "timing_ms"}
    if isinstance(debug, list):
        return [_strip_timing(v) for v in debug]
    return debug


def _run_pipeline(monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name, shared, rerank, use_llm, llm_mode, thresholds in CONFIGS:
        if llm_mode == "ok":
            monkeypatch.setattr(llm.LLMWrapperWriter, "_generate", fake_llm_generate)
        elif llm_mode == "down":
            monkeypatch.setattr(llm.LLMWrapperWriter, "_generate", unreachable_llm_generate)
        rows = {}
        queries = _queries()
        if use_llm:
            queries = queries[:10] + EXTRA_QUERIES
        for q in queries:
            retriever = _retriever(shared, "en" if shared else q["lang"], rerank)
            res = answer.answer_query(
                retriever=retriever, user_query=q["query"], language=q["lang"], use_llm=use_llm,
                debug=True, **thresholds,
            )
            row = {f: getattr(res, f) for f in RESULT_FIELDS}
            row["debug"] = _strip_timing(res.debug)
            for cand in row["debug"].get("top_candidates", []):
                cand.pop("q", None)  # question text is already identified by idx
            rows[q["id"]] = row
        out[name] = rows
        monkeypatch.undo()
    return out


def _helpers() -> Dict[str, Any]:
    """Outputs of the pure helpers on fixed inputs."""
    reframe_inputs = [
        ("en", "Tamoxifen lowers the risk of dying from breast cancer."),
        ("en", "Tamoxifen reduces death from breast cancer by about a third."),
        ("en", "It lowers your chance of recurrence and of dying from the cancer."),
        ("en", "The cancer cells die when deprived of estrogen."),
        ("fr", "Elle augmente la mortalité par cancer du sein si on l'arrête."),
        ("fr", "Le traitement diminue la mortalité du cancer du sein de 30 %."),
        ("fr", "Il réduit le risque d'en mourir."),
        ("fr", "La mort des cellules cancéreuses est souhaitable."),
    ]
    preamble_inputs = [
        "Here is a clear and compassionate response to your question: Hot flashes are common.",
        "Voici une réponse claire : Les bouffées de chaleur sont fréquentes.",
        "Of course you should not stop treatment without talking to your doctor. Other info.",
        "Hot flashes are common.",
        "",
    ]
    stats_inputs = [
        ("en", "What percentage of women have hot flashes?"),
        ("en", "How many years do I take tamoxifen?"),
        ("en", "Does tamoxifen affect my heart rate?"),
        ("fr", "Quel est le taux de récidive ?"),
        ("fr", "Quelle fréquence pour les bouffées de chaleur ?"),
        ("fr", "Combien de comprimés par jour ?"),
    ]
    question_inputs = [
        "What are the side effects?", "and it helps.", "Why was hormone therapy prescribed?",
        "Est-ce que je peux arrêter ?", "", "1.",
    ]
    return {
        "reframe": [[lang, t, answer._reframe_survival(t, lang)] for lang, t in reframe_inputs],
        "preamble": [[t, llm._strip_llm_preamble(t)] for t in preamble_inputs],
        "stats_intent": [[lang, t, text._is_stats_intent(t, lang)] for lang, t in stats_inputs],
        "tokenize": [[t, text._tokenize(t)] for t in ["ménopause", "anti-hormone therapy", "Tamoxifen 20mg!"]],
        "looks_like_question": [[t, text._looks_like_faq_question(t)] for t in question_inputs],
        "crosslingual_notice": [answer._crosslingual_notice(a, b) for a, b in
                                [("en", "fr"), ("fr", "en"), ("en", "en")]],
        "abstain": [answer.build_abstain("en"), answer.build_abstain("fr")],
    }


def _normalize(obj: Any) -> Any:
    return json.loads(json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str))


def test_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    actual = _normalize({"helpers": _helpers(), "pipeline": _run_pipeline(monkeypatch)})

    if os.getenv("UPDATE_SNAPSHOT") == "1" or not os.path.exists(SNAPSHOT_PATH):
        os.makedirs(os.path.dirname(SNAPSHOT_PATH), exist_ok=True)
        with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
            json.dump(actual, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            f.write("\n")
        pytest.skip("snapshot written")

    with open(SNAPSHOT_PATH, encoding="utf-8") as f:
        expected = json.load(f)

    assert actual["helpers"] == expected["helpers"]
    for config, rows in expected["pipeline"].items():
        for qid, row in rows.items():
            assert actual["pipeline"][config][qid] == row, f"{config} / {qid} changed"
    assert actual["pipeline"].keys() == expected["pipeline"].keys()
