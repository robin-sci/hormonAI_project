from __future__ import annotations
"""Text processing: language codes, tokenizing, stemming, synonyms,
statistics-intent detection and IDF-weighted query anchors."""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Set, Tuple

if TYPE_CHECKING:
    from hormonai.retrieval import HybridFAQRetriever

try:
    import snowballstemmer  # type: ignore
except Exception:
    snowballstemmer = None


# ---------------------------
# Language + tokenization
# ---------------------------

def _norm_lang(lang: str) -> str:
    lang = (lang or "en").lower()
    if lang in ("fr", "fra", "french", "français", "francais"):
        return "fr"
    return "en"


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*", (text or "").lower())


def _has_number_or_percent(text: str) -> bool:
    t = text or ""
    return bool(re.search(r"(\d+(\.\d+)?)\s*%|\b\d+(\.\d+)?\b", t))


_INTERROGATIVE_PREFIX = re.compile(
    r"^(can|do|does|is|are|should|shall|will|would|could|may|might|what|when|why|how|where|which|who|"
    r"puis|dois|doit|est-ce|peut|peut-on|peut-il|faut|faut-il|comment|pourquoi|quand|quoi|quel|quelle|où|y-a-t-il)\b",
    flags=re.IGNORECASE,
)


def _looks_like_faq_question(question: str) -> bool:
    """
    Guard against parse artifacts where an ANSWER fragment was stored as a
    question (e.g. "Do not double up to make up for a missed dose.",
    "When osteoporosis exists before or develops during treatment, ...").

    A well-formed FAQ question either ends with '?' or is a short
    interrogative clause. Long declarative sentences that merely start with an
    interrogative word ("When osteoporosis exists...") are rejected. This is a
    runtime safety net for the prebuilt indexes; ingest_faq.py has been fixed
    so freshly ingested corpora will not contain these artifacts.
    """
    q = (question or "").strip()
    if not q:
        return False
    if q.endswith("?"):
        return True
    # Reject negative imperatives / instruction lines ("Do not double up ...",
    # "Ne pas ...") that start with an interrogative-looking word but are answers.
    if re.match(r"^(do not|don't|never|ne\s+pas|n[’']|il ne faut pas)\b", q, flags=re.IGNORECASE):
        return False
    # No question mark: only accept a short interrogative clause.
    if _INTERROGATIVE_PREFIX.match(q) and len(_tokenize(q)) <= 12:
        return True
    return False


# NOTE: the old hand-maintained EN/FR stopword, generic, emotion, and
# drug-term lists (and extract_core_keywords / anchor_keywords / _emotion_stems)
# were removed. Anchor extraction is now IDF-weighted (extract_anchor_concepts +
# a small domain-independent _MINIMAL_FUNCTION_WORDS set); see that function.


# ---------------------------
# Stats intent vs stats grounding (FIX)
# ---------------------------

# Broad: detect that user is asking for stats
STATS_INTENT_HINTS_EN = {
    "percent","percentage","proportion","rate","prevalence","incidence",
    "how","many","often",
    "odds","chance","probability","likelihood","frequency",
}

STATS_INTENT_HINTS_FR = {
    "pourcentage","percent","proportion","taux","prévalence","prevalence","incidence",
    "combien","souvent",
    "probabilité","probabilite","fréquence","frequence",
}

# Strict: require candidate to actually be “stats-like”
# IMPORTANT: NO "how", "many", "often" here — those cause false positives via section titles.
STATS_GROUND_HINTS_EN = {
    "percent","percentage","proportion","rate","prevalence","incidence",
    "odds","chance","probability","likelihood","frequency",
}

STATS_GROUND_HINTS_FR = {
    "pourcentage","percent","proportion","taux","prévalence","prevalence","incidence",
    "probabilité","probabilite","fréquence","frequence",
}

# For stats queries, ignore broad concepts that would match almost anything.
STATS_BROAD_CONCEPTS_EN = {"cancer", "patient", "patients", "people", "person", "persons", "breast"}
STATS_BROAD_CONCEPTS_FR = {"cancer", "patient", "patients", "personne", "personnes", "sein"}


