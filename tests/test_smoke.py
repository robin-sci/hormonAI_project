"""End-to-end smoke tests for the CLI and the Streamlit GUI (with fake models)."""

from __future__ import annotations

import html
import json
import os
import sys

import pytest

import rag_core

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")
QUESTION = "How long will I be on hormone therapy?"


def _expected(language: str, shared: bool) -> rag_core.AnswerResult:
    r = rag_core.HybridFAQRetriever(language=language, data_dir=DATA_DIR, rerank=True,
                                    rerank_top_n=5, shared=shared)
    r.load()
    return rag_core.answer_query(retriever=r, user_query=QUESTION)


def test_cli_answers_logs_and_cites(monkeypatch, capsys, tmp_path):
    import chatbot

    log_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(sys, "argv", [
        "chatbot.py", "-l", "en", "--data-dir", DATA_DIR, "--audit-log", str(log_path),
        "--retrieval-scope", "shared",
    ])
    inputs = iter([QUESTION, "", "exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    chatbot.main()

    out = capsys.readouterr().out
    expected = _expected("en", shared=True)
    assert expected.answered
    assert f"Bot: {expected.answer_text}" in out
    assert expected.sources_text in out
    records = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert len(records) == 1 and records[0]["answered"] is True


def test_gui_answers_with_sources(monkeypatch):
    testing = pytest.importorskip("streamlit.testing.v1")

    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setattr(sys, "argv", ["hormonai_app.py"])
    at = testing.AppTest.from_file(os.path.join(REPO_ROOT, "hormonai_app.py"), default_timeout=60)
    at.run()
    assert not at.exception

    at.text_area(key="user_input").input(QUESTION)
    next(b for b in at.button if b.label == "Send").click()
    at.run()
    assert not at.exception

    expected = _expected("en", shared=True)
    rendered = "\n".join(m.value for m in at.markdown)
    first_line = expected.answer_text.splitlines()[0]
    assert html.escape(first_line) in rendered
    assert any(e.label == "Sources used for this answer" for e in at.expander)


def test_eval_harness_runs_on_both_scopes(monkeypatch, capsys):
    import eval_retrieval

    for scope in ("language", "shared"):
        monkeypatch.setattr(sys, "argv", [
            "eval_retrieval.py", "--data-dir", DATA_DIR, "--retrieval-scope", scope,
        ])
        assert eval_retrieval.main() in (0, 1)
        out = capsys.readouterr().out
        assert "CORE CASES" in out and "FALSE-ANSWER" in out
        assert ("kb_all_*" in out) == (scope == "shared")


def test_interface_defaults(monkeypatch):
    from config import parse_args

    monkeypatch.delenv("HORMONAI_RETRIEVAL_SCOPE", raising=False)
    monkeypatch.delenv("HORMONAI_RERANK_TOP_N", raising=False)
    assert parse_args(default_scope="language", argv=[]).retrieval_scope == "language"  # CLI
    gui = parse_args(default_scope="shared", argv=[])  # GUI
    assert (gui.retrieval_scope, gui.rerank, gui.rerank_top_n) == ("shared", True, 5)
    monkeypatch.setenv("HORMONAI_RETRIEVAL_SCOPE", "Shared")
    assert parse_args(default_scope="language", argv=[]).retrieval_scope == "shared"
