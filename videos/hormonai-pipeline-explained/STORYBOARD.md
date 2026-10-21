---
format: 1920x1080
duration: 60s
message: "hormonAI answers only from its own vetted FAQ: it finds the best-matching entry, checks it really fits, and otherwise declines."
arc: how-to-process
audience: project stakeholders, clinicians and reviewers of the hormonAI project (non-specialists in ML)
mode: collaborative
music: none
---

## Video direction

- **Palette (frame.md roles):** canvas `bg` cream everywhere; `primary` cobalt is the only accent — the active rail step, the winning card, the "answer" exit, focal highlights; `text` near-black for headlines; `text-muted`/`text-light` for labels and secondary chips; `card-tinted` (4% cobalt fill, 20% border, 14px radius, no shadow) for every card/chip/lane; `negative` red only for the struck-through guess in Frame 1 and never elsewhere; `positive` green only for the "answer" check mark in Frame 6.
- **Type:** Space Grotesk for headlines, step numbers, chips and the formula; Inter for body and quoted FAQ text. Lean on the ramp: h1 for hook/takeaway lines, h2 for step titles, metric-value for "180", body for quotes.
- **Stage:** Frames 3–7 share ONE stage: a slim five-step progress rail across the top (1 Search · 2 Merge · 3 Rerank · 4 Check · 5 Answer, pills, the active step filled cobalt, done steps cobalt outline, upcoming `text-light`), a step title under it at upper-left, and the working diagram filling the middle ~55% of the frame. The question card ("How long will I be on tamoxifen?") stays pinned at the left of the stage in Frames 3–5 so the object being acted on carries across the steps.
- **Motion grammar + reveal model:** smooth long-tail settles (`power3`; `expo.out` only for fast arrivals); no bounce, no overshoot. Silent video: every piece reveals on its own beat in reading order, spread across the shot, back half included — never the whole canvas at t=0. Holds are still; at most subtle jitter (`sine-wave-loop`, low amplitude) on one held hero.
- **Rhythm / held frames:** Frame 2 ends on a ~2s held read (breather after the hook); Frame 6 holds ~2s on the decline line (the safety point must be read); Frame 8 is the final held read. All other frames keep revealing until their last ~1s.
- **Reading time:** silent video — every on-screen sentence stays fully visible for at least ~1.5s before the frame ends.
- **Negative list:** no AI gradients, bokeh, glow-spam or neon; no robots, brains or sparkle icons; no stock medical imagery (pills, stethoscopes, DNA); no shadows (frame.md forbids them); no cursor or browser chrome; no slideshow (front-load then freeze) and no screensaver (many elements floating independently); no lazy breathing, no slow back-half pans/pushes; no red except the struck-through guess.
- **Real FAQ text only:** every FAQ question shown on a chip or card must be one of these real entries (verbatim): "How long do I need to take hormone therapy?" (the winner) · "How long do I need to take hormone therapy: 5 years, 10 years, or for life?" · "Why is the treatment often set at 5 years: is the risk really lower after that point?" · "Do side effects like hot flashes last the entire duration of treatment?" · "What is the real risk of stopping, or of pausing for a month or two to see whether the treatment is causing my pain?" · "Should tamoxifen be stopped before long flights?" · "Can I eat grapefruit?". Ranks shown are illustrative of the mechanism, not a recorded run.
- **Captions:** none (silent, on-screen text only); still keep primary content in the top ~83% for bottom-edge consistency.

## Frame 1 — Hook

- scene: One patient question types onto the cream canvas; beneath it two possible replies — a confident made-up one (struck through) and "I'd rather check."
- onscreen: "How long will I be on tamoxifen?" / A chatbot could guess. / A medical chatbot must not.
- voiceover: ""
- duration: 6s
- poster: 5s
- transition_in: cut
- status: animated
- src: compositions/frames/01-hook.html
- type: hook
- persuasion: Stakes / consequence + before/after contrast
- beat: Concern + recognition
- blueprint: compose

narrativeRole: Opens the gap — why answering medical questions from a chatbot is risky, in the viewer's own terms.
keyMessage: For patients, a wrong confident answer is worse than no answer.

- focal: the patient question line
- roles: question line = foreground subject · two reply lines = supporting · faint hairline grid = background (dim ~35%)

Compose: a three-beat statement build; the payoff is the swap from a struck-through guess to the careful reply.
Scene 1 (0.0–2.0s): cream field with a faint cobalt hairline grid; the question "How long will I be on tamoxifen?" types on with a blinking caret (`discrete-text-sequence`), h1-scale, centered upper-third — the only thing on screen.
Scene 2 (2.0–3.6s): below it a confident reply chip slides up ("Probably 2 years — you can stop when you feel better.") in `text-muted`, then a red strike-through draws across it (`css-marker-patterns`) as the line "A chatbot could guess." reveals beside it (per-word, `dynamic-content-sequencing`).
Scene 3 (3.6–6.0s): the struck chip dims to ~30%; "A medical chatbot must not." lands large in near-black with "must not" in cobalt (per-word reveal, `dynamic-content-sequencing`); centered stack, holds still.