# Words that, on their own, signal the user wants a statistic.
# NOTE: bare "how"/"many"/"often" are deliberately EXCLUDED -- they caused
# duration questions like "How long do I need to stay on therapy?" to be
# misrouted into the strict stats gate and hard-abstained. Statistical INTENT
# is now detected from explicit statistical words or specific bigrams.
STATS_WORD_EN = {
    "percent", "percentage", "proportion", "rate", "rates",
    "prevalence", "incidence", "odds", "probability", "likelihood", "frequency",
}
STATS_WORD_FR = {
    "pourcentage", "percent", "proportion", "taux", "prévalence", "prevalence",
    "incidence", "probabilité", "probabilite", "fréquence", "frequence",
}

_STATS_BIGRAMS_EN = {
    ("how", "many"), ("how", "often"), ("how", "likely"),
    ("what", "percentage"), ("what", "percent"), ("what", "proportion"),
    ("what", "fraction"), ("what", "share"),
}


def _is_stats_intent(user_query: str, language: str) -> bool:
    lang = _norm_lang(language)
    text = user_query or ""
    if "%" in text:
        return True

    toks = _tokenize(text)          # ordered
    tokset = set(toks)
    words = STATS_WORD_FR if lang == "fr" else STATS_WORD_EN
    if tokset & words:
        return True

    bigrams = set(zip(toks, toks[1:]))
    if lang == "fr":
        # "combien de <X>" is statistical, EXCEPT "combien de temps" (= how long).
        if ("combien", "de") in bigrams and "temps" not in tokset:
            return True
        if ("quelle", "fréquence") in bigrams or ("quelle", "frequence") in bigrams:
            return True
        if ("quel", "pourcentage") in bigrams:
            return True
        return False

    return len(bigrams & _STATS_BIGRAMS_EN) > 0


# ---------------------------
# Stemming (Snowball preferred)
# ---------------------------

_STEMMER_CACHE: Dict[str, Any] = {}


def _snowball_stem(token: str, language: str) -> str:
    assert snowballstemmer is not None
    lang = _norm_lang(language)
    key = "english" if lang == "en" else "french"
    if key not in _STEMMER_CACHE:
        _STEMMER_CACHE[key] = snowballstemmer.stemmer(key)
    return _STEMMER_CACHE[key].stemWord((token or "").lower())


def _fallback_stem_en(token: str) -> str:
    t = (token or "").lower()
    if len(t) <= 2:
        return t
    if t.endswith("ies") and len(t) > 4:
        t = t[:-3] + "y"
    elif t.endswith("es") and len(t) > 4:
        t = t[:-2]
    elif t.endswith("s") and len(t) > 3:
        t = t[:-1]
    for suf in ("ing", "ed", "ly"):
        if t.endswith(suf) and len(t) > len(suf) + 2:
            t = t[: -len(suf)]
            break
    return t


def _fallback_stem_fr(token: str) -> str:
    t = (token or "").lower()
    if len(t) <= 2:
        return t
    if t.endswith("es") and len(t) > 4:
        t = t[:-2]
    elif t.endswith("s") and len(t) > 3:
        t = t[:-1]
    for suf in ("ements","ement","ations","ation","ateurs","ateur","ées","ée","er","ir","re"):
        if t.endswith(suf) and len(t) > len(suf) + 2:
            t = t[: -len(suf)]
            break
    return t


def _stem(token: str, language: str) -> str:
    if snowballstemmer is not None:
        try:
            return _snowball_stem(token, language)
        except Exception:
            pass
    return _fallback_stem_fr(token) if _norm_lang(language) == "fr" else _fallback_stem_en(token)


def _stem_set(tokens: List[str], language: str) -> Set[str]:
    return {_stem(t, language) for t in tokens if t}


# ---------------------------
# Lay ↔ clinical synonym sets (MATCHING ONLY)
# ---------------------------

