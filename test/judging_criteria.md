# Internal Judging Criteria — calibrated to the official Track 2 samples

Judge each caption on two axes, 0.0-1.0 each. Final = (accuracy + style) / 2.
Calibrated against the organizers' published focus list and reference examples
(July 2026). Apply these rules exactly; do not invent extra requirements.

## Official focus (weigh in this order)
1. Accurate captions — no invented objects, actions, places, or text
2. Correct requested style
3. Specific video details — the caption should fit THIS video
4. No major hallucinations — a single invented load-bearing fact caps accuracy at 0.4
5. Complete output — empty/near-empty caption = 0

## Accuracy axis (all styles)
- 1.0: everything checkable is correct AND at least one detail pins it to this
  exact video (named place, specific object/color/action, readable sign)
- 0.8: correct, mostly specific, but one soft/unverifiable claim
- 0.6: correct but visibly generic — could describe many similar videos
  (this is the ceiling for vague captions in formal/sarcastic/humorous_tech)
- 0.4 or below: contains an invented detail or contradicts the video
- humorous_non_tech EXCEPTION: the official checklist does not demand video
  details for this style. A relatable joke loosely tied to the scene with one
  real anchor can still reach 0.8 accuracy if nothing is wrong. Still punish
  contradictions and inventions hard.

## Style axis, per style (calibrated to the reference examples)
- formal ("clear and professional"): news-agency tone, precise vocabulary,
  no jokes/opinions/exclamations. Detail-rich 1-2 sentences is IDEAL (the
  official formal references run 12-60 words). Do NOT penalize length if it
  stays 1-2 tight sentences.
- sarcastic ("sarcastic but still accurate"): dry, deadpan, ironic one-liner
  built on the actual content. 'Ah yes...', mock admiration, understatement
  are the reference register. Ideal length 12-25 words; rambling loses points.
  Sarcasm that ignores the video content caps at 0.5 style.
- humorous_tech ("tech humor plus real video details"): ONE tech metaphor
  mapped onto real visible details, so the joke only works for this clip.
  Reference register: "Nature's annual deployment: all leaf nodes updated to
  yellow simultaneously" / "When you..." constructions. Ideal 12-28 words.
  A tech joke that could caption any video caps at 0.5 style.
- humorous_non_tech ("funny, everyday humour with no technical jargon"):
  FUNNY and relatable comes first. Any tech/programming/internet/gaming word
  caps style at 0.3. Reference register: "When you finally hit the beach after
  a long week, but the ocean waves say 'not today, buddy.'" Ideal 10-25 words.
  Warmth and relatability beat cleverness.

## Length calibration (all reference examples measured)
- formal: 12-60 words acceptable, detail preferred
- other styles: 10-30 words; over ~35 words = -0.1 style; paragraph-like = -0.2

## Process
- LOOK at the video frames before scoring anything
- Score each caption independently; never compare to other candidates
- Never try to guess which system wrote a caption
