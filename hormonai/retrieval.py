from __future__ import annotations
"""Hybrid retrieval over the knowledge-base indexes: BM25 + three FAISS
channels fused with Reciprocal Rank Fusion, optional CrossEncoder rerank."""

import math
import os
import pickle
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from hormonai.text import (
    _concept_match_stems,
    _looks_like_faq_question,
    _norm_lang,
    _stem_set,
    _tokenize,
)


# ---------------------------
# Dataclasses
# ---------------------------

@dataclass
class RetrievalCandidate:
    index: int
    question: str
    section: str
    answer: str
    fused_score: float
    rerank_score: Optional[float] = None
    # Best cosine similarity to the query across the dense (FAISS) indexes.
    # Used by the semantic-accept path so the answer/abstain decision is not
    # purely lexical. None when no dense index returned this candidate.
    dense_sim: Optional[float] = None
    # Language of the source item ("en"/"fr"). Used for same-language-first
    # selection with cross-lingual fallback in shared mode.
    lang: str = ""
    # Provenance, so display/citation can branch by type. For an article chunk
    # `question` is a heading breadcrumb (not a real question), so the formatters
    # must NOT present it as one.
    source_type: str = "faq"
    source_id: str = ""
    heading_path: str = ""


# ---------------------------
# Hybrid Retriever
# ---------------------------