# Lay <-> clinical synonym groups. Any member of a group is considered to
# cover any other member during the coverage gate. This is a stopgap that
# encodes the most common lay/clinical mismatches; the durable fix is a
# domain-adapted embedding model or an LLM query-rewrite step (see
# RETRIEVAL_REVIEW.md, section 5.3).
_SYNONYM_GROUPS_EN: List[List[str]] = [
    ["heart", "cardiovascular", "cardio", "cardiac"],
    ["bone", "bones", "osteoporosis", "osteoporotic", "skeletal"],
    # "break" was the concept that broke the example query: the corpus phrases
    # the same idea as "pause", "stop", "discontinue", etc.
    ["break", "pause", "stop", "stopping", "interrupt", "interruption",
     "discontinue", "discontinuation", "hold", "holiday", "suspend"],
    ["pregnant", "pregnancy", "conceive", "conception", "fertility", "baby", "child"],
    ["tired", "tiredness", "fatigue", "exhausted", "exhaustion", "energy"],
    ["period", "periods", "menstrual", "menstruation", "cycle", "cycles", "bleeding"],
    ["bloodwork", "blood", "bloodtest", "labs"],
    ["mood", "depression", "depressed", "sad"],
    ["sleep", "sleeping", "insomnia"],
    ["libido", "sex", "sexual", "desire"],
    ["diet", "food", "foods", "eat", "eating", "nutrition"],
    ["exercise", "activity", "sport", "sports", "physical"],
    ["recurrence", "relapse", "return", "coming-back", "comeback"],
]

_SYNONYM_GROUPS_FR: List[List[str]] = [
    ["coeur", "cardiovasculaire", "cardio", "cardiaque"],
    ["os", "osseux", "ostéoporose", "osteoporose", "squelette"],
    ["pause", "arrêt", "arret", "arrêter", "arreter", "stopper", "interrompre",
     "interruption", "suspendre", "interrompue"],
    ["enceinte", "grossesse", "concevoir", "conception", "fertilité", "fertilite",
     "bébé", "bebe", "enfant"],
    ["fatigue", "fatigué", "fatigue", "épuisé", "epuise", "épuisement", "énergie", "energie"],
    ["règles", "regles", "menstruel", "menstruation", "cycle", "cycles", "saignement"],
    ["sang", "prise-de-sang", "analyses"],
    ["humeur", "dépression", "depression", "déprimé", "deprime", "triste"],
    ["sommeil", "dormir", "insomnie"],
    ["libido", "sexe", "sexuel", "sexuelle", "désir", "desir"],
    ["régime", "regime", "alimentation", "aliment", "aliments", "manger", "nutrition"],
    ["exercice", "activité", "activite", "sport", "physique"],
    ["récidive", "recidive", "rechute", "retour"],
]


def _build_synonym_map(groups: List[List[str]], lang: str) -> Dict[str, Set[str]]:
    m: Dict[str, Set[str]] = {}
    for group in groups:
        stems = {_stem(w, lang) for w in group}
        for s in stems:
            m.setdefault(s, set()).update(stems)
    return m


_SYNONYM_MAP_CACHE: Dict[str, Dict[str, Set[str]]] = {}


def _synonym_map(lang: str) -> Dict[str, Set[str]]:
    lang = _norm_lang(lang)
    if lang not in _SYNONYM_MAP_CACHE:
        groups = _SYNONYM_GROUPS_FR if lang == "fr" else _SYNONYM_GROUPS_EN
        _SYNONYM_MAP_CACHE[lang] = _build_synonym_map(groups, lang)
    return _SYNONYM_MAP_CACHE[lang]


def _concept_match_stems(concept_stem: str, language: str) -> Set[str]:
    lang = _norm_lang(language)
    m = _synonym_map(lang)
    return m.get(concept_stem, {concept_stem})


def _anchor_overlap_concepts(text: str, anchor_concepts: Set[str], language: str) -> Set[str]:
    lang = _norm_lang(language)
    text_stems = _stem_set(_tokenize(text or ""), lang)

    covered: Set[str] = set()
    for concept in anchor_concepts:
        acceptable = _concept_match_stems(concept, lang)
        if len(text_stems.intersection(acceptable)) > 0:
            covered.add(concept)
    return covered


# ---------------------------
# IDF-weighted anchor extraction (replaces the stopword/generic/emotion lists)
# ---------------------------

