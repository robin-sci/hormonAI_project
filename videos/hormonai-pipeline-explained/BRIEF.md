---
workflow: faceless-explainer
flow: automation
storyboard: yes
message: "hormonAI answers only from its own vetted FAQ: it finds the best-matching entry, checks it really fits, and otherwise declines."
destination: youtube
aspect: 1920x1080
language: en
audience: project stakeholders, clinicians and reviewers of the hormonAI project (non-specialists in ML)
length: 60s
angle: how-to
narration: no
---

## Intent

A ~60 second explainer of how hormonAI turns a patient's question into an answer, as the pipeline is now:
question -> four parallel searches -> rank fusion -> reranker -> answer-or-decline gate -> verbatim answer
(or optional grounded LLM rewording) -> survival-language guardrail -> answer with sources. For use in
project presentations. Calm, clinical, trustworthy; no hype.

## Customizations

- No narration: the explanation is carried by on-screen text and diagrams (no speech model can be
  downloaded in this environment). Silent: no music, no SFX.

## Notes

- User-answered: length ~60s, destination 16:9 presentation/YouTube, on-screen text only, plan review first.
- Inferred (not asked): flow automation; angle how-to (step-by-step walkthrough of one question);
  audience project stakeholders; language English.
- Facts must match the code: knowledge base = 180 FAQ entries (111 EN, 69 FR); top 40 per search;
  RRF 1/(60+rank); reranker scores top 5; up to 3 sources per answer; LLM is a local Ollama model and is
  off by default; never machine-translates; declines when nothing fits.