class HybridFAQRetriever:
    def __init__(
        self,
        language: str = "en",
        data_dir: str = "data",
        top_k: int = 40,   # candidate pool per channel; sized for the enlarged, bilingual corpus
        embedding_model: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        rerank: bool = False,
        rerank_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
        rerank_top_n: int = 20,   # only rerank the top-N fused candidates (latency vs. recall)
        shared: bool = False,
        corpus_prefix: Optional[str] = None,
    ):
        # `language` is the ACTIVE QUERY language (drives stemming, IDF anchors,
        # query prefix). In shared mode the corpus contains all languages and
        # this attribute may be reassigned per query.
        self.language = _norm_lang(language)
        self.data_dir = data_dir
        self.top_k = top_k
        self.embedding_model_name = embedding_model
        # Shared multilingual mode: load one combined index ('<prefix>_all_*')
        # spanning all languages, prefer same-language candidates, fall back
        # cross-lingual. `corpus_prefix` overrides the loaded basename.
        self.shared = shared
        self.corpus_prefix = corpus_prefix

        self.rerank = rerank
        self.rerank_model = rerank_model
        self.rerank_top_n = max(2, int(rerank_top_n))

        self._items: List[Dict[str, Any]] = []
        self._bm25: Optional[BM25Okapi] = None
        self._index_q: Optional[faiss.Index] = None
        self._index_qa: Optional[faiss.Index] = None
        self._index_qp: Optional[faiss.Index] = None
        self._embedder: Optional[SentenceTransformer] = None
        self._cross_encoder = None

        self._stored_embedding_model_name: Optional[str] = None
        self._query_prefix: str = ""

        # Per-language corpus statistics for IDF-weighted anchor extraction
        # (replaces the hand-maintained stopword / generic / emotion lists).
        # Keyed by language: {lang: {df, idf, size}}. Accessors use
        # the ACTIVE query language so the same combined corpus serves both.
        self._stats_by_lang: Dict[str, Dict[str, Any]] = {}

    def load(self) -> None:
        if self.corpus_prefix:
            prefix = self.corpus_prefix
        elif self.shared:
            prefix = "kb_all"
        else:
            prefix = f"kb_{self.language}"
        qa_path = os.path.join(self.data_dir, f"{prefix}_qa.pkl")
        bm25_path = os.path.join(self.data_dir, f"{prefix}_bm25.pkl")
        idx_q_path = os.path.join(self.data_dir, f"{prefix}_index_q.faiss")
        idx_qa_path = os.path.join(self.data_dir, f"{prefix}_index_qa.faiss")
        idx_qp_path = os.path.join(self.data_dir, f"{prefix}_index_qp.faiss")

        with open(qa_path, "rb") as f:
            payload = pickle.load(f)
        self._items = payload["items"]
        self._stored_embedding_model_name = payload.get("embedding_model_name")
        # Model-agnostic query prefix (e.g. "query: " for e5). Empty for mpnet /
        # BGE-M3. Ingestion stores the matching passage prefix on the doc side.
        self._query_prefix = payload.get("query_prefix", "") or ""

        # Precompute per-LANGUAGE stem document frequency and smoothed IDF.
        # Each item is stemmed in its OWN language, so a shared multilingual
        # corpus still yields clean, language-correct anchor statistics. Common
        # words (high df, e.g. "hormone") get low weight automatically -- no
        # stopword/generic list needed. Accessors below key on the active query
        # language.
        df_by_lang: Dict[str, "Counter[str]"] = {}
        size_by_lang: Dict[str, int] = {}
        for it in self._items:
            lg = _norm_lang(it.get("lang", self.language))
            blob = f"{it.get('question','')} {it.get('section','')} {it.get('answer','')}"
            for para in (it.get("q_paraphrases") or []):
                blob += " " + str(para)
            d = df_by_lang.setdefault(lg, Counter())
            for s in _stem_set(_tokenize(blob), lg):  # each stem once per doc
                d[s] += 1
            size_by_lang[lg] = size_by_lang.get(lg, 0) + 1

        self._stats_by_lang = {}
        for lg, d in df_by_lang.items():
            size = max(1, size_by_lang.get(lg, 1))
            idf = {s: math.log((size + 1) / (c + 1)) + 1.0 for s, c in d.items()}
            self._stats_by_lang[lg] = {"df": dict(d), "idf": idf, "size": size}

        with open(bm25_path, "rb") as f:
            payload_bm25 = pickle.load(f)
        self._bm25 = payload_bm25["bm25"]

        self._index_q = faiss.read_index(idx_q_path)
        self._index_qa = faiss.read_index(idx_qa_path)

        if os.path.exists(idx_qp_path):
            try:
                self._index_qp = faiss.read_index(idx_qp_path)
            except Exception:
                self._index_qp = None
        else:
            self._index_qp = None

        self._embedder = SentenceTransformer(self.embedding_model_name)

        expected_dim = int(getattr(self._index_q, "d", -1))
        model_dim = int(self._embedder.get_sentence_embedding_dimension())
        if expected_dim > 0 and expected_dim != model_dim:
            hint = ""
            if self._stored_embedding_model_name:
                hint = (
                    f" (ingest used: '{self._stored_embedding_model_name}'). "
                    "Fix: re-run ingest_faq.py with the same --embedding-model as the chatbot, "
                    "or run the chatbot with --embedding-model set to the ingest model."
                )
            raise ValueError(
                f"Embedding dimension mismatch: FAISS index expects d={expected_dim} "
                f"but embedding model '{self.embedding_model_name}' outputs d={model_dim}.{hint}"
            )

        if self._index_qp is not None:
            qp_dim = int(getattr(self._index_qp, "d", -1))
            if qp_dim > 0 and qp_dim != model_dim:
                self._index_qp = None

        if self.rerank:
            try:
                from sentence_transformers import CrossEncoder
                self._cross_encoder = CrossEncoder(self.rerank_model)
            except Exception:
                self._cross_encoder = None

    def _encode(self, text: str) -> np.ndarray:
        assert self._embedder is not None
        emb = self._embedder.encode([text], convert_to_numpy=True).astype("float32")
        faiss.normalize_L2(emb)
        return emb

    # The query language is passed to every per-query method instead of being
    # stored on the retriever: one loaded retriever is shared by all GUI
    # sessions, so per-query state on it would leak between users.

    def _stats(self, language: str) -> Dict[str, Any]:
        """Corpus statistics for the given query language."""
        return self._stats_by_lang.get(language, {"df": {}, "idf": {}, "size": 1})

    def corpus_size(self, language: str) -> int:
        return self._stats(language)["size"]

    def df(self, stem: str, language: str) -> int:
        """Document frequency of a stem (max over its synonym group)."""
        d = self._stats(language)["df"]
        acceptable = _concept_match_stems(stem, language)
        return max((d.get(a, 0) for a in acceptable), default=0)

    def idf(self, stem: str, language: str) -> float:
        """Smoothed IDF of a stem (min over its synonym group; 0.0 if absent)."""
        idf_map = self._stats(language)["idf"]
        acceptable = _concept_match_stems(stem, language)
        vals = [idf_map[a] for a in acceptable if a in idf_map]
        return min(vals) if vals else 0.0

    def retrieve(
        self,
        user_query: str,
        language: Optional[str] = None,
        timing: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievalCandidate]:
        """Hybrid retrieval for one query. `language` defaults to the index
        language; if a `timing` dict is given, it receives the per-stage
        latency breakdown (retrieve / rerank ms, n_reranked)."""
        lang = _norm_lang(language) if language else self.language
        if timing is None:
            timing = {}
        timing.update({"retrieve": 0.0, "rerank": 0.0, "n_reranked": 0})
        if not self._items:
            return []

        assert self._bm25 is not None
        assert self._index_q is not None
        assert self._index_qa is not None

        _t_retrieve = time.perf_counter()
        bm25_scores = self._bm25.get_scores(_tokenize(user_query))
        bm25_ranked = np.argsort(-bm25_scores)[: self.top_k]

        # The three dense indexes are queried with the same encoded vector; only
        # the document side differs, so encode once (was encoded three times).
        q_emb = self._encode(f"{self._query_prefix}Question: {user_query}")
        Dq, Iq = self._index_q.search(q_emb, self.top_k)
        Dqa, Iqa = self._index_qa.search(q_emb, self.top_k)

        Iqp = None
        Dqp = None
        if self._index_qp is not None:
            try:
                Dqp, Iqp = self._index_qp.search(q_emb, self.top_k)
            except Exception:
                Iqp = None
                Dqp = None

        def rrf(rank: int, k: int = 60) -> float:
            return 1.0 / (k + rank)

        fused: Dict[int, float] = {}
        # Track the best cosine similarity seen for each item across dense indexes
        # (IndexFlatIP on L2-normalized vectors -> inner product == cosine).
        dense_sim: Dict[int, float] = {}

        def _note_dense(D, I):
            if D is None or I is None:
                return
            for sim, idx in zip(D[0].tolist(), I[0].tolist()):
                if idx >= 0:
                    dense_sim[int(idx)] = max(dense_sim.get(int(idx), -1.0), float(sim))

        _note_dense(Dq, Iq)
        _note_dense(Dqa, Iqa)
        _note_dense(Dqp, Iqp)

        for r, idx in enumerate(bm25_ranked.tolist()):
            fused[int(idx)] = fused.get(int(idx), 0.0) + rrf(r)
        for r, idx in enumerate(Iq[0].tolist()):
            if idx >= 0:
                fused[int(idx)] = fused.get(int(idx), 0.0) + rrf(r)
        for r, idx in enumerate(Iqa[0].tolist()):
            if idx >= 0:
                fused[int(idx)] = fused.get(int(idx), 0.0) + rrf(r)
        if Iqp is not None:
            for r, idx in enumerate(Iqp[0].tolist()):
                if idx >= 0:
                    fused[int(idx)] = fused.get(int(idx), 0.0) + rrf(r)

        ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)[: self.top_k]

        candidates: List[RetrievalCandidate] = []
        for idx, score in ranked:
            it = self._items[int(idx)]
            question = str(it.get("question", ""))
            # Runtime artifact filter: drop answer-fragments mis-parsed as
            # questions in the prebuilt indexes (see _looks_like_faq_question).
            # Only applies to FAQ items -- article "questions" are heading
            # breadcrumbs and are not expected to be well-formed questions.
            source_type = str(it.get("source_type", "faq"))
            if source_type == "faq" and not _looks_like_faq_question(question):
                continue
            candidates.append(
                RetrievalCandidate(
                    index=int(idx),
                    question=question,
                    section=str(it.get("section", "")),
                    answer=str(it.get("answer", "")),
                    fused_score=float(score),
                    dense_sim=(dense_sim.get(int(idx)) if int(idx) in dense_sim else None),
                    lang=_norm_lang(str(it.get("lang", lang))),
                    source_type=source_type,
                    source_id=str(it.get("source_id", "")),
                    heading_path=str(it.get("heading_path", "")),
                )
            )

        # Embedding + BM25 + FAISS search + fusion are done; the rest is reranking.
        timing["retrieve"] = (time.perf_counter() - _t_retrieve) * 1000.0

        if self._cross_encoder is not None and len(candidates) >= 2:
            # Rerank only a SHORTLIST of the best fused candidates, not the whole
            # top_k pool. Cross-encoder cost is linear in the number of pairs, and
            # a large reranker (e.g. bge-reranker-v2-m3) over 40 pairs is the main
            # per-query latency. `candidates` is already sorted by fused score, so
            # the top `rerank_top_n` are the strongest hybrid hits; the reranked
            # shortlist is returned and the weaker tail is dropped.
            shortlist = candidates[: self.rerank_top_n]
            pairs = [(user_query, f"{c.section}\n{c.question}\n{c.answer}") for c in shortlist]
            _t_rerank = time.perf_counter()
            try:
                ce_scores = self._cross_encoder.predict(pairs)
                for c, s in zip(shortlist, ce_scores):
                    c.rerank_score = float(s)
                shortlist.sort(
                    key=lambda c: c.rerank_score if c.rerank_score is not None else -1e9,
                    reverse=True,
                )
                candidates = shortlist
                timing["n_reranked"] = len(pairs)
            except Exception:
                pass
            timing["rerank"] = (time.perf_counter() - _t_rerank) * 1000.0

        return candidates
