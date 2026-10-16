"""Answer/abstain decision, answer formatting and compassionate wording.

answer_query() is the single entry point used by the CLI, GUI and eval."""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from hormonai.llm import LLMWrapperWriter
from hormonai.retrieval import HybridFAQRetriever, RetrievalCandidate
from hormonai.text import (
    STATS_BROAD_CONCEPTS_EN,
    STATS_BROAD_CONCEPTS_FR,
    STATS_GROUND_HINTS_EN,
    STATS_GROUND_HINTS_FR,
    STATS_INTENT_HINTS_EN,
    STATS_INTENT_HINTS_FR,
    _anchor_overlap_concepts,
    _has_number_or_percent,
    _is_stats_intent,
    _norm_lang,
    _stem,
    _stem_set,
    _tokenize,
    extract_anchor_concepts,
)


@dataclass
class AnswerResult:
    answered: bool
    answer_text: str
    source_title: Optional[str] = None
    source_index: Optional[int] = None
    source_indices: Optional[List[int]] = None   # positional indices of every bundled source
    sources_text: Optional[str] = None            # formatted citations, kept OUT of answer_text
    timing_ms: Optional[Dict[str, Any]] = None    # per-query latency breakdown (always populated)
    # LLM rephrasing outcome, so callers can surface a silent fallback:
    #   None                  -> LLM rephrasing not requested (use_llm=False)
    #   "used"                -> LLM rephrased the answer
    #   "fallback_unreachable"-> LLM requested but unreachable; showed verbatim
    #   "fallback_empty"      -> LLM reachable but returned nothing; showed verbatim
    llm_status: Optional[str] = None
    llm_error: Optional[str] = None               # connection/HTTP error detail, when unreachable
    debug: Optional[Dict[str, Any]] = None


# ---------------------------
# Formatting functions
# ---------------------------

def _candidate_title(c: RetrievalCandidate) -> str:
    """A display heading for a bundle entry. FAQ -> the question; article -> its
    source document / section heading (never the fake 'question' breadcrumb)."""
    if c.source_type == "faq":
        return (c.question or "").strip()
    hp = (c.heading_path or "").strip()
    src = (c.source_id or "").strip()
    if hp and src and hp != src:
        return f"{src} — {hp}"
    return hp or src or (c.section or "").strip()


def _format_bundle_body(bundle: List[RetrievalCandidate]) -> str:
    if not bundle:
        return ""
    parts: List[str] = []
    for c in bundle:
        parts.append(f"**{_candidate_title(c)}**\n{c.answer.strip()}")
    return "\n\n".join(parts).strip()


def _format_preface(language: str) -> str:
    lang = _norm_lang(language)
    if lang == "fr":
        return "**Voici les informations disponibles sur ce sujet :**\n\n"
    return "**Here is the available information on this topic:**\n\n"


def _format_sources(language: str, bundle: List[RetrievalCandidate]) -> str:
    lang = _norm_lang(language)
    lines: List[str] = []
    label = "Source :" if lang == "fr" else "Source:"
    sec_label = "section :" if lang == "fr" else "section:"
    for c in bundle:
        if c.source_type == "faq":
            lines.append(f"**— {label}** “{c.question}” ({sec_label} {c.section})")
        else:
            # Article: cite the source document (+ section heading when it adds
            # information), not the "question" breadcrumb.
            src = (c.source_id or c.section or "").strip()
            hp = (c.heading_path or "").strip()
            cite = f"{src} — {hp}" if (hp and src and hp != src) else src
            lines.append(f"**— {label}** {cite}")
    return "\n\n".join(lines).strip()


def _bundle_source_text(bundle: List[RetrievalCandidate]) -> str:
    """Verbatim source text handed to the LLM for grounded rephrasing. FAQ items
    keep their question as a mini-heading; article chunks (whose 'question' is a
    filename breadcrumb) contribute their body only."""
    parts: List[str] = []
    for c in bundle:
        q = (c.question or "").strip()
        a = (c.answer or "").strip()
        if q.endswith("?"):
            parts.append(f"{q}\n{a}")
        else:
            parts.append(a)
    return "\n\n".join(p for p in parts if p).strip()