# Minimal, DOMAIN-INDEPENDENT grammatical stop set. This is NOT the old
# maintained keyword machinery -- it only removes universal function words that
# have no retrieval value in any corpus. Everything domain-specific (which
# medical terms are "generic", which words are emotional, which are drugs) is
# now handled automatically by corpus IDF, so those lists are no longer used
# for extraction.
_MINIMAL_FUNCTION_WORDS = {
    # English
    "the", "a", "an", "and", "or", "but", "if", "of", "to", "in", "on", "for",
    "with", "as", "at", "by", "from", "is", "are", "was", "were", "be", "been",
    "do", "does", "did", "have", "has", "had", "can", "could", "should", "would",
    "will", "may", "might", "must", "i", "you", "we", "they", "he", "she", "it",
    "my", "your", "our", "their", "this", "that", "these", "those", "what",
    "why", "how", "when", "where", "which", "who", "not", "no", "yes",
    "about", "into", "onto", "over", "under", "than", "then", "because",
    "while", "during", "before", "after", "between", "through", "without",
    "within", "again", "also", "too", "very", "just", "really", "ever",
    "never", "always", "still", "instead", "sometimes", "maybe", "perhaps",
    # discourse markers / interjections (closed-class, no retrieval value)
    "okay", "ok", "please", "thanks", "thank", "hello", "hi", "hey", "yeah", "sure",
    # French
    "le", "la", "les", "un", "une", "des", "et", "ou", "de", "du", "dans", "sur",
    "pour", "avec", "par", "au", "aux", "en", "est", "sont", "ai", "as", "avez",
    "je", "tu", "il", "elle", "nous", "vous", "ils", "elles", "ce", "cet",
    "cette", "ces", "quoi", "pourquoi", "comment", "quand", "quel", "quelle",
    "pas", "ne", "que", "qui", "sans", "avant", "apres", "après", "encore",
    "aussi", "vraiment", "juste", "jamais", "toujours", "parfois", "peut-etre",
    "peut-être", "bonjour", "salut", "merci", "oui", "non",
}


@dataclass
class AnchorExtraction:
    anchors: List[str]                 # discriminative stems used for coverage
    present: List[Tuple[str, float, int]]   # (stem, idf, df) for all in-corpus tokens
    dropped_absent: List[str]          # tokens not in the corpus (df == 0)
    dropped_common: List[str]          # in-corpus but too frequent to be useful


def extract_anchor_concepts(
    user_query: str,
    language: str,
    retriever: "HybridFAQRetriever",
    max_df_fraction: float = 0.5,
) -> AnchorExtraction:
    """
    Select anchor concepts by corpus IDF instead of hand-maintained lists.

    A stem is an anchor iff it is:
      - not a universal grammatical function word,
      - present in the corpus (df >= 1), and
      - discriminative, i.e. df <= max_df_fraction * corpus_size
        (words appearing in more than ~half the corpus carry no signal).

    Absent tokens (df == 0) are NOT anchors -- lexical matching cannot use them,
    and they are handled by the semantic path. This automatically drops filler
    ("ever", "really"), domain-generic terms ("hormone", "treatment"), emotion
    words, and drug names that saturate the corpus, with zero curation.
    """
    lang = _norm_lang(language)
    cap = max(1, int(retriever.corpus_size(lang) * max_df_fraction))

    seen: Set[str] = set()
    present: List[Tuple[str, float, int]] = []
    dropped_absent: List[str] = []
    anchors: List[str] = []
    dropped_common: List[str] = []

    for tok in _tokenize(user_query):
        if len(tok) <= 2 or tok in _MINIMAL_FUNCTION_WORDS:
            continue
        s = _stem(tok, lang)
        if s in seen:
            continue
        seen.add(s)

        d = retriever.df(s, lang)
        if d <= 0:
            dropped_absent.append(tok)
            continue

        present.append((s, retriever.idf(s, lang), d))
        if d <= cap:
            anchors.append(s)
        else:
            dropped_common.append(tok)

    # If everything present was too common (e.g. a very short, generic query),
    # keep the single most specific (highest-IDF) present stem so lexical
    # coverage still has something to work with.
    if not anchors and present:
        best = max(present, key=lambda x: x[1])
        anchors.append(best[0])

    return AnchorExtraction(
        anchors=anchors,
        present=present,
        dropped_absent=dropped_absent,
        dropped_common=dropped_common,
    )
