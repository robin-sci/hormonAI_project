# AGENTS.md

## AI Agent Guidelines for hormonAI Development

This document provides guidance for AI coding assistants (such as Claude, GitHub Copilot, Cursor, or similar tools) working on the hormonAI codebase. It outlines the project's architecture, design principles, and best practices to ensure consistency and quality.

---

## Project Overview

**hormonAI** is a Retrieval-Augmented Generation (RAG) chatbot designed to answer questions about adjuvant hormone therapy for breast cancer. In the chat interface the assistant is presented as **Mona**. The system is built with safety, transparency, and medical accuracy as core priorities.

### Key Characteristics

- **Domain-restricted**: Only answers from a curated knowledge base (FAQ Q/A pairs **and** reference articles)
- **Bilingual**: English and French in one shared multilingual embedding space; same-language answers are preferred, with a cross-lingual fallback that is clearly labeled and never machine-translated
- **Hybrid retrieval**: Combines dense semantic search (FAISS) with keyword search (BM25), fused with RRF, then CrossEncoder reranking (on by default)
- **Safety-first**: Semantic-first answer/abstain gate; declines out-of-scope questions gracefully
- **Source transparency**: Every answer shows its knowledge-base origin, kept out of the answer body
- **Optional LLM rephrasing**: A local Ollama model can rephrase ONLY the retrieved text; otherwise the source text is returned verbatim

---

## Architecture Components

### Core Modules

1. **ingest.py**: Current, type-aware ingestion (FAQ + articles)
   - Reads a JSON manifest (`manifest.json`) tagging each source's `type` (`faq`/`article`) and `lang`, or `--faq` / `--article` paths
   - **FAQ** `.docx`: parsed into atomic Q/A pairs (one chunk per question)
   - **Articles** (`.docx`, `.md`, `.txt`, `.pdf`): split on their own headings, then into overlapping child chunks (`--chunk-size` 250 / `--chunk-overlap` 40 words) with a heading breadcrumb and parent link. PDFs are extracted with PyMuPDF (fallback `pypdf`) and cleaned
   - Emits one unified item schema (`id`, `source_id`, `source_type`, `lang`, `section`, `heading_path`, `question`, `answer`, `parent_id`, `parent_text`, `q_paraphrases`)
   - Builds a combined index (`kb_all_*`, `--shared`) and per-language indexes (`kb_{lang}_*`, `--per-language`); both on by default
   - Embedding-model-agnostic (`--embedding-model`); `--passage-prefix` / `--query-prefix` for models like e5 (the query prefix is stored and used at query time)

2. **ingest_faq.py**: Legacy FAQ-only ingestion (still supported)
   - Writes `faq_{lang}_*` files by default
   - Optional offline question paraphrasing via Ollama (`--augment-questions`) for the paraphrase index

3. **rag_core.py**: Core RAG logic
   - `HybridFAQRetriever`: four-channel retrieval with RRF fusion, optional CrossEncoder reranking, per-language IDF statistics
   - `extract_anchor_concepts()`: IDF-weighted lexical anchors (no hand-maintained stopword lists)
   - `answer_query()`: semantic-first answer/abstain decision, bundle selection, cross-lingual fallback, optional LLM rephrasing; returns an `AnswerResult`
   - `LLMWrapperWriter`: Ollama client (`/api/generate`) for grounded rephrasing; records `last_error` so fallbacks are surfaced
   - `build_abstain()`: language-specific refusal text

4. **chatbot.py**: Command-line interface
   - Interactive REPL-style chatbot; `--debug` prints retrieval/decision details

5. **hormonai_app.py**: Streamlit GUI
   - User-friendly web interface ("Mona"), with sample prompts
   - Language switching, LLM toggle, reranking options
   - Language scope: combined index with cross-lingual fallback, or query-language corpus only (`--retrieval-scope`; operator-only, defaults to `shared` in the GUI)
   - Accepts the same launch arguments as the CLI (Streamlit passthrough after `--`)
   - Conversation history; sources shown in a "Sources used for this answer" panel (kept out of the answer body)

6. **audit_logger.py**: Query logging system
   - Appends JSONL events (default `logs/audit.jsonl`): query, language, answered, used_llm, source, rounded `timing_ms`, meta

7. **tools/latency_report.py**: p50/p95/p99 latency from the audit log

---

## Retrieval Architecture