# ---------------------------
# Compassionate survival reframing
# ---------------------------
#
# Patient-facing answers must not describe the person's own outcome with the
# words "death"/"dying" (or FR "mort"/"mourir"/"décès"). It is fine, and often
# more accurate, to speak of SURVIVAL instead. The source corpus itself uses
# mortality phrasing (e.g. NCI: "lower your risk of ... and of dying from breast
# cancer"), so a grounded rephrase or verbatim quote will echo it unless we
# reframe deterministically here -- a prompt alone is not reliable with a small
# local model.
#
# IMPORTANT: the patterns are NARROW on purpose. They match only patient-
# mortality constructions (".. dying/death FROM breast cancer/the cancer/it",
# ".. risk/chance of dying .."). They deliberately do NOT touch statements about
# cancer CELLS dying ("the cells may die", "la mort des cellules cancéreuses"),
# which are accurate, desirable, and not distressing.

_SURVIVAL_REFRAMES_EN: List[Tuple[str, str]] = [
    # "the risk of (you) dying [from ...]" -> threat-to-survival framing
    (r"\bthe risk of (?:you |your )?dying(?: from (?:breast cancer|the cancer|it))?\b",
     "the risk to your long-term survival"),
    # "risk/chance/likelihood of dying [from ...]"
    (r"\b(?:risk|chance|chances|likelihood) of dying(?: from (?:breast cancer|the cancer|it))?\b",
     "risk to long-term survival"),
    # "risk/chance of death from ..."
    (r"\b(?:risk|chance|chances|likelihood) of death(?: from (?:breast cancer|the cancer|it))?\b",
     "risk to long-term survival"),
    # list/conjunction context: "..., as well as / and (of) dying from ..."
    (r"\s*,?\s*(?:as well as|and)\s+(?:of\s+)?dying from (?:breast cancer|the cancer|it)\b",
     ", as well as improving long-term survival"),
    # any remaining "dying/death from <cancer/it>"
    (r"\bdying from (?:breast cancer|the cancer|it)\b", "affecting long-term survival"),
    (r"\bdeath from (?:breast cancer|the cancer|it)\b", "long-term survival"),
]

_SURVIVAL_REFRAMES_FR: List[Tuple[str, str]] = [
    # "réduire/diminuer (le risque de) mortalité du/par cancer du sein" -> survie
    (r"\b(réduire|réduit|diminuer|diminue|abaisser|abaisse|baisser)\s+(?:la\s+|le\s+)?"
     r"(?:risque de\s+)?mortalité\s+(?:du|par)\s+cancer du sein\b",
     r"améliorer la survie au cancer du sein"),
    (r"\bla mortalité\s+(?:du|par)\s+cancer du sein\b", "la survie au cancer du sein"),
    # "risque de décès / de mourir [du cancer du sein / de la maladie]"
    (r"\brisque de (?:décès|mourir)(?:\s+(?:du|par)\s+cancer du sein|\s+de la maladie)?\b",
     "risque pour la survie à long terme"),
    # "mourir du cancer du sein / de la maladie" and "en mourir"
    (r"\bmourir\s+(?:du cancer du sein|de la maladie)\b", "pour la survie à long terme"),
    (r"\ben mourir\b", "pour la survie à long terme"),
]


