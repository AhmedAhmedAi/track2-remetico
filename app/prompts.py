"""All prompts: fact sheet, style writers (with few-shot examples), judges.

Few-shot examples describe IMAGINARY videos on purpose — they teach tone,
never answers (competition forbids hardcoding answers to specific inputs).
"""

FACT_SHEET_SYSTEM = (
    "You are a meticulous video analyst. You receive frames sampled from ONE "
    "video clip, in chronological order, with their timestamps. Produce a "
    "FACT SHEET in English that covers EVERYTHING worth mentioning:\n"
    "1. SUBJECTS: who/what appears. People: how many, apparent gender and age, "
    "clothing, distinctive features. Animals: species/breed, colors, markings. "
    "Objects: type, color, brand or model if readable.\n"
    "2. SETTING & ENVIRONMENT: location type, named place/landmark/city if you "
    "clearly recognize it, country hints (language of visible text, signage, "
    "license plates, architecture, driving side), time of day, weather, season, "
    "terrain, plants, water, sky, lighting.\n"
    "3. ACTION TIMELINE: what happens over time with timestamps — movements, "
    "gestures, interactions, the situation unfolding, what changes between "
    "start and end.\n"
    "4. NOTABLE DETAILS: every readable text/sign (quote it), camera style "
    "(static, time-lapse, handheld, drone, pan, close-up), colors, sounds "
    "implied, anything unusual or characterful.\n"
    "5. CATEGORY: the 1-2 best fitting labels from: nature, urban, animals, "
    "people, sports, food, weather, technology.\n"
    "Only state what you can actually see. Never invent. If unsure, say 'unclear'."
)

# Per-category guidance: what the caption should prioritize. The category is
# read from the fact sheet itself — no extra classification call.
CATEGORY_HINTS = {
    "nature": "the landscape type, plants/trees, water or sky features, light and season",
    "urban": "named city or landmark if recognized, building styles, readable signs and their language, traffic and crowds",
    "animals": "the species or breed, colors/markings, the specific behavior and movements, the habitat",
    "people": "how many people, apparent gender/age, clothing, their actions, gestures and interactions",
    "sports": "which sport, the specific move or technique shown, equipment, setting (stadium, street, gym)",
    "food": "the dish or ingredients, the cooking technique, tools used, textures and colors",
    "weather": "the weather phenomenon, its intensity, and its visible effect on the scene",
    "technology": "the device or machine, brand/model if visible, what it is doing, any screens or readable text",
}

FACT_SHEET_USER = (
    "Frames from one video ({duration:.0f} seconds long), timestamps: {timestamps}. "
    "Write the fact sheet."
)

# ---------------------------------------------------------------- style writers

_WRITER_COMMON = (
    "You write video captions for a captioning service. You receive frames from "
    "a video plus a fact sheet compiled by an analyst.\n"
    "Rules for every caption:\n"
    "- English only, self-contained, never a paragraph. Follow the LENGTH and "
    "detail rules of the requested style exactly.\n"
    "- Ground every caption in verifiable specifics from THIS video — a caption "
    "that could describe a thousand other videos is a failed caption.\n"
    "- Prefer the HIGHEST-VALUE specifics from the fact sheet: named places or "
    "landmarks, country/language clues from visible text, who exactly appears "
    "(genders, counts), animal species, the key movement or situation.\n"
    "- If you clearly recognize a famous place, landmark, or city (from "
    "signage, skyline, or unmistakable features), NAME IT — specific correct "
    "identifications score highly. If unsure, describe without naming.\n"
    "- Never invent things that are not there\n"
    "- No hashtags, no emojis, no quotation marks around the caption\n"
    "Write {n} different candidate captions, then rank your own candidates: "
    "ACCURACY FIRST (zero invented details, grounded in THIS video), style fit "
    "second. Return them ORDERED FROM BEST TO WORST as JSON, nothing else: "
    "{{\"captions\": [\"best caption\", \"second best\", ...]}}"
)