> **Models run locally.** Embeddings (`SentenceTransformer`) and the reranker
> (`CrossEncoder`) execute in-process via `sentence-transformers`/PyTorch; there
> is no external inference API. The model setting accepts a Hugging Face id or a
> local directory path (set `HF_HUB_OFFLINE=1` for fully offline use). The
> optional LLM (`--use-llm`) runs in a local Ollama server.

Defaults:
- Embedding model: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` (`HORMONAI_EMBEDDING_MODEL`); must match the model used at ingestion
- Reranker: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (`HORMONAI_RERANK_MODEL`; `BAAI/bge-reranker-v2-m3` recommended)

### Four-Channel Hybrid Retrieval

Each channel returns its top `top_k` (default 40) candidates. Every item is a FAQ Q/A pair or an article chunk in the same schema, so all channels cover the whole knowledge base:

1. **BM25 (keyword-based)**: Over the tokenized full text (section/heading + question/title + answer/body)
2. **FAISS "topic" index** (`index_q`): FAQ question, or article heading + leading chunk text as a topic proxy
3. **FAISS "topic+paraphrases" index** (`index_qp`): Topic augmented with question paraphrases when present (equals the topic index otherwise)
4. **FAISS "full" index** (`index_qa`): Question + answer, or heading + full chunk body

The three dense channels share one encoded query vector.

### Scoring System

- **Fused Score** (`fused_score`): Reciprocal Rank Fusion (RRF) across all channels
  - Formula: `rrf(rank) = 1 / (60 + rank)`
  - Not a similarity score; used for relative ordering
- **Dense similarity** (`dense_sim`): Best cosine similarity across the FAISS channels; used by the gate when reranking is off

- **Rerank Score** (`rerank_score`, on by default; `--no-rerank` to disable): CrossEncoder second-pass reranking
  - Scores `(query, section + question + answer)` pairs
  - Overrides the fused ordering when enabled
  - Reranks only the top-N fused candidates for latency (`--rerank-top-n` / `HORMONAI_RERANK_TOP_N`; CLI default 5, retriever default 20)
  - Loads lazily and degrades gracefully if unavailable

### Answer / Abstain Decision (semantic-first)

`answer_query()` accepts if EITHER:

1. **Primary**: the top candidate's relevance clears its threshold — `rerank_score >= --rerank-threshold` (default -1.0) when reranking is on, else `dense_sim >= --sem-threshold` (default 0.62)
2. **Lexical safety net**: a candidate covers a high-IDF query anchor and is at least `--dense-floor` (default 0.50) cosine-similar

Additional behavior:
- IDF anchors no longer gate the answer; they shape multi-concept bundles (up to 3 sources) and provide the safety net
- Statistics-intent queries must pass an extra stats gate (the source must contain numbers/percentages for the asked concept)
- In shared mode, the decision runs on same-language candidates first, then on cross-language candidates as a fallback, which adds an "only available in <language>" notice
- Thresholds are model-specific and must be calibrated on `tests/eval_set.jsonl`; watch the false-ANSWER rate

See `RETRIEVAL_REVIEW.md` for the full design and change log.

---

## Design Principles

### 1. Safety and Medical Ethics

- **Never hallucinate**: Strictly answer from the knowledge base only
- **Graceful refusal**: Decline out-of-scope questions politely
- **Transparency**: Always show sources
- **Language-appropriate**: Match the user's language; never machine-translate source content
- **Compassionate wording**: Mortality phrasing is reframed as survival language (`_reframe_survival`) without changing meaning

### 2. Code Quality Standards

- **Type hints**: Use Python type annotations for all functions
- **Docstrings**: Document all classes and public methods
- **Error handling**: Graceful degradation, never crash
- **Logging**: Use the audit logger / Python logging rather than ad-hoc prints in library code
- **Configuration**: Avoid hardcoded values; use CLI flags with `HORMONAI_*` env-var defaults

### 3. Modularity

- Keep RAG logic separate from UI (CLI vs Streamlit)
- Single responsibility principle for each module
- Testable components with clear interfaces

---

## Development Guidelines

### Adding New Features

When adding functionality:

1. **Consider both interfaces**: Ensure CLI and Streamlit parity (the GUI parses the same launch arguments)
2. **Update both languages**: Maintain English/French support
3. **Preserve safety**: Never bypass the knowledge-base-only restriction
4. **Add tests**: Add eval cases to `tests/eval_set.jsonl` and/or scripts in `/tests/`
5. **Update documentation**: Modify README.md, RETRIEVAL_REVIEW.md (retrieval changes) and this file

### Modifying Retrieval Logic

When changing `rag_core.py`:

- Maintain backward compatibility with existing indexes (`kb_*` and legacy `faq_*`)
- Consider impact on both scoring paths (dense vs rerank)
- Re-run `tests/eval_retrieval.py` for both languages and both retrieval scopes
- Document scoring behavior changes
- Preserve the citation/sources mechanism

### Adding New Dependencies

Before adding a new package:

1. Verify it's necessary and well-maintained
2. Check license compatibility (project is MIT)
3. Add to `requirements.txt` with version pinning
4. Test installation in clean environment
5. Document usage in README if user-facing

---

## File Structure Conventions

### Data Directory (`/data/`)

Generated by `ingest.py` (`<prefix>` defaults to `kb`; `<scope>` is `all` for the combined index or a language code):

```
kb_{scope}_index_q.faiss      # FAISS "topic" index
kb_{scope}_index_qp.faiss     # FAISS "topic+paraphrases" index
kb_{scope}_index_qa.faiss     # FAISS "full" (question+answer) index
kb_{scope}_qa.pkl             # Items + metadata (embedding model, query prefix)
kb_{scope}_bm25.pkl           # BM25 index
```

The legacy `ingest_faq.py` writes the same suffixes with a `faq_{lang}` prefix.

Note: `data/` is currently tracked in git (not in `.gitignore`). Rebuild and commit indexes together with any corpus or embedding-model change.

### Corpus Directory (`/corpus/`)

Source documents, organized by language (`corpus/en/`, `corpus/fr/`) and referenced from `manifest.json`. Ignored by git (local, potentially third-party material).

### Logs Directory (`/logs/`)

- JSONL audit log, default `logs/audit.jsonl` (`--audit-log`, `HORMONAI_AUDIT_LOG` for the latency report)
- `query` events: query, language, answered, used_llm, source index/question, `timing_ms`, meta
- Optional PHI-free `latency` events from the GUI (`HORMONAI_AUDIT_LATENCY=1`)
- Listed in `.gitignore`; logs can contain patient questions and must never be committed

---

## Testing Strategy

### Current Test Files

- `tests/eval_set.jsonl`: Gold eval cases (EN + FR, categorized, with `expected_answerable` and `gold_ids`)
- `tests/eval_retrieval.py`: Runs the gold set — recall@k, false-answer and false-abstention rates
- `tests/pdf_fidelity.py`: PDF extraction QA (per-source metrics + preview)
- `tests/test_snapshot.py`: Snapshot of every patient-visible pipeline output across seven configurations (`tests/snapshots/pipeline.json`); run with `python -m pytest tests/`
- `tests/test_smoke.py`: CLI and Streamlit GUI end-to-end smoke tests
- `tests/fakes.py`: Deterministic stand-in embedder, reranker and Ollama, so tests need no model downloads

Any refactor must keep `python -m pytest tests/` green without regenerating the snapshot. A change that is meant to alter answers regenerates it (`UPDATE_SNAPSHOT=1`) and the diff is reviewed.

### When Adding Tests

- Test both languages separately
- Test edge cases (empty queries, very long queries)
- Test safety gates (out-of-scope questions should abstain)
- Test retrieval accuracy with known Q/A pairs (`gold_ids`)
- Mock LLM calls when appropriate

---

## LLM Integration Notes

### Current LLM Support

- **Ollama** (local) is the only LLM backend
  - Model: `llama3.2` (default; `--llm-model` / `HORMONAI_LLM_MODEL`)
  - Endpoint: `OLLAMA_HOST` (default `http://localhost:11434`), `/api/generate`
  - Answer time: grounded rephrasing of the retrieved text, only for answered queries, only with `--use-llm` / the GUI toggle
  - Ingestion time (legacy `ingest_faq.py --augment-questions`): question paraphrases for the `qp` index

