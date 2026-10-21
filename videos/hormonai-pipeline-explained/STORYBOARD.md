---
format: 1920x1080
duration: 60s
message: "hormonAI answers only from its own vetted FAQ: it finds the best-matching entry, checks it really fits, and otherwise declines."
arc: how-to-process
audience: project stakeholders, clinicians and reviewers of the hormonAI project (non-specialists in ML)
mode: collaborative
music: none
---

## Frame 1 — Hook

- scene: One patient question types onto the cream canvas; beneath it two possible replies — a confident made-up one (struck through) and "I'd rather check."
- onscreen: "How long will I be on tamoxifen?" / A chatbot could guess. / A medical chatbot must not.
- voiceover: ""
- duration: 6s
- poster: 5s
- transition_in: cut
- status: outline
- src: compositions/frames/01-hook.html
- type: hook
- persuasion: Stakes / consequence + before/after contrast
- beat: Concern + recognition
- blueprint: kinetic-type-beats

narrativeRole: Opens the gap — why answering medical questions from a chatbot is risky, in the viewer's own terms.
keyMessage: For patients, a wrong confident answer is worse than no answer.

## Frame 2 — The promise

- scene: The hormonAI wordmark settles; a stack of FAQ cards fans out behind it with the counts "180 vetted answers · English 111 · Français 69"; a single line lands: "It answers only from these — or it says so."
- onscreen: hormonAI / 180 vetted FAQ answers · EN 111 · FR 69 / Answers only from these. Otherwise: "Please ask your oncology team."
- voiceover: ""
- duration: 7s
- poster: 6s
- transition_in: crossfade
- status: outline
- src: compositions/frames/02-promise.html
- type: product_intro
- persuasion: Concretization (abstract safety → a finite stack of vetted cards)
- beat: Clarity + relief
- blueprint: titlecard-reveal

narrativeRole: Lands the thesis by beat 2 — the bot is a careful finder of vetted answers, not a free writer.
keyMessage: Every answer comes from a fixed, reviewed knowledge base.

## Frame 3 — Step 1: four searches

- scene: Stage for the whole process: a slim 5-step progress rail at top (Search · Merge · Rerank · Check · Answer), step 1 lit. The question card sits left; four lanes fan out to the right, each filling with ranked result chips: "Keywords", "Meaning of the question", "Question + answer", "Rewordings". Each lane ends with "top 40".
- onscreen: 1 Search / Keywords (BM25) · Meaning of the question · Question + answer · Rewordings / each returns its top 40
- voiceover: ""
- duration: 8s
- poster: 7s
- transition_in: push-slide LEFT
- status: outline
- src: compositions/frames/03-search.html
- type: feature_showcase
- persuasion: Signposting + progressive disclosure (one lane at a time)
- beat: Orientation + comprehension
- blueprint: grid-card-assemble

narrativeRole: First move of the process — the question is matched four different ways at once, by words and by meaning.
keyMessage: Four searches look for the answer from different angles.

## Frame 4 — Step 2: merge the rankings

- scene: Same stage, rail on step 2. The four lanes from frame 3 slide together; chips that appear high in several lanes glow and rise into one merged list; a small formula tag reads "score = Σ 1 / (60 + rank)".
- onscreen: 2 Merge / Ranked high in several searches → rises to the top / score = Σ 1 / (60 + rank)
- voiceover: ""
- duration: 7s
- poster: 6s
- transition_in: push-slide LEFT
- status: outline
- src: compositions/frames/04-merge.html
- type: feature_showcase
- persuasion: Demonstration (show the mechanism running) + causal chain
- beat: "Aha"
- blueprint: grid-card-assemble

narrativeRole: Shows how the four views are combined into one ordering without trusting any single search.
keyMessage: Agreement between searches decides the shortlist.

## Frame 5 — Step 3: rerank the top 5

- scene: Same stage, rail on step 3. The top 5 merged chips become 5 cards; a reading lens passes over each card paired with the question and stamps a relevance bar; the cards re-order and the winner lifts to #1: "How long do I need to take hormone therapy?"
- onscreen: 3 Rerank / A second model reads question + entry side by side / #1 "How long do I need to take hormone therapy?"
- voiceover: ""
- duration: 7s
- poster: 6s
- transition_in: push-slide LEFT
- status: outline
- src: compositions/frames/05-rerank.html
- type: feature_showcase
- persuasion: Progressive disclosure + comparison
- beat: Focus + confidence
- blueprint: grid-card-assemble

narrativeRole: Shows the precise, slower check that decides the best candidate.
keyMessage: The best-fitting FAQ entry is picked by reading, not just matching.

## Frame 6 — Step 4: answer or decline

- scene: Same stage, rail on step 4. The #1 card enters a checkpoint gate that splits into three outcomes, each lighting in turn: "Clear match → answer" (cobalt), "Only in the other language → shown as-is, labelled 'only available in French'", "Nothing fits → polite decline: 'Please discuss this with your oncology team.'" Our example passes through the first.
- onscreen: 4 Check / Clear match → answer · Rare specific term (e.g. a drug name) + close meaning → answer / Only in the other language → shown as-is, never machine-translated / Nothing fits → decline: "Please discuss this with your oncology team."
- voiceover: ""
- duration: 10s
- poster: 9s
- transition_in: push-slide LEFT
- status: outline
- src: compositions/frames/06-gate.html
- type: benefit_highlight
- persuasion: Frame-then-fill (state the three exits, then light each) + rule of three
- beat: Conviction
- blueprint: kinetic-type-beats

narrativeRole: The safety core — the bot must earn the right to answer, and has honest exits when it can't.
keyMessage: When nothing really fits, hormonAI declines instead of guessing.

## Frame 7 — Step 5: the answer

- scene: Same stage, rail on step 5. A chat bubble from "Mona" assembles: a short empathy line, then the FAQ text quoted verbatim ("…the treatment lasts 5 to 10 years, depending on…"), then a "Sources used for this answer" panel slides out beside it. A small toggle "Local LLM rewording — off by default" flips on briefly to show the same text reworded more warmly, with the note "uses only this text"; a final tag: "Survival wording guardrail".
- onscreen: 5 Answer / Verbatim from the FAQ, with its source / Optional local LLM: rewords only this text — adds nothing / Sources used for this answer
- voiceover: ""
- duration: 8s
- poster: 7s
- transition_in: push-slide LEFT
- status: outline
- src: compositions/frames/07-answer.html
- type: social_proof
- persuasion: Worked example with real content
- beat: Satisfaction + trust
- blueprint: titlecard-reveal

narrativeRole: Pays off the example — the patient sees vetted text and exactly where it came from.
keyMessage: The answer is the FAQ itself, with its source shown.

## Frame 8 — Takeaway

- scene: The five rail steps collapse into one line; the distilled rule lands large; a quiet footer.
- onscreen: Find. Check. Answer — or decline. / Runs fully locally: models, index and the optional LLM.
- voiceover: ""
- duration: 6s
- poster: 5s
- transition_in: crossfade
- status: outline
- src: compositions/frames/08-takeaway.html
- type: branding
- persuasion: Distillation + callback (to the hook's "must not guess")
- beat: Clarity + resolve
- blueprint: kinetic-type-beats

narrativeRole: Compresses the process into one memorable rule and answers the hook.
keyMessage: hormonAI finds, checks, and answers — or honestly declines.
