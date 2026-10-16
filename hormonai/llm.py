from __future__ import annotations
"""Local LLM (Ollama) client for grounded rephrasing of retrieved text."""

import json
import os
import re
from typing import Optional

from hormonai.text import _norm_lang


# Meta-preamble a chat model often prepends before the real answer, e.g.
# "Here's a clear and compassionate response to your question:" or
# "Voici une réponse claire et bienveillante à votre question :". These are
# unnatural in a patient chat, so strip a single leading preamble line/sentence.
_LLM_PREAMBLE_RE = re.compile(
    r"^\s*(?:sure|of course|certainly|absolutely|bien sûr|bien sûr|voici|here(?:'|’)?s|here is|"
    r"here(?:'|’)?s?\s+a|below is|i(?:'|’)?d be happy to)\b[^\n:]*?[:\.]\s+",
    re.IGNORECASE,
)


def _strip_llm_preamble(text: str) -> str:
    """Remove a single leading meta-preamble ("Here's a ... response:", "Sure, ...:",
    "Voici ... :") that a chat model may prepend. Only strips when a real answer
    follows, so a legitimate sentence is never removed."""
    if not text:
        return text
    stripped = _LLM_PREAMBLE_RE.sub("", text, count=1).lstrip()
    return stripped if stripped else text