### LLM Usage Guidelines

When working with LLM components:

1. **Always make LLM optional**: System must work without LLM
2. **Graceful fallback**: Return verbatim source text if the LLM fails, and surface why (`llm_status`, `last_error`)
3. **Safety prompts**: Use ONLY the source text; add no facts, figures, drugs or dosages
4. **Token limits**: Keep `num_predict` bounded (rephrase default 400)
5. **Post-processing**: Keep `_strip_llm_preamble` and `_reframe_survival` applied to LLM output

### Prompt Engineering

The rephrase system prompt (`LLMWrapperWriter._rephrase_system_prompt`, EN and FR) requires:

```
- Use ONLY information in the SOURCE TEXT; add no facts
- Answer the question directly and generally
- Keep every safety caveat / condition from the source
- Gentle, non-alarming tone
- Survival framing (never "death/dying" about the patient), same meaning and certainty
- Do not overstate benefits or give false reassurance
- If the source does not answer the question, say so
```

When modifying prompts:
- Maintain safety constraints
- Test with edge cases
- Keep sources out of the answer body
- Keep the EN and FR prompts aligned

---

## Language Support

### Adding a New Language

To add support for a new language:

1. **Documents**: Obtain FAQ / articles in that language and add them to `manifest.json` with the new `lang`
2. **Ingest**: Run `ingest.py --manifest manifest.json` (extend the `--language` choices as needed)
3. **Embedding Model**: Verify multilingual support
4. **Stemming / anchors**: Add stemming support in `rag_core.py` (`_stem`) and language-specific strings (abstain text, notices, prompts)
5. **UI Strings**: Add translations to both CLI and Streamlit
6. **Testing**: Add eval cases to `tests/eval_set.jsonl`
7. **Documentation**: Update README with the new language