## Frame 2 — The promise

- scene: The hormonAI wordmark settles; a stack of FAQ cards fans out behind it with the counts "180 vetted answers · English 111 · Français 69"; a single line lands: "It answers only from these — or it says so."
- onscreen: hormonAI / 180 vetted FAQ answers · EN 111 · FR 69 / Answers only from these. Otherwise: "Please ask your oncology team."
- voiceover: ""
- duration: 7s
- poster: 6s
- transition_in: crossfade
- status: animated
- src: compositions/frames/02-promise.html
- type: product_intro
- persuasion: Concretization (abstract safety → a finite stack of vetted cards)
- beat: Clarity + relief
- blueprint: titlecard-reveal

narrativeRole: Lands the thesis by beat 2 — the bot is a careful finder of vetted answers, not a free writer.
keyMessage: Every answer comes from a fixed, reviewed knowledge base.

- focal: the stack of FAQ cards with "180"
- roles: FAQ card stack = foreground subject · hormonAI wordmark = supporting (upper-left) · EN/FR split labels = supporting · cream field = background

Reproduce (titlecard-reveal): one restrained move (slide-up crossfade) per element, then a still hold.
Scene 1 (0.0–1.6s): "hormonAI" wordmark (Space Grotesk, near-black, "AI" cobalt) slides up into the upper-left; asymmetric 60/40 layout begins.
Scene 2 (1.6–3.6s): on the right 60%, a fanned stack of tinted FAQ cards fans out (`center-outward-expansion`), each card showing a short real question in body type ("Can I eat grapefruit?", "How long do I need to take hormone therapy?"); "180" counts up to its value in metric-value cobalt (`counting-dynamic-scale`) with the label "vetted FAQ answers", then "EN 111 · FR 69" fades in beneath as two pills.
Scene 3 (3.6–5.0s): on the left, the line "Answers only from these." reveals (per-word), then "Otherwise:" and the quoted decline "Please ask your oncology team." in `text-muted` italic.
Scene 4 (5.0–7.0s): held read — everything still.

## Frame 3 — Step 1: four searches

- scene: Stage for the whole process: a slim 5-step progress rail at top (Search · Merge · Rerank · Check · Answer), step 1 lit. The question card sits left; four lanes fan out to the right, each filling with ranked result chips: "Keywords", "Meaning of the question", "Question + answer", "Rewordings". Each lane ends with "top 40".
- onscreen: 1 Search / Keywords (BM25) · Meaning of the question · Question + answer · Rewordings / each returns its top 40
- voiceover: ""
- duration: 8s
- poster: 7s
- transition_in: push-slide LEFT
- status: animated
- src: compositions/frames/03-search.html
- type: feature_showcase
- persuasion: Signposting + progressive disclosure (one lane at a time)
- beat: Orientation + comprehension
- blueprint: grid-card-assemble

narrativeRole: First move of the process — the question is matched four different ways at once, by words and by meaning.
keyMessage: Four searches look for the answer from different angles.

- focal: the four search lanes
- roles: four lanes = foreground subject · question card = supporting (pinned left) · progress rail = supporting (top) · result chips = supporting

