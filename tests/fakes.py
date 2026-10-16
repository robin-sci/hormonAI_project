"""Deterministic stand-ins for the embedding model, the reranker and Ollama.

The real models are large downloads and are not needed to check that a code
change keeps behaviour identical: the tests run the real indexes and the real
pipeline with these fakes, so any difference in the output comes from the code.
"""

from __future__ import annotations

import hashlib
import re
import sys
import types
from typing import Iterable, List, Sequence, Tuple

import numpy as np

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _words(text: str) -> List[str]:
    return [w.lower() for w in _WORD_RE.findall(text or "")]


class FakeSentenceTransformer:
    """Hashed bag-of-words embedder with the dimension of the committed indexes."""

    dim = 1024

    def __init__(self, model_name: str = "", *args, **kwargs) -> None:
        self.model_name = model_name

    def get_sentence_embedding_dimension(self) -> int:
        return self.dim

    def encode(self, texts: Sequence[str], convert_to_numpy: bool = True, **kwargs) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype="float32")
        for row, text in enumerate(texts):
            for w in _words(text):
                h = int(hashlib.md5(w.encode("utf-8")).hexdigest()[:8], 16)
                out[row, h % self.dim] += 1.0 if (h >> 12) & 1 else -1.0
        return out


class FakeCrossEncoder:
    """Scores a (query, passage) pair by word overlap, on a reranker-like scale."""

    def __init__(self, model_name: str = "", *args, **kwargs) -> None:
        self.model_name = model_name

    def predict(self, pairs: Iterable[Tuple[str, str]]) -> List[float]:
        scores: List[float] = []
        for query, passage in pairs:
            q, p = set(_words(query)), set(_words(passage))
            overlap = len(q & p) / max(1, len(q))
            scores.append(round(6.0 * overlap - 3.0, 6))
        return scores


def install_fake_sentence_transformers() -> None:
    """Make `import sentence_transformers` resolve to the fakes."""
    mod = types.ModuleType("sentence_transformers")
    mod.SentenceTransformer = FakeSentenceTransformer  # type: ignore[attr-defined]
    mod.CrossEncoder = FakeCrossEncoder  # type: ignore[attr-defined]
    sys.modules["sentence_transformers"] = mod


def fake_llm_generate(self, system: str, prompt: str, max_tokens: int) -> str:
    """Replacement for LLMWrapperWriter._generate that echoes the source text."""
    self.last_error = None
    source = prompt.split("SOURCE", 1)[-1][:300]
    return "Here is a clear and compassionate answer: " + " ".join(source.split())


def unreachable_llm_generate(self, system: str, prompt: str, max_tokens: int) -> str:
    """Replacement for LLMWrapperWriter._generate that simulates Ollama being down."""
    self.last_error = "URLError: <urlopen error [Errno 111] Connection refused>"
    return ""