### Language-Specific Considerations

- **Tokenization / stemming**: Snowball stemmer with built-in fallbacks for EN/FR
- **Anchors**: IDF statistics are computed per language, so no stop-word lists are needed
- **Embedding models**: Use multilingual models so the shared index works
- **UI text**: Keep all user-facing strings translatable

---

## Common Tasks for AI Agents

### Task: Improve Retrieval Accuracy

```python
# Locations to modify:
# - rag_core.py: HybridFAQRetriever.retrieve(), _decide_bundle(), answer_query()
# - Tune top_k / rerank_top_n, thresholds (sem/rerank/dense-floor)
# - Try other embedding / reranker models (re-ingest + re-calibrate)
# - Measure with tests/eval_retrieval.py (both languages, both scopes)
```

### Task: Add Conversation Memory

```python
# Implementation approach:
# 1. Extend chatbot.py and hormonai_app.py history tracking (GUI already keeps display history)
# 2. Modify answer_query to accept conversation context
# 3. Update prompts to use context appropriately
# 4. Maintain safety: don't allow context to override the knowledge-base restriction
# 5. Add a memory limit to prevent token overflow
```

### Task: Improve LLM Response Quality

```python
# Tuning locations:
# - rag_core.py: LLMWrapperWriter._rephrase_system_prompt() / rephrase()
# - Adjust temperature (default 0.6) and num_predict
# - Keep _strip_llm_preamble / _reframe_survival post-processing
# - Test tone and empathy with medical stakeholders
```

### Task: Add New Retrieval Channel

```python
# Steps:
# 1. Modify ingest.py to build the new index
# 2. Update HybridFAQRetriever.load() / retrieve() to include the channel
# 3. Add its ranking to the RRF fusion
# 4. Measure impact with tests/eval_retrieval.py
# 5. Update README "Scoring" and RETRIEVAL_REVIEW.md
```

---

## Debugging Tips

### Common Issues

**Issue**: Retrieval returns irrelevant results
- Check that the query-time embedding model matches the one used at ingestion
- Verify BM25 tokenization
- Inspect candidates and the decision path with `--debug`
- Review top-k values and thresholds

**Issue**: Too many abstentions / false answers
- Thresholds are model-specific; re-calibrate on the gold set after changing models
- Check whether reranking is on (rerank threshold) or off (dense threshold)

**Issue**: LLM output is off-topic or missing
- Review the rephrase prompt constraints
- Check that source text is passed to `rephrase()`
- Check `llm_status` / `llm_error` in debug output (Ollama unreachable → verbatim fallback)
- Test without `--use-llm` to isolate the problem

**Issue**: Language switching not working
- Verify the `kb_{lang}_*` / `kb_all_*` files exist
- Check the retrieval scope (`--retrieval-scope shared|language`)
- Ensure the documents were ingested with the correct `lang`

**Issue**: FAISS index errors
- Rebuild indexes: re-run `ingest.py`
- Check FAISS version compatibility
- Verify embedding dimensions match

---

## Performance Considerations

### Optimization Priorities

1. **Retrieval speed**: Keep top-k and `rerank_top_n` low; the query is encoded once for all dense channels
2. **Memory usage**: Stream large files, manage index sizes
3. **LLM latency**: Rephrasing is optional and only runs for answered queries
4. **Startup time**: Lazy-load models (the CrossEncoder loads lazily), cache indexes