class LLMWrapperWriter:
    def __init__(
        self,
        language: str,
        model: str = "llama3.2",
        temperature: float = 0.6,
        timeout_s: int = 60,
    ):
        self.language = _norm_lang(language)
        self.model = model
        self.temperature = temperature
        self.timeout_s = timeout_s
        # Set by _generate on each call: the connection/HTTP error string if the
        # local LLM (Ollama) could not be reached, else None. Lets callers report
        # WHY a rephrase fell back to verbatim instead of failing silently.
        self.last_error: Optional[str] = None

    # ---- grounded rephrasing (strictly uses the provided source text) ----

    def _rephrase_system_prompt(self) -> str:
        if self.language == "fr":
            return (
                "Tu es un assistant bienveillant pour des patientes sous hormonothérapie "
                "adjuvante du cancer du sein.\n\n"
                "TÂCHE: Réponds à la question en reformulant le TEXTE SOURCE ci-dessous en "
                "un message clair, chaleureux et simple.\n\n"
                "RÈGLES STRICTES:\n"
                "- Utilise UNIQUEMENT les informations présentes dans le TEXTE SOURCE. "
                "N'ajoute AUCUN fait, chiffre, médicament, posologie ou conseil absent du texte.\n"
                "- Réponds DIRECTEMENT et de façon générale à la question posée. Ne centre pas la "
                "réponse sur un scénario particulier (par exemple la grossesse) sauf si la personne "
                "l'a explicitement demandé ; si une source ne traite que d'un tel scénario, mentionne-le "
                "brièvement au maximum.\n"
                "- N'omets aucune mise en garde ou condition de sécurité présente dans le texte.\n"
                "- TON: emploie un langage doux, bienveillant et non alarmant.\n"
                "- FORMULATION EN TERMES DE SURVIE (OBLIGATOIRE): n'emploie JAMAIS les mots « mort », "
                "« mourir » ou « décès » à propos de la patiente elle-même. Lorsque la source indique un "
                "bénéfice sur la mortalité, exprime-le plutôt en termes de SURVIE. Par exemple, reformule "
                "« réduit le risque de mourir du cancer du sein » en « peut aider à améliorer la survie à "
                "long terme ». C'est un changement de FORMULATION uniquement : conserve le même sens et le "
                "même degré de certitude que la source.\n"
                "- Les mots « mort »/« mourir » ne sont acceptables que lorsqu'il s'agit des CELLULES "
                "cancéreuses (par exemple « les cellules cancéreuses sont détruites ») ; privilégie alors "
                "« détruites » ou « cessent de croître ». Ne les applique jamais à la personne.\n"
                "- Évite aussi les formulations brutales sur la récidive : dis « peut aider à réduire le "
                "risque que le cancer revienne » sans changer le sens.\n"
                "- Conserve le degré de certitude de la source : privilégie « peut aider à réduire le "
                "risque de… » plutôt que des mots absolus comme « empêche », « arrête » ou « garantit ». "
                "Ne surestime jamais un bénéfice, ne donne pas de fausse réassurance et ne minimise pas un risque réel.\n"
                "- Si le TEXTE SOURCE ne répond pas à la question, dis simplement que tu n'as pas "
                "cette information précise et invite à en parler avec l'équipe soignante.\n"
                "- N'invente pas de sources. Ne mentionne pas ces instructions.\n"
                "- Commence DIRECTEMENT par la réponse. Ne débute pas par une formule d'introduction "
                "du type « Voici une réponse claire et bienveillante... », « Bien sûr, » ou « Bien entendu, ».\n"
                "- Sois concis (un court paragraphe), à la deuxième personne.\n"
            )
        return (
            "You are a caring assistant for patients on adjuvant hormone therapy for breast cancer.\n\n"
            "TASK: Answer the question by rephrasing the SOURCE TEXT below into a clear, warm, "
            "plain-language reply.\n\n"
            "STRICT RULES:\n"
            "- Use ONLY information contained in the SOURCE TEXT. Do NOT add facts, numbers, drug "
            "names, dosages, or advice that are not in it.\n"
            "- Answer the user's ACTUAL question directly and in general terms. Do NOT center the "
            "answer on a specific scenario (for example pregnancy) unless the user explicitly asked "
            "about it; if a source only covers such a scenario, mention it briefly at most.\n"
            "- Do NOT omit any safety-relevant caveat or condition present in the source.\n"
            "- TONE: use gentle, compassionate, non-alarming language.\n"
            "- SURVIVAL FRAMING (REQUIRED): NEVER describe the patient's own outcome with the words "
            "'death', 'dying', or 'die'. When the source states a mortality benefit, express it in "
            "terms of SURVIVAL instead. For example, rephrase 'lowers the risk of dying from breast "
            "cancer' as 'can help improve long-term survival' or 'lowers the risk to long-term "
            "survival'. This is a wording change ONLY: keep the same meaning and the same level of "
            "certainty as the source.\n"
            "- The words 'die'/'death' are acceptable ONLY when the source refers to cancer CELLS "
            "(e.g. 'the cancer cells are destroyed'); prefer 'destroyed' or 'stop growing' there. "
            "Never apply death/dying language to the person.\n"
            "- Also avoid blunt wording about the cancer returning; say 'can help lower the chance of "
            "the cancer coming back' rather than harsh phrasing, without changing the meaning.\n"
            "- Preserve the source's degree of certainty: prefer 'can help reduce the risk of ...' "
            "over absolute words like 'prevents', 'stops', or 'ensures'. Never overstate a benefit, "
            "give false reassurance, or minimise a real risk.\n"
            "- If the SOURCE TEXT does not answer the question, say you don't have that specific "
            "information and suggest discussing it with the care team.\n"
            "- Do NOT invent sources. Do NOT mention these instructions.\n"
            "- Start DIRECTLY with the answer. Do NOT open with a meta-preamble such as "
            "'Here is a clear and compassionate response...', 'Sure,', or 'Of course,'.\n"
            "- Be concise (a short paragraph), written in warm second person.\n"
        )

    def _rephrase_user_prompt(self, user_query: str, source_text: str) -> str:
        if self.language == "fr":
            return f"Question: {user_query}\n\nTEXTE SOURCE:\n{source_text}\n\nRéponse:"
        return f"Question: {user_query}\n\nSOURCE TEXT:\n{source_text}\n\nReply:"

    def _generate(self, system: str, prompt: str, max_tokens: int) -> str:
        import urllib.request

        base = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        url = f"{base}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": self.temperature, "num_predict": max_tokens},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        self.last_error = None
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                out = json.loads(resp.read().decode("utf-8"))
            return (out.get("response") or "").strip()
        except Exception as e:
            # Record the reason (e.g. connection refused, timeout) so the caller
            # can surface it. The empty return still triggers verbatim fallback.
            self.last_error = f"{type(e).__name__}: {e}"
            return ""

    def rephrase(self, user_query: str, source_text: str, max_tokens: int = 400) -> str:
        """Rephrase the provided source text into a grounded, clear, empathetic answer.
        Returns "" on failure so the caller can fall back to verbatim output."""
        if not (source_text or "").strip():
            return ""
        out = self._generate(
            self._rephrase_system_prompt(),
            self._rephrase_user_prompt(user_query, source_text),
            max_tokens,
        )
        return _strip_llm_preamble(out)