def _reframe_survival(text: str, language: str) -> str:
    """Rewrite patient-mortality phrasing into survival language, in place.

    Deterministic and narrowly scoped so accurate cancer-cell-death statements
    are preserved. Applied to the final patient-facing answer (both the grounded
    LLM rephrase and the verbatim path), never to the cited source snippets in
    the Sources dropdown (those stay verbatim for verifiability)."""
    if not text:
        return text
    is_fr = _norm_lang(language) == "fr"
    rules = _SURVIVAL_REFRAMES_FR if is_fr else _SURVIVAL_REFRAMES_EN
    out = text
    for pattern, repl in rules:
        out = re.sub(pattern, repl, out, flags=re.IGNORECASE)
    if is_fr:
        # Restore French elision broken by a substitution starting with a vowel
        # (e.g. "de améliorer" -> "d'améliorer", "que améliorer" -> "qu'améliorer").
        out = re.sub(r"\b([dlncjmts])e améliorer\b", r"\1'améliorer", out, flags=re.IGNORECASE)
        out = re.sub(r"\bque améliorer\b", "qu'améliorer", out, flags=re.IGNORECASE)
    # Tidy artifacts a substitution can leave behind (", ," or doubled spaces).
    out = re.sub(r"\s+,", ",", out)
    out = re.sub(r",\s*,", ",", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out


# ---------------------------
# Empathy + LLM wrapper
# ---------------------------

_EMPATHY_BANK_EN = [
    "Thank you for sharing that — it’s completely understandable to want reassurance.",
    "I hear you. It’s very reasonable to be thinking about this.",
    "It makes sense to want clear, reliable guidance about your health.",
    "You’re not alone in asking this — it’s a valid concern.",
    "It’s understandable to want straightforward information, especially with everything you’re managing.",
]

_EMPATHY_BANK_FR = [
    "Merci de le partager — c’est tout à fait normal de vouloir être rassuré(e).",
    "Je vous comprends. C’est une inquiétude très légitime.",
    "C’est normal de vouloir une information claire et fiable sur votre santé.",
    "Vous n’êtes pas seul(e) à vous poser la question — c’est une préoccupation valable.",
    "C’est compréhensible de vouloir une réponse simple et fiable, surtout avec tout ce que vous traversez.",
]


def _stable_choice(items: List[str], key: str) -> str:
    if not items:
        return ""
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    idx = int(h[:8], 16) % len(items)
    return items[idx]


def _fallback_empathy(language: str, user_query: str, top_question: str) -> str:
    lang = _norm_lang(language)
    key = f"{lang}::{user_query.strip().lower()}::{top_question.strip().lower()}"
    bank = _EMPATHY_BANK_FR if lang == "fr" else _EMPATHY_BANK_EN
    s = _stable_choice(bank, key)
    return (s.strip() + "\n\n") if s else ""


# ---------------------------
# Abstain
# ---------------------------

def build_abstain(language: str) -> str:
    lang = _norm_lang(language)
    if lang == "fr":
        return (
            "Je comprends votre question. Cependant, les informations sur lesquelles je m’appuie ne semblent pas "
            "contenir d’information spécifique sur ce sujet. Pour éviter d’inventer des informations médicales, "
            "je ne peux pas répondre à partir de ces sources.\n\n"
            "Je vous recommande d’en parler avec votre équipe d’oncologie."
        )
    return (
        "I understand why you’re asking. However, the information I have does not appear to contain specific "
        "information about this topic. To avoid inventing medical information, I can’t answer this from my sources.\n\n"
        "Please discuss this with your oncology team."
    )


# ---------------------------
# Scoring + selection
# ---------------------------

def _score_candidate(c: RetrievalCandidate) -> float:
    return float(c.rerank_score) if c.rerank_score is not None else float(c.fused_score)


def _select_bundle_with_coverage(
    candidates: List[RetrievalCandidate],
    language: str,
    anchor_concepts: Set[str],
    max_n: int = 3,
) -> Tuple[List[RetrievalCandidate], Dict[str, Any]]:
    """
    Greedily build a bundle that covers as many anchor concepts as possible.

    The first (lead) member is the highest-scoring candidate that covers
    anything; each further member must cover at least one new concept.
    """
    lang = _norm_lang(language)
    ranked = sorted(candidates, key=_score_candidate, reverse=True)

    covered: Set[str] = set()
    bundle: List[RetrievalCandidate] = []
    per_candidate_covered: List[Dict[str, Any]] = []

    for c in ranked:
        if len(bundle) >= max_n:
            break

        text = f"{c.question} {c.section} {c.answer}"
        cov = _anchor_overlap_concepts(text, anchor_concepts, lang)

        if not cov:
            continue
        if cov.issubset(covered):
            continue

        bundle.append(c)
        covered |= cov
        per_candidate_covered.append({"idx": c.index, "covered_concepts": sorted(list(cov))})

        if covered == anchor_concepts:
            break

    details = {
        "required_concepts": sorted(list(anchor_concepts)),
        "covered_concepts": sorted(list(covered)),
        "coverage_complete": covered == anchor_concepts,
        "bundle_cover_debug": per_candidate_covered,
    }
    return bundle, details


# ---------------------------
# FIXED: Stats gate
# ---------------------------

def _passes_stats_gate(text: str, language: str) -> bool:
    """
    Stats answers must:
      - contain a number/percent
      - contain a strict stats marker (NOT "how")
    """
    lang = _norm_lang(language)
    if not _has_number_or_percent(text):
        return False

    hints = STATS_GROUND_HINTS_FR if lang == "fr" else STATS_GROUND_HINTS_EN
    hint_stems = {_stem(x, lang) for x in hints}
    text_stems = _stem_set(_tokenize(text), lang)
    return len(text_stems.intersection(hint_stems)) > 0


def _stats_concept_stems_to_require(anchor_concepts: Set[str], language: str) -> Set[str]:
    """
    For stats queries, require overlap with at least one non-broad concept.
    E.g. genetics/mutation should be required; cancer/patient should not.
    """
    lang = _norm_lang(language)

    # remove stats-intent stems from concept set (e.g., percent)
    intent_hints = STATS_INTENT_HINTS_FR if lang == "fr" else STATS_INTENT_HINTS_EN
    intent_stems = {_stem(x, lang) for x in intent_hints}
    concepts = set(anchor_concepts) - set(intent_stems)

    broad = STATS_BROAD_CONCEPTS_FR if lang == "fr" else STATS_BROAD_CONCEPTS_EN
    broad_stems = {_stem(x, lang) for x in broad}
    concepts = concepts - broad_stems

    return concepts


# ---------------------------
# Main answer function
# ---------------------------

def _semantic_top(candidates: List[RetrievalCandidate]) -> Optional[RetrievalCandidate]:
    """Candidate with the highest dense cosine similarity to the query."""
    scored = [c for c in candidates if c.dense_sim is not None]
    if not scored:
        return None
    return max(scored, key=lambda c: c.dense_sim if c.dense_sim is not None else -1.0)


def _primary_relevance(c: RetrievalCandidate, uses_rerank: bool) -> Optional[float]:
    """The relevance signal used for the accept decision: cross-encoder rerank
    score when reranking is active, otherwise dense cosine similarity."""
    if uses_rerank and c.rerank_score is not None:
        return float(c.rerank_score)
    if c.dense_sim is not None:
        return float(c.dense_sim)
    return None


def _crosslingual_notice(query_lang: str, answer_lang: str) -> str:
    """One-line note shown when the only relevant content is in another language."""
    q, a = _norm_lang(query_lang), _norm_lang(answer_lang)
    if q == a:
        return ""
    if q == "fr":
        names = {"en": "anglais", "fr": "français"}
        return f"(Cette information n’est disponible qu’en {names.get(a, a)}.)"
    names = {"en": "English", "fr": "French"}
    return f"(This information is only available in {names.get(a, a)}.)"


def _decide_bundle(
    cands: List[RetrievalCandidate],
    lang: str,
    anchor_concepts: Set[str],
    strong_anchors: Set[str],
    stats_intent: bool,
    thresholds: Dict[str, float],
    dbg: Dict[str, Any],
    debug: bool,
) -> Optional[List[RetrievalCandidate]]:
    """
    Run the semantic-first accept decision over ONE candidate subset (used once
    for same-language candidates, then again for cross-language as a fallback).
    Returns the answer bundle, or None to abstain. Writes decision debug into
    `dbg`.
    """
    if not cands:
        if debug:
            dbg["decision_path"] = "abstain(no_candidates)"
        return None

    sem_accept_threshold = thresholds["sem_accept_threshold"]
    rerank_accept_threshold = thresholds["rerank_accept_threshold"]
    dense_floor = thresholds["dense_floor"]

    uses_rerank = any(c.rerank_score is not None for c in cands)

    def _prim(c: RetrievalCandidate) -> float:
        v = _primary_relevance(c, uses_rerank)
        return v if v is not None else -1e9

    top_primary = max(cands, key=_prim)
    primary_threshold = rerank_accept_threshold if uses_rerank else sem_accept_threshold
    primary_value = _primary_relevance(top_primary, uses_rerank)

    if debug:
        dbg["primary_signal"] = "rerank" if uses_rerank else "dense"
        dbg["primary_value"] = round(primary_value, 4) if primary_value is not None else None
        dbg["primary_threshold"] = primary_threshold

    # Stats preference: answer with a grounded statistic if the user asked for one.
    if stats_intent:
        required = _stats_concept_stems_to_require(anchor_concepts, lang)
        ok_stats: List[RetrievalCandidate] = []
        for c in cands:
            text = f"{c.question} {c.section} {c.answer}"
            if not _passes_stats_gate(text, lang):
                continue
            if required and not _anchor_overlap_concepts(text, required, lang):
                continue
            ok_stats.append(c)
        if debug:
            dbg["stats_gate_candidates"] = [{"idx": c.index} for c in ok_stats[:10]]
        if ok_stats:
            best = sorted(ok_stats, key=_score_candidate, reverse=True)[0]
            if debug:
                dbg["decision_path"] = "stats"
            return [best]
        elif debug:
            dbg["stats_fell_through"] = True

    primary_ok = (primary_value is not None) and (primary_value >= primary_threshold)

    # Lexical safety net: a candidate covering a high-IDF anchor at >= dense_floor.
    lexical_lead: Optional[RetrievalCandidate] = None
    if strong_anchors:
        for c in sorted(cands, key=_score_candidate, reverse=True):
            text = f"{c.question} {c.section} {c.answer}"
            if not _anchor_overlap_concepts(text, strong_anchors, lang):
                continue
            if c.dense_sim is not None and c.dense_sim < dense_floor:
                continue
            lexical_lead = c
            break

    if not (primary_ok or lexical_lead is not None):
        if debug:
            dbg["decision_path"] = "abstain"
        return None

    lead = top_primary if primary_ok else lexical_lead
    if debug:
        dbg["decision_path"] = "semantic_primary" if primary_ok else "lexical_net"

    def _member_ok(c: RetrievalCandidate) -> bool:
        v = _primary_relevance(c, uses_rerank)
        return v is not None and v >= primary_threshold

    relevant_pool = [c for c in cands if _member_ok(c)]
    if lead is not None and lead not in relevant_pool:
        relevant_pool = [lead] + relevant_pool

    if anchor_concepts:
        bundle, cov_details = _select_bundle_with_coverage(
            relevant_pool, lang, anchor_concepts, max_n=3
        )
        if debug:
            dbg["coverage_gate"] = cov_details
    else:
        bundle = []

    if lead is not None:
        bundle = [lead] + [c for c in bundle if c.index != lead.index]
    if not bundle and lead is not None:
        bundle = [lead]

    # Multi-source: fill the remaining slots with the next most relevant
    # candidates (all above the accept threshold), so the answer presents the
    # top few relevant FAQ entries rather than betting everything on the
    # reranker's single #1. This surfaces complementary answers (e.g. a
    # "therapeutic break" entry alongside a "recurrence risk" entry).
    have = {c.index for c in bundle}
    for c in sorted(relevant_pool, key=_score_candidate, reverse=True):
        if len(bundle) >= 3:
            break
        if c.index not in have:
            bundle.append(c)
            have.add(c.index)

    return bundle if bundle else None


def answer_query(
    retriever: "HybridFAQRetriever",
    user_query: str,
    language: Optional[str] = None,
    use_llm: bool = False,
    llm_model: str = "llama3.2",
    debug: bool = False,
    sem_accept_threshold: float = 0.62,
    rerank_accept_threshold: float = -1.0,  # mmarco cross-encoder scores relevant items ~ -1..+2
    dense_floor: float = 0.50,
) -> AnswerResult:
    """
    SEMANTIC-FIRST answer/abstain decision.

    `language` is the query language ("en"/"fr"); it defaults to the
    retriever's index language. Pass it explicitly when one retriever serves
    several languages (the shared index), never by mutating the retriever.

    The primary relevance signal is the cross-encoder rerank score (when
    reranking is on) or dense cosine similarity (otherwise). Lexical / IDF
    anchors NO LONGER gate the answer -- they only (a) shape the bundle for
    multi-concept questions and (b) provide a recall safety net for rare,
    highly specific terms. This is what lets the IDF anchor extractor stay
    list-free without risking false abstentions.

    Accept if EITHER:
      1. Primary: top candidate's relevance >= its threshold
         (rerank >= `rerank_accept_threshold`, or dense >= `sem_accept_threshold`).
      2. Lexical safety net: a candidate covers a HIGH-IDF anchor (idf >=
         corpus average) AND is at least `dense_floor` cosine-similar. Catches
         specific-term matches the reranker/embedder may under-score.

    Thresholds MUST be calibrated on the gold eval set (tests/eval_set.jsonl)
    for the deployed models. Defaults are conservative starting points, NOT
    tuned values. For a patient-facing tool, watch the false-ANSWER rate when
    lowering thresholds.
    """
    lang = _norm_lang(language or retriever.language)
    _t_total = time.perf_counter()
    timing: Dict[str, Any] = {}
    candidates = retriever.retrieve(user_query, lang, timing)
    timing["llm"] = 0.0

    ax = extract_anchor_concepts(user_query, lang, retriever)
    anchors = ax.anchors
    anchor_concepts = set(anchors)
    # "Strong" (specific) anchors for the lexical safety net: terms that appear
    # in only a small share of the corpus. Defined by document-frequency, NOT by
    # idf >= average_idf -- the latter collapses to the empty set once a large
    # article corpus inflates the average, disabling the net entirely.
    strong_df_cap = max(1, int(0.15 * retriever.corpus_size(lang)))
    strong_anchors = {a for a in anchor_concepts if 1 <= retriever.df(a, lang) <= strong_df_cap}
    stats_intent = _is_stats_intent(user_query, lang)

    sem_top = _semantic_top(candidates)
    sem_top_sim = (sem_top.dense_sim if (sem_top and sem_top.dense_sim is not None) else None)

    dbg: Dict[str, Any] = {}
    if debug:
        dbg["query_lang"] = lang
        dbg["timing_ms"] = timing  # same dict object; llm/total filled in below
        dbg["shared_mode"] = bool(getattr(retriever, "shared", False))
        dbg["anchors"] = anchors
        dbg["strong_anchors"] = sorted(list(strong_anchors))
        dbg["present_concepts"] = [f"{s}(idf={idf:.2f},df={d})" for (s, idf, d) in ax.present]
        dbg["absent_concepts"] = ax.dropped_absent
        dbg["dropped_common"] = ax.dropped_common
        dbg["stats_intent"] = stats_intent
        dbg["sem_top_sim"] = (round(sem_top_sim, 4) if sem_top_sim is not None else None)
        dbg["sem_accept_threshold"] = sem_accept_threshold
        dbg["qp_index_loaded"] = (retriever._index_qp is not None)  # type: ignore[attr-defined]
        dbg["top_candidates"] = [
            {"idx": c.index, "lang": c.lang, "fused": round(c.fused_score, 5),
             "rerank": (round(c.rerank_score, 3) if c.rerank_score is not None else None),
             "dense": (round(c.dense_sim, 4) if c.dense_sim is not None else None),
             "q": c.question[:120]}
            for c in candidates[:15]
        ]

    if not candidates:
        timing["total"] = (time.perf_counter() - _t_total) * 1000.0
        return AnswerResult(answered=False, answer_text=build_abstain(lang),
                            timing_ms=timing, debug=(dbg if debug else None))

    thresholds = {
        "sem_accept_threshold": sem_accept_threshold,
        "rerank_accept_threshold": rerank_accept_threshold,
        "dense_floor": dense_floor,
    }

    # Same-language first, cross-lingual fallback. In per-language mode every
    # candidate already shares the query language, so `cross` is empty.
    if getattr(retriever, "shared", False):
        same = [c for c in candidates if c.lang == lang]
        cross = [c for c in candidates if c.lang != lang]
    else:
        same, cross = candidates, []

    notice = ""
    bundle = _decide_bundle(same, lang, anchor_concepts, strong_anchors,
                            stats_intent, thresholds, dbg, debug)

    if bundle is None and cross:
        cross_dbg: Dict[str, Any] = {}
        cross_bundle = _decide_bundle(cross, lang, anchor_concepts, strong_anchors,
                                      stats_intent, thresholds, cross_dbg, debug)
        if cross_bundle is not None:
            bundle = cross_bundle
            notice = _crosslingual_notice(lang, bundle[0].lang)
            if debug:
                dbg["crosslingual_fallback"] = True
                dbg["answer_lang"] = bundle[0].lang
                dbg["cross_pass"] = cross_dbg

    if not bundle:
        if debug:
            dbg.setdefault("decision_path", "abstain")
        timing["total"] = (time.perf_counter() - _t_total) * 1000.0
        return AnswerResult(answered=False, answer_text=build_abstain(lang),
                            timing_ms=timing, debug=(dbg if debug else None))

    # Labels/preface are in the QUERY language. Source citations are computed here
    # but kept OUT of the answer body: the UI shows them in the "Sources used for
    # this answer" dropdown (built from source_indices), and CLI/verifiability
    # consumers can read them from AnswerResult.sources_text.
    sources = _format_sources(lang, bundle)
    notice_block = (notice + "\n\n") if notice else ""

    def _verbatim_answer() -> str:
        # FAQ content quoted verbatim + fixed empathy sentence (original behavior).
        faq_body = _format_bundle_body(bundle)
        factual_block = (_format_preface(lang) + faq_body).strip()
        prefix = _fallback_empathy(lang, user_query, bundle[0].question)
        return (prefix + notice_block + factual_block).strip()

    llm_status: Optional[str] = None
    llm_error: Optional[str] = None
    if use_llm:
        # Grounded rephrasing: the LLM rewrites ONLY the retrieved source text for
        # clarity + empathy (no new facts), then the verbatim sources are cited.
        # If the LLM is unreachable/empty, fall back to the verbatim answer so we
        # never lose a response -- but record WHY so the CLI/GUI can say so.
        source_text = _bundle_source_text(bundle)
        _t_llm = time.perf_counter()
        writer = LLMWrapperWriter(language=lang, model=llm_model)
        rephrased = writer.rephrase(user_query=user_query, source_text=source_text).strip()
        timing["llm"] = (time.perf_counter() - _t_llm) * 1000.0
        if rephrased:
            answer_text = (notice_block + rephrased).strip()
            llm_status = "used"
            if debug:
                dbg["llm_mode"] = "rephrase"
        else:
            # Distinguish "could not reach the LLM" from "LLM returned nothing".
            answer_text = _verbatim_answer()
            llm_error = writer.last_error
            llm_status = "fallback_unreachable" if writer.last_error else "fallback_empty"
            if debug:
                dbg["llm_mode"] = "verbatim_fallback"
                dbg["llm_error"] = writer.last_error
    else:
        answer_text = _verbatim_answer()
        if debug:
            dbg["llm_mode"] = "verbatim"

    # Compassion guardrail: reframe patient-mortality phrasing ("dying from breast
    # cancer") into survival language. Deterministic, so it holds regardless of
    # what the local LLM emits and covers the verbatim path too. Applied to the
    # answer body only; cited sources in the dropdown stay verbatim.
    answer_text = _reframe_survival(answer_text, lang)

    timing["total"] = (time.perf_counter() - _t_total) * 1000.0

    top = bundle[0]
    return AnswerResult(
        answered=True,
        answer_text=answer_text,
        source_title=_candidate_title(top),   # FAQ question or article source, never a filename breadcrumb
        source_index=top.index,
        source_indices=[c.index for c in bundle],
        sources_text=sources,
        timing_ms=timing,
        llm_status=llm_status,
        llm_error=llm_error,
        debug=(dbg if debug else None),
    )


# ---------------------------
# Debug printer
# ---------------------------

def print_debug(result: AnswerResult) -> None:
    if not result.debug:
        return

    print("\n[DEBUG] query_lang:", result.debug.get("query_lang"),
          "| shared_mode:", result.debug.get("shared_mode"),
          "| crosslingual_fallback:", result.debug.get("crosslingual_fallback", False))
    print("[DEBUG] anchors:", result.debug.get("anchors"))
    print("[DEBUG] strong_anchors:", result.debug.get("strong_anchors"))
    print("[DEBUG] present_concepts (idf,df):", result.debug.get("present_concepts"))
    print("[DEBUG] dropped_absent:", result.debug.get("absent_concepts"))
    print("[DEBUG] dropped_common:", result.debug.get("dropped_common"))
    print("[DEBUG] stats_intent:", result.debug.get("stats_intent"))
    print("[DEBUG] primary_signal:", result.debug.get("primary_signal"),
          "value:", result.debug.get("primary_value"),
          "threshold:", result.debug.get("primary_threshold"))
    print("[DEBUG] sem_top_sim:", result.debug.get("sem_top_sim"))
    print("[DEBUG] decision_path:", result.debug.get("decision_path"))
    print("[DEBUG] qp_index_loaded:", result.debug.get("qp_index_loaded"))

    t = result.debug.get("timing_ms") or {}
    if t:
        print("[DEBUG] timing_ms: retrieve={:.0f} rerank={:.0f} (n={}) llm={:.0f} total={:.0f}".format(
            t.get("retrieve", 0.0), t.get("rerank", 0.0), t.get("n_reranked", 0),
            t.get("llm", 0.0), t.get("total", 0.0)))

    if "coverage_gate" in result.debug:
        print("[DEBUG] coverage_gate:", result.debug.get("coverage_gate"))

    if "stats_gate_candidates" in result.debug:
        print("[DEBUG] stats_gate_candidates:", result.debug.get("stats_gate_candidates"))

    print("[DEBUG] Retrieved candidates:")
    for row in result.debug.get("top_candidates", []):
        print(f"  idx={row['idx']} fused={row['fused']} rerank={row['rerank']} "
              f"dense={row.get('dense')} | Q={row['q']}")