### Benchmarking

- `answer_query` records a per-stage timing breakdown (`timing_ms`), shown with `--debug` / `HORMONAI_SHOW_TIMING=1`
- `tools/latency_report.py` reports p50/p95/p99 from the audit log

---

## Security and Privacy

### Data Handling

- **No PII collection**: Don't log personally identifiable information
- **Latency logging**: Never includes the raw patient query
- **Secure secrets**: Use environment variables, never commit keys
- **HTTPS only**: Enforce secure connections for production deployment

### Medical Compliance

- **Not medical advice disclaimer**: Include in UI
- **Source citation**: Always provide knowledge-base references
- **No diagnosis**: Explicitly avoid diagnostic language
- **Encourage consultation**: Suggest speaking with healthcare providers

---

## Deployment Notes

### Pre-Deployment Checklist

- [ ] Eval set passing at acceptable recall / false-answer rates
- [ ] Knowledge-base documents up to date
- [ ] Indexes rebuilt with the latest documents and the deployed embedding model
- [ ] Thresholds calibrated for the deployed models
- [ ] Environment variables configured
- [ ] Logging configured
- [ ] Medical disclaimer visible
- [ ] Language support verified

### Environment Variables

```bash
# Models
HORMONAI_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-mpnet-base-v2
HORMONAI_RERANK_MODEL=cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
HORMONAI_RERANK_TOP_N=5
HF_HUB_OFFLINE=1                 # optional: fully offline model loading

# Retrieval scope and gate thresholds
HORMONAI_RETRIEVAL_SCOPE=shared  # or: language
HORMONAI_SEM_THRESHOLD=0.62
HORMONAI_RERANK_THRESHOLD=-1.0
HORMONAI_DENSE_FLOOR=0.50

# Optional LLM (Ollama)
HORMONAI_LLM_MODEL=llama3.2
OLLAMA_HOST=http://localhost:11434

# Instrumentation
HORMONAI_SHOW_TIMING=1           # GUI per-query latency breakdown
HORMONAI_AUDIT_LATENCY=1         # GUI PHI-free latency logging
HORMONAI_AUDIT_LOG=logs/audit.jsonl  # used by tools/latency_report.py
```

---

## Contributing

### Code Review Criteria

When reviewing changes:

1. **Safety**: Does it maintain the knowledge-base-only restriction?
2. **Accuracy**: Does it preserve the sources mechanism?
3. **Usability**: Is it user-friendly for both languages?
4. **Performance**: Does it impact response time?
5. **Testing**: Are there adequate tests / eval cases?
6. **Documentation**: Is it documented?

### AI Agent Self-Review

Before submitting changes, verify:

- [ ] Code follows project conventions
- [ ] Type hints are present
- [ ] Docstrings are clear
- [ ] No hardcoded paths or credentials
- [ ] Both languages work
- [ ] Eval passes
- [ ] README updated if needed
- [ ] No sensitive data in commits

---

## Resources

### Key Dependencies

- **sentence-transformers**: Embeddings and CrossEncoder reranking
- **faiss-cpu**: Vector similarity search
- **rank-bm25**: Keyword-based retrieval
- **streamlit**: Web UI framework
- **python-docx**: DOCX parsing
- **PyMuPDF / pypdf**: PDF text extraction

### Useful Links

- [Sentence Transformers Documentation](https://www.sbert.net/)
- [FAISS Wiki](https://github.com/facebookresearch/faiss/wiki)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [Ollama](https://ollama.com/)
- [Reciprocal Rank Fusion Paper](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)

---

## Changelog

When making significant changes, document them here:

### [Unreleased]

- Type-aware ingestion (`ingest.py`): FAQ + articles (docx/md/txt/pdf) in one `kb_*` index
- Shared multilingual index with same-language preference and labeled cross-lingual fallback
- Semantic-first answer/abstain gate with IDF-weighted anchors
- Reranking on by default; configurable reranker and `rerank_top_n`
- Retrieval scope option (`--retrieval-scope`)
- Grounded LLM rephrasing via local Ollama with surfaced fallback
- Gold eval set and evaluation harness; latency instrumentation and report

### Version 1.0

- Initial release
- Hybrid retrieval with RRF fusion
- Bilingual support (EN/FR)
- CLI and Streamlit interfaces
- Optional LLM rephrasing
- Optional CrossEncoder reranking

---

## Contact

For questions about this codebase or suggestions for improvement, please open an issue on GitHub.

---

*Last updated: 2026-10-15*
