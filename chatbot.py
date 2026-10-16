#!/usr/bin/env python3
"""
chatbot.py

CLI for hormonAI.

Key rules:
- Retrieval is restricted to the knowledge base (FAQs + articles).
- LLM (if enabled) rephrases ONLY the retrieved source text (no added facts).
- Answers are grounded strictly in the retrieved sources (verbatim or grounded
  rephrase), with sources always cited.
"""

from __future__ import annotations

import os
import sys

from config import gate_kwargs, load_retriever, parse_args
from hormonai.answer import answer_query, print_debug
from audit_logger import AuditLogger


def main() -> None:
    args = parse_args(default_scope="language")

    shared = args.retrieval_scope == "shared"
    scope_label = "shared (cross-lingual fallback)" if shared else "language-only"
    print(f"Loading retriever for LANGUAGE = {args.language} | scope = {scope_label}...")
    retriever = load_retriever(args, args.language, shared)

    logger = AuditLogger(args.audit_log)

    if args.language == "fr":
        print("Chatbot prêt (base de connaissances hormonothérapie adjuvante).")
        print("Tapez 'exit' ou 'quit' pour quitter.\n")
    else:
        print("Chatbot ready (adjuvant hormone therapy knowledge base).")
        print("Type 'exit' or 'quit' to leave.\n")

    while True:
        try:
            user = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not user:
            continue
        if user.lower() in ("exit", "quit"):
            print("Bye.")
            break

        result = answer_query(
            retriever=retriever,
            user_query=user,
            use_llm=args.use_llm,
            llm_model=args.llm_model,
            debug=args.debug,
            **gate_kwargs(args),
        )

        if args.debug:
            print_debug(result)

        logger.log_query(
            query=user,
            language=args.language,
            answered=result.answered,
            used_llm=(args.use_llm and result.answered),
            source_index=result.source_index,
            source_question=result.source_title,
            timing_ms=result.timing_ms,
            meta=(result.debug if args.debug else None),
        )

        # Make an LLM rephrasing fallback explicit instead of silent: the answer
        # is the verbatim source text because the LLM could not be used.
        if result.llm_status in ("fallback_unreachable", "fallback_empty"):
            if result.llm_status == "fallback_unreachable":
                reason = (f"could not reach the LLM ({result.llm_error}); "
                          f"is Ollama running at {os.getenv('OLLAMA_HOST', 'http://localhost:11434')}?")
            else:
                reason = "the LLM returned nothing"
            print(f"[notice] LLM rephrasing requested but {reason} "
                  f"Showing the verbatim source answer instead.", file=sys.stderr)

        print("\nBot:", result.answer_text, "\n")
        # Sources are kept out of the answer body (the GUI shows them in a
        # dropdown); print them here so the CLI answer stays verifiable.
        if result.sources_text:
            label = "Sources :" if args.language == "fr" else "Sources:"
            print(label, "\n" + result.sources_text, "\n")


if __name__ == "__main__":
    main()
