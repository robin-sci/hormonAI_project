"""Launch configuration shared by the CLI, the Streamlit GUI and the eval harness.

Every option is defined once here, with its HORMONAI_* environment variable as
the default, so all entry points run with the same settings.
Precedence: command-line flag > environment variable > built-in default.
"""

from __future__ import annotations

import argparse
import os
from typing import Any, Dict, List, Optional

from rag_core import HybridFAQRetriever


def add_retrieval_args(p: argparse.ArgumentParser, default_scope: str) -> None:
    """Index, model, retrieval-scope and answer/abstain gate options."""
    p.add_argument("--data-dir", default="data")
    p.add_argument("--top-k", type=int, default=40)
    p.add_argument("--embedding-model",
                   default=os.getenv("HORMONAI_EMBEDDING_MODEL",
                                     "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"),
                   help="Must match the model used at ingestion (e.g. BAAI/bge-m3).")
    # Reranking reorders candidates so the gates operate on better-ordered
    # results. The cross-encoder degrades gracefully if it cannot be loaded.
    p.add_argument("--rerank", action=argparse.BooleanOptionalAction, default=True,
                   help="CrossEncoder reranking (better ordering, slower). Default: on.")
    p.add_argument("--rerank-model",
                   default=os.getenv("HORMONAI_RERANK_MODEL", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"),
                   help="Cross-encoder reranker (e.g. BAAI/bge-reranker-v2-m3 for stronger multilingual ranking).")
    p.add_argument("--rerank-top-n", type=int,
                   default=int(os.getenv("HORMONAI_RERANK_TOP_N", "5")),
                   help="Rerank only the top-N fused candidates (lower = faster; default 5).")
    #   shared   -> combined kb_all index, same-language-first + cross-lingual fallback
    #   language -> ONLY the query-language corpus (kb_<lang>), no cross-lingual fallback
    p.add_argument("--retrieval-scope", choices=["shared", "language"],
                   default=(os.getenv("HORMONAI_RETRIEVAL_SCOPE") or default_scope).lower(),
                   help=f"'shared' = combined index with cross-lingual fallback; "
                        f"'language' = query-language corpus only (default here: {default_scope}).")
    # Gate thresholds: calibrate on tests/eval_set.jsonl for the deployed models.
    p.add_argument("--sem-threshold", type=float,
                   default=float(os.getenv("HORMONAI_SEM_THRESHOLD", "0.62")),
                   help="Dense cosine accept threshold when reranking is OFF (default: 0.62).")
    p.add_argument("--rerank-threshold", type=float,
                   default=float(os.getenv("HORMONAI_RERANK_THRESHOLD", "-1.0")),
                   help="Cross-encoder accept threshold when reranking is ON (default: -1.0).")
    p.add_argument("--dense-floor", type=float,
                   default=float(os.getenv("HORMONAI_DENSE_FLOOR", "0.50")),
                   help="Cosine floor for the high-IDF lexical safety net (default: 0.50).")


def parse_args(default_scope: str, argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Options of the chat interfaces (CLI and GUI)."""
    p = argparse.ArgumentParser(description="hormonAI chatbot (knowledge-base-restricted RAG).")
    p.add_argument("--language", "-l", choices=["en", "fr"], default="en")
    add_retrieval_args(p, default_scope)
    p.add_argument("--use-llm", action="store_true",
                   help="Rephrase answers with the local LLM (grounded in the retrieved text only).")
    p.add_argument("--llm-model", default=os.getenv("HORMONAI_LLM_MODEL", "llama3.2"),
                   help="Ollama model name (default: llama3.2).")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--audit-log", default="logs/audit.jsonl")
    return p.parse_args(argv)


def load_retriever(args: argparse.Namespace, language: str, shared: bool,
                   rerank: Optional[bool] = None) -> HybridFAQRetriever:
    """Build and load a retriever: the combined index if `shared`, else kb_<language>."""
    r = HybridFAQRetriever(
        language=language,
        data_dir=args.data_dir,
        top_k=args.top_k,
        embedding_model=args.embedding_model,
        rerank=args.rerank if rerank is None else rerank,
        rerank_model=args.rerank_model,
        rerank_top_n=args.rerank_top_n,
        shared=shared,
    )
    r.load()
    return r


def gate_kwargs(args: argparse.Namespace) -> Dict[str, Any]:
    """Answer/abstain thresholds as keyword arguments for answer_query()."""
    return {
        "sem_accept_threshold": args.sem_threshold,
        "rerank_accept_threshold": args.rerank_threshold,
        "dense_floor": args.dense_floor,
    }