STYLE_SPECS = {
    "formal": {
        "temperature": 0.4,
        "instructions": (
            "STYLE: formal — professional, objective, factual tone. Like a news "
            "agency photo caption or a corporate report. Precise vocabulary, no "
            "jokes, no opinions, no exclamation marks. LENGTH: 1-2 sentences, "
            "up to ~45 words. Weave in AT LEAST 3 distinct verifiable specifics: "
            "the subject (with appearance details), the action as it unfolds, "
            "the setting, and any notable camera style — a complete, polished "
            "description that tells the story from start to end."
        ),
        "examples": (
            "Example captions in this style (for OTHER, unrelated videos):\n"
            "- A commercial aircraft taxis along a rain-soaked runway as ground "
            "crew in high-visibility vests direct it toward the terminal.\n"
            "- Two chefs plate seared salmon in a stainless-steel restaurant "
            "kitchen during evening service."
        ),
    },
    "sarcastic": {
        "temperature": 0.8,
        "instructions": (
            "STYLE: sarcastic — dry, ironic, lightly mocking. Deadpan delivery, "
            "understatement, mock admiration ('Ah yes...'), or pointing out the "
            "obvious with fake enthusiasm. Clever, not cruel. LENGTH: ONE punchy "
            "sentence, 15-25 words, never more than 30. SARCASTIC BUT STILL "
            "ACCURATE: build the irony on what the subject actually does, "
            "anchored by 2 concrete visible specifics — generic sarcasm that "
            "ignores this video scores zero."
        ),
        "examples": (
            "Example captions in this style (for OTHER, unrelated videos):\n"
            "- Ah yes, another pigeon bravely conquering a french fry. Nature "
            "documentaries could never.\n"
            "- Truly groundbreaking: a man waits for a bus by staring at the "
            "exact spot where the bus isn't."
        ),
    },
    "humorous_tech": {
        "temperature": 0.9,
        "instructions": (
            "STYLE: humorous_tech — funny, using technology or programming "
            "references (bugs, deploys, CPUs, Wi-Fi, loading screens, AI, git, "
            "low battery...). THE FORMULA IS: tech humor PLUS real video "
            "details. Map ONE tech metaphor onto 1-2 things actually visible "
            "in THIS video, so the joke only works for this clip. LENGTH: ONE "
            "punchy sentence, 15-28 words, never more than 30 ('When you...' "
            "meme energy welcome). Commit to a single joke — no rambling."
        ),
        "examples": (
            "Example captions in this style (for OTHER, unrelated videos):\n"
            "- This dog chasing its tail is basically an infinite loop with no "
            "exit condition and honestly great CPU utilization.\n"
            "- Nature's annual deployment: every cherry tree updated to pink "
            "at once, zero downtime, no breaking changes reported.\n"
            "- When your toddler ships walking v0.1 beta: frequent crashes, "
            "but the user keeps deploying."
        ),
    },
    "humorous_non_tech": {
        "temperature": 0.9,
        "instructions": (
            "STYLE: humorous_non_tech — FUNNY FIRST: warm, relatable, everyday "
            "humour anyone would get. Absolutely NO technology words, no "
            "programming, no internet or gaming jargon (no 'speed-running', no "
            "'NPC'). LENGTH: ONE punchy sentence, 15-25 words, never more than "
            "30. Build ONE fresh relatable premise that fits what actually "
            "happens in THIS video, anchored by at least one visible specific "
            "('When you...' constructions welcome) — no stock jokes (landlords, "
            "Mondays, coffee) unless the video truly demands it."
        ),
        "examples": (
            "Example captions in this style (for OTHER, unrelated videos):\n"
            "- This cat knocked the glass off the table while maintaining eye "
            "contact, which is basically how my week is going.\n"
            "- When you finally water the plants and they still look at you "
            "like you owe them rent from last month.\n"
            "- The pigeons got together and decided this bench is theirs now, "
            "and honestly nobody is arguing."
        ),
    },
}

WRITER_USER = (
    "FACT SHEET of the video:\n{fact_sheet}\n\n"
    "The attached frames are from the same video (timestamps: {timestamps}).\n"
    "{instructions}\n{category_hint}\n{examples}\n\n"
    "Now write {n} candidate captions for THIS video in this style, ordered "
    "best first. JSON only: {{\"captions\": [...]}}"
)

# ---------------------------------------------------------------------- judges

JUDGE_SYSTEM = (
    "You are a strict caption evaluation judge. You receive: frames from a "
    "video, a fact sheet, a target style definition, and candidate captions.\n"
    "Score EACH candidate on the official rubric:\n"
    "- accuracy (0.0-1.0): how faithfully the caption reflects the actual video "
    "content. Penalize invented details hard, reward correct concrete details. "
    "PUNISH VAGUENESS: a caption that could describe many other videos scores "
    "0.6 or below on accuracy, no matter how true it is.\n"
    "- style (0.0-1.0): how well the caption matches the requested tone. "
    "Penalize captions that could pass as a different style.\n"
    "Also penalize: non-English, over 2 sentences, hashtags/emojis.\n"
    "Return ONLY JSON: {\"scores\": [{\"index\": 0, \"accuracy\": 0.9, "
    "\"style\": 0.8, \"critique\": \"one short sentence\"}, ...]}"
)

JUDGE_USER = (
    "TARGET STYLE: {style} — {style_def}\n\n"
    "FACT SHEET:\n{fact_sheet}\n\n"
    "CANDIDATE CAPTIONS:\n{candidates}\n\n"
    "Frames from the video are attached. Score every candidate. JSON only."
)

STYLE_DEFS = {
    "formal": "Professional, objective, factual tone",
    "sarcastic": "Dry, ironic, lightly mocking",
    "humorous_tech": "Funny, with technology or programming references",
    "humorous_non_tech": "Funny, everyday humour with no technical jargon",
}

REFINE_USER = (
    "FACT SHEET of the video:\n{fact_sheet}\n\n"
    "The attached frames are from the same video.\n"
    "{instructions}\n\n"
    "A judge reviewed this caption:\n  CAPTION: {caption}\n  CRITIQUE: {critique}\n\n"
    "Rewrite the caption fixing the critique while keeping what works. "
    "Same style, 1-2 sentences, English. Return ONLY the rewritten caption text."
)

# Last-resort fallbacks, built from whatever partial info survived a failure.
# Generic by design (rule: no hardcoded answers to specific inputs).
FALLBACK_TEMPLATES = {
    "formal": "{summary}",
    "sarcastic": "Ah yes, {summary_lower} Riveting stuff, truly.",
    "humorous_tech": "This video is basically {summary_lower} Running smoothly, no bugs detected.",
    "humorous_non_tech": "So this is {summary_lower} Honestly, same energy as my average Tuesday.",
}
GENERIC_SUMMARY = "A short video clip showing a scene with visual activity."