Adapt (grid-card-assemble): keep the staggered cascade signature; the grid becomes four horizontal lanes that self-populate with ranked chips.
Scene 1 (0.0–1.4s): the progress rail draws in across the top (`svg-path-draw`) and pill "1 Search" fills cobalt; step title "1 · Search" (h2) at upper-left; the question card slides in at the left of the stage.
Scene 2 (1.4–5.6s): four connector lines draw from the question card to four lanes on the right 65% of the stage, one lane per ~1s, top to bottom (`svg-path-draw` then a staggered cascade): "Keywords (BM25)", "Meaning of the question", "Question + answer", "Rewordings"; as each lane label lands, 5 small ranked chips cascade into it (#1…#5) — the real top hit "How long do I need to take hormone therapy?" appears as a chip in several lanes at different ranks (#1, #2, #1, #3).
Scene 3 (5.6–8.0s): a tag "each search returns its top 40" reveals at the lanes' right edge in `text-muted`; hold.

## Frame 4 — Step 2: merge the rankings

- scene: Same stage, rail on step 2. The four lanes from frame 3 slide together; chips that appear high in several lanes glow and rise into one merged list; a small formula tag reads "score = Σ 1 / (60 + rank)".
- onscreen: 2 Merge / Ranked high in several searches → rises to the top / score = Σ 1 / (60 + rank)
- voiceover: ""
- duration: 7s
- poster: 6s
- transition_in: push-slide LEFT
- status: animated
- src: compositions/frames/04-merge.html
- type: feature_showcase
- persuasion: Demonstration (show the mechanism running) + causal chain
- beat: "Aha"
- blueprint: grid-card-assemble

narrativeRole: Shows how the four views are combined into one ordering without trusting any single search.
keyMessage: Agreement between searches decides the shortlist.

- focal: the merged ranked list
- roles: merged list = foreground subject · four faded lanes = supporting (left, dim ~40%) · formula tag = supporting · rail = supporting

Adapt (grid-card-assemble): keep the cascade into one list; the signature is chips from several lanes converging into a single ranked column.
Scene 1 (0.0–1.2s): rail advances — "1 Search" turns to a done outline and "2 Merge" fills cobalt; title "2 · Merge" (h2); the four lanes from Frame 3 are already in place, dimmed to ~40% on the left half.
Scene 2 (1.2–4.6s): the matching chips of "How long do I need to take hormone therapy?" glow in cobalt in each lane they appear in, then all copies fly right and merge into ONE chip at #1 of a new merged column (`scale-swap-transition`); then four more chips settle below it as #2–#5 in a staggered cascade.
Scene 3 (4.6–7.0s): the line "Ranked high in several searches → rises to the top" reveals under the title (per-word), then the formula tag "score = Σ 1 / (60 + rank)" types in (Space Grotesk, cobalt-tinted pill); hold.

## Frame 5 — Step 3: rerank the top 5

- scene: Same stage, rail on step 3. The top 5 merged chips become 5 cards; a reading lens passes over each card paired with the question and stamps a relevance bar; the cards re-order and the winner lifts to #1: "How long do I need to take hormone therapy?"
- onscreen: 3 Rerank / A second model reads question + entry side by side / #1 "How long do I need to take hormone therapy?"
- voiceover: ""
- duration: 7s
- poster: 6s
- transition_in: push-slide LEFT
- status: animated
- src: compositions/frames/05-rerank.html
- type: feature_showcase
- persuasion: Progressive disclosure + comparison
- beat: Focus + confidence
- blueprint: grid-card-assemble

narrativeRole: Shows the precise, slower check that decides the best candidate.
keyMessage: The best-fitting FAQ entry is picked by reading, not just matching.

- focal: the five shortlist cards being re-ordered
- roles: five cards = foreground subject · reading lens = supporting · relevance bars = supporting · question card = supporting (pinned left) · rail = supporting

Adapt (grid-card-assemble): keep the self-assembling list; the signature move is the re-order where the best card lifts to #1.
Scene 1 (0.0–1.2s): rail: "2 Merge" done, "3 Rerank" fills; title "3 · Rerank" (h2); the five merged chips expand into five tinted cards stacked vertically on the right 60% (`card-morph-anchor`), each showing its FAQ question.
Scene 2 (1.2–4.8s): a cobalt reading bracket pairs the question card with each FAQ card in turn, top to bottom (~0.6s each), and a relevance bar fills on each card as it is read (`stat-bars-and-fills`); the line "A second model reads question + entry side by side" reveals under the title.
Scene 3 (4.8–7.0s): the cards re-order by bar length (one smooth vertical reflow) and "How long do I need to take hormone therapy?" lifts to #1 with a cobalt border and a "#1" pill; the others dim; hold.

## Frame 6 — Step 4: answer or decline

- scene: Same stage, rail on step 4. The #1 card enters a checkpoint gate that splits into three outcomes, each lighting in turn: "Clear match → answer" (cobalt), "Only in the other language → shown as-is, labelled 'only available in French'", "Nothing fits → polite decline: 'Please discuss this with your oncology team.'" Our example passes through the first.
- onscreen: 4 Check / Clear match → answer · Rare specific term (e.g. a drug name) + close meaning → answer / Only in the other language → shown as-is, never machine-translated / Nothing fits → decline: "Please discuss this with your oncology team."
- voiceover: ""
- duration: 10s
- poster: 9s
- transition_in: push-slide LEFT
- status: animated
- src: compositions/frames/06-gate.html
- type: benefit_highlight
- persuasion: Frame-then-fill (state the three exits, then light each) + rule of three
- beat: Conviction
- blueprint: kinetic-type-beats

narrativeRole: The safety core — the bot must earn the right to answer, and has honest exits when it can't.
keyMessage: When nothing really fits, hormonAI declines instead of guessing.

- focal: the checkpoint gate with three exits
- roles: gate = foreground subject · three exit paths with labels = foreground (revealed in turn) · winning card = supporting · rail = supporting

Compose: a branching diagram built in three reveals (frame-then-fill: the three exits are drawn as outlines first, then each lights in turn).
Scene 1 (0.0–1.5s): rail: "3 Rerank" done, "4 Check" fills; title "4 · Check" (h2); the #1 card slides from the left into a vertical checkpoint bar at centre-left; three exit paths draw to the right as faint outlines (`svg-path-draw`) — triptych of stacked rows.
Scene 2 (1.5–4.0s): exit 1 lights cobalt with a green check: "Clear match → answer", then its second line "or: a rare, specific term (e.g. a drug name) + close meaning → answer"; our card travels along this path and parks at its end.
Scene 3 (4.0–6.0s): exit 2 lights: "Only in the other language → shown as-is, labelled 'only available in French' — never machine-translated".
Scene 4 (6.0–10.0s): exit 3 lights: "Nothing fits → decline", followed by the quoted reply "Please discuss this with your oncology team." in a tinted card (keyword glow on "decline"); held read for the last ~2s.

## Frame 7 — Step 5: the answer

- scene: Same stage, rail on step 5. A chat bubble from "Mona" assembles: a short empathy line, then the FAQ text quoted verbatim ("…the treatment lasts 5 to 10 years, depending on…"), then a "Sources used for this answer" panel slides out beside it. A small toggle "Local LLM rewording — off by default" flips on briefly to show the same text reworded more warmly, with the note "uses only this text"; a final tag: "Survival wording guardrail".
- onscreen: 5 Answer / Verbatim from the FAQ, with its source / Optional local LLM: rewords only this text — adds nothing / Sources used for this answer
- voiceover: ""
- duration: 8s
- poster: 7s
- transition_in: push-slide LEFT
- status: animated
- src: compositions/frames/07-answer.html
- type: social_proof
- persuasion: Worked example with real content
- beat: Satisfaction + trust
- blueprint: titlecard-reveal

narrativeRole: Pays off the example — the patient sees vetted text and exactly where it came from.
keyMessage: The answer is the FAQ itself, with its source shown.

- focal: Mona's answer bubble with the verbatim FAQ text
- roles: answer bubble = foreground subject · sources panel = supporting (right) · LLM toggle = supporting · guardrail tag = supporting · rail = supporting

Adapt (titlecard-reveal): keep one restrained move per element and a still landing; extended to a three-part card build.
Scene 1 (0.0–1.4s): rail: "4 Check" done, "5 Answer" fills; title "5 · Answer" (h2); a chat bubble labelled "Mona" slides up on the left 60%, first showing the empathy line "It's understandable to want straightforward information." in `text-muted`.
Scene 2 (1.4–3.6s): the verbatim FAQ text writes in below it (per-line reveal): "How long do I need to take hormone therapy?" (bold) then "For hormone receptor-positive breast cancer, the treatment lasts 5 to 10 years, depending on individual cancer characteristics…"; a tag "Verbatim from the FAQ" appears above the bubble.
Scene 3 (3.6–5.4s): a panel "Sources used for this answer" slides out on the right 40% with the citation "How long do I need to take hormone therapy? — Section 1: General Information on Hormone Therapy".
Scene 4 (5.4–8.0s): beneath the bubble a pill toggle "Local LLM rewording" shows "off by default", flips on (`press-release-spring`, no overshoot) and the caption "rewords only this text — adds nothing" reveals; then a small tag "Survival-wording guardrail" fades in; hold.

## Frame 8 — Takeaway

- scene: The five rail steps collapse into one line; the distilled rule lands large; a quiet footer.
- onscreen: Find. Check. Answer — or decline. / Runs fully locally: models, index and the optional LLM.
- voiceover: ""
- duration: 6s
- poster: 5s
- transition_in: crossfade
- status: animated
- src: compositions/frames/08-takeaway.html
- type: branding
- persuasion: Distillation + callback (to the hook's "must not guess")
- beat: Clarity + resolve
- blueprint: kinetic-type-beats

narrativeRole: Compresses the process into one memorable rule and answers the hook.
keyMessage: hormonAI finds, checks, and answers — or honestly declines.

- focal: the distilled rule line
- roles: rule line = foreground subject · collapsed rail = supporting · footer = supporting · faint hairline grid = background

Adapt (kinetic-type-beats): keep the statement building across beats onto a calm payoff (no spring pop — smooth settle).
Scene 1 (0.0–1.4s): the five rail pills slide together into one centered pill row and fade to `text-light`.
Scene 2 (1.4–4.0s): "Find." "Check." "Answer —" land one per beat at h1 scale on one centered line (`kinetic-beat-slam`, smooth settles), then "or decline." completes the line in cobalt.
Scene 3 (4.0–6.0s): the footer "Runs fully locally: models, index and the optional LLM." reveals in body `text-muted` beneath; final held read, then the video ends on a soft fade to the cream canvas.
