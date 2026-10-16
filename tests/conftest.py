"""Pytest setup: import the app modules from the repo root with fake models."""

from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
for path in (REPO_ROOT, TESTS_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from fakes import install_fake_sentence_transformers  # noqa: E402

# Must run before rag_core is imported anywhere.
install_fake_sentence_transformers()

# Legacy standalone scripts, not pytest tests.
collect_ignore = ["test_retreival.py", "inspect_qa.py", "eval_retrieval.py", "pdf_fidelity.py"]
