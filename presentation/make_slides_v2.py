"""Slide deck v2: light professional theme, denser content, distinct from video."""
from PIL import Image, ImageDraw, ImageFont
import json

W, H = 1920, 1080
BG = (247, 248, 251)
INK = (23, 32, 46)          # near-black navy
NAVY = (26, 58, 107)
TEAL = (11, 122, 138)
DIM = (95, 105, 122)
CARD = (255, 255, 255)
LINE = (222, 227, 236)

def font(size, bold=False):
    return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size,
                              index=1 if bold else 0)

def new_slide(title=None, subtitle=None):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 26, H], fill=NAVY)
    d.rectangle([26, 0, 34, H], fill=TEAL)
    if title:
        d.text((110, 70), title, font=font(66, True), fill=NAVY)
        d.line([110, 170, W-110, 170], fill=LINE, width=3)
    if subtitle:
        d.text((110, 178), subtitle, font=font(34), fill=DIM)
    return img, d

def card(d, x0, y0, x1, y1):
    d.rounded_rectangle([x0, y0, x1, y1], 16, fill=CARD, outline=LINE, width=2)

def wrap(d, text, x, y, f, max_w, fill=INK, lh=1.32):
    words, line, yy = text.split(), "", y
    for word in words:
        t = (line + " " + word).strip()
        if d.textlength(t, font=f) <= max_w:
            line = t
        else:
            d.text((x, yy), line, font=f, fill=fill); yy += int(f.size*lh); line = word
    if line:
        d.text((x, yy), line, font=f, fill=fill); yy += int(f.size*lh)
    return yy

slides = []

# 1 ---- title
img, d = new_slide()
d.text((110, 210), "CineGemma", font=font(140, True), fill=NAVY)
d.rectangle([116, 380, 700, 396], fill=TEAL)
d.text((110, 450), "A Multi-Agent Video Captioning System Built Entirely on Gemma 4",
       font=font(50), fill=INK)
d.text((110, 560), "AMD Developer Hackathon: ACT II   |   Track 2: Video Captioning",
       font=font(36), fill=DIM)
d.text((110, 620), "Google DeepMind Gemma 4 31B IT, served on a dedicated Fireworks AI deployment",
       font=font(36), fill=DIM)
# team card
card(d, 110, 720, W-110, 940)
d.text((150, 748), "Team Remetico", font=font(46, True), fill=NAVY)
d.text((150, 822), "Ahmed Ahmed Abdlehadi      Ahmed Saad Elmenawy", font=font(38, True), fill=INK)
d.text((150, 878), "A team focused on developing practical AI solutions, rather than just following trends.",
       font=font(32), fill=DIM)
d.text((110, 985), "docker.io/aa2003/amd-track2-captioner:latest", font=font(32, True), fill=TEAL)
slides.append(img)

# 2 ---- challenge & judging
img, d = new_slide("The Challenge", "Official task and judging criteria, Track 2")
y = 250
card(d, 110, y, W-110, y+210)
wrap(d, "Input: a JSON list of video URLs (clips of 30 seconds to 2 minutes) with requested "
        "styles. Output: one caption per requested style per clip, written to results.json. "
        "The evaluation set is hidden: about 12 clips spanning nature, urban, animals, people, "
        "sports, food, weather and technology.", 150, y+35, font(38), W-330)
y += 260
d.text((110, y), "Scoring by an LLM judge, per caption:", font=font(42, True), fill=NAVY); y += 80
for name, desc in [("Caption accuracy (0 to 1)", "how faithfully the caption reflects the actual video content"),
                   ("Style match (0 to 1)", "how well the caption lands the requested tone")]:
    card(d, 110, y, W-110, y+100)
    d.text((150, y+28), name, font=font(40, True), fill=TEAL)
    d.text((820, y+32), desc, font=font(36), fill=INK)
    y += 130
y += 20
wrap(d, "Hard limits: 10 minutes total runtime, under 30 seconds per request, container ready "
        "in 60 seconds, public linux/amd64 image under 10 GB, English only, no hardcoding.",
     110, y, font(36), W-260, fill=DIM)
slides.append(img)

# 3 ---- architecture
img, d = new_slide("Architecture: Five Gemma Stages", "All clips processed in parallel; styles fan out per clip")
stages = [
    ("Frame sampling", "Motion-adaptive: 1 fps thumbnails are scored for motion; the frame budget "
     "(6 to 24, scaling with duration) concentrates where action happens. First and last frames always kept."),
    ("Fact sheet (Gemma vision)", "All frames in chronological order with timestamps. Subjects, setting, "
     "action timeline, visible text and signs, camera style, recognized landmarks."),
    ("4 style writers (parallel)", "Each style gets a dedicated Gemma call: frames + fact sheet + few-shot "
     "examples + style-tuned temperature (0.4 formal, 0.9 humor). Six candidate captions per style."),
    ("4 judges (parallel)", "Each judge sees the frames and scores every candidate with the official rubric. "
     "Vague or invented captions are punished; the best candidate wins."),
    ("Refine pass", "Winners scoring under 0.85 get one rewrite driven by the judge's critique."),
]
y = 235
for i, (t, desc) in enumerate(stages, 1):
    card(d, 110, y, W-110, y+140)
    d.ellipse([140, y+42, 196, y+98], fill=TEAL)
    n = font(40, True)
    d.text((158 if i < 10 else 150, y+48), str(i), font=n, fill=(255,255,255))
    d.text((230, y+18), t, font=font(40, True), fill=NAVY)
    wrap(d, desc, 230, y+70, font(30), W-400, fill=DIM, lh=1.2)
    y += 160
slides.append(img)

# 4 ---- gemma best practices
img, d = new_slide("Using Gemma 4 the Right Way", "Best practices that shaped the system")
rows = [
    ("Thinking mode tuned off", "Gemma 4 reasons before answering by default. For 2-sentence captions this "
     "cost 30+ second calls. reasoning_effort none gives 7-second calls with identical blind-judged quality."),
    ("Server-enforced structured output", "Writers and judges must return JSON matching a schema. "
     "Malformed output became impossible, removing our most common failure."),
    ("Native-resolution frames", "Frames resized to 768 px, matching Gemma's vision encoder. "
     "Up to 24 frames per clip, 14 to each writer, all under the API image limits."),
    ("Per-style temperatures and few-shots", "Precision for formal (0.4), freedom for humor (0.9), "
     "hand-written style examples about imaginary videos, so tone is taught without hardcoding answers."),
    ("Confident landmark naming", "Gemma names Shibuya Crossing or the New York City skyline when it is sure, "
     "and describes without naming when it is not."),
]
y = 235
for t, desc in rows:
    card(d, 110, y, W-110, y+140)
    d.text((150, y+18), t, font=font(38, True), fill=TEAL)
    wrap(d, desc, 150, y+68, font(30), W-320, fill=INK, lh=1.2)
    y += 160
slides.append(img)

# 5 ---- reliability
img, d = new_slide("Reliability: Built to Never Fail", "Every failure mode has a planned answer")
rows = [
    ("Parallel everything", "12 clips at once; total time equals the slowest clip, not the sum. "
     "Task starts staggered 1.5 s apart to avoid burst overload."),
    ("25-second hard cap per request", "Under the official 30-second rule. Retries with backoff, "
     "then an always-on serverless fallback model."),
    ("Triple fallback ladder", "Full writer with frames, then a fast text-only writer from the fact sheet, "
     "then a style template. A caption exists for every style, every clip, always."),
    ("Global watchdog at 8.3 minutes", "If anything hangs, best-available results are written and the "
     "container exits cleanly. The 10-minute wall is unreachable by design."),
    ("Guaranteed valid output", "results.json written atomically, exact schema, exit code 0, "
     "verified in crash tests with dead URLs and forced failures."),
]
y = 235
for t, desc in rows:
    card(d, 110, y, W-110, y+140)
    d.text((150, y+18), t, font=font(38, True), fill=TEAL)
    wrap(d, desc, 150, y+68, font(30), W-320, fill=INK, lh=1.2)
    y += 160
slides.append(img)

# 6 ---- benchmark methodology
img, d = new_slide("How We Tested", "The evaluation was rehearsed before submitting")
y = 240
for para in [
    "We assembled 12 fresh test clips matching the hidden set's brief: nature, urban, animals, people, "
    "sports, food, weather and technology, 6 seconds to 2 minutes long.",
    "Blind LLM judging: independent judges saw the video frames plus anonymized captions from two systems "
    "at a time, and scored every caption with the official rubric (accuracy and style, 0 to 1).",
    "We benchmarked against a frontier-model captioning agent (Claude) as a quality ceiling, ran three "
    "iteration rounds, and re-verified after every engineering change.",
]:
    card(d, 110, y, W-110, y+170)
    wrap(d, para, 150, y+32, font(36), W-330, fill=INK)
    y += 205
y += 15
d.text((110, y), "Three iteration rounds, each change verified by blind judging before shipping.",
       font=font(44, True), fill=NAVY)
slides.append(img)

# 7 ---- results
img, d = new_slide("Results", "Final configuration, 12-clip dress rehearsal")
stats = [("12", "clips, 8 categories"), ("48/48", "captions, zero failures"),
         ("2:57", "total for 12 videos"), ("7 s", "typical Gemma call")]
x = 110
for num, label in stats:
    card(d, x, 240, x+400, 470)
    tw = d.textlength(num, font=font(84, True))
    d.text((x+(400-tw)/2, 285), num, font=font(84, True), fill=TEAL)
    lw = d.textlength(label, font=font(30))
    d.text((x+(400-lw)/2, 400), label, font=font(30), fill=DIM)
    x += 430
try:
    caps = {t["task_id"]: t["captions"] for t in json.load(open("test/output/results_FINAL.json"))}
    examples = [("formal", caps["e04"]["formal"]), ("humorous_tech", caps["e02"]["humorous_tech"])]
except Exception:
    examples = []
y = 530
d.text((110, y), "Real output from the system:", font=font(40, True), fill=NAVY); y += 70
for style, text in examples:
    card(d, 110, y, W-110, y+180)
    d.text((150, y+20), style, font=font(34, True), fill=TEAL)
    wrap(d, text, 150, y+70, font(30), W-320, fill=INK, lh=1.25)
    y += 210
slides.append(img)

# 8 ---- compliance
img, d = new_slide("Rules Compliance", "Every limit, measured")
rows = [
    ("Total runtime", "10 min limit", "2:57 measured"),
    ("Response per request", "under 30 s", "25 s hard cap, ~7 s typical"),
    ("Container ready", "60 s", "about 2 s"),
    ("Image size", "10 GB max", "245 MB"),
    ("Architecture", "linux/amd64", "built with buildx, verified"),
    ("Output", "valid JSON, all styles", "guaranteed by design, validated"),
    ("Language", "English only", "enforced and checked"),
    ("Hardcoding", "forbidden", "every caption computed fresh"),
]
y = 240
d.text((150, y), "Requirement", font=font(34, True), fill=DIM)
d.text((820, y), "Rule", font=font(34, True), fill=DIM)
d.text((1320, y), "CineGemma", font=font(34, True), fill=DIM)
y += 60
for a, b, c in rows:
    card(d, 110, y, W-110, y+80)
    d.text((150, y+22), a, font=font(34, True), fill=INK)
    d.text((820, y+24), b, font=font(32), fill=DIM)
    d.text((1320, y+22), c, font=font(32, True), fill=TEAL)
    y += 92
slides.append(img)

# 9 ---- closing
img, d = new_slide()
d.text((110, 210), "CineGemma", font=font(110, True), fill=NAVY)
d.rectangle([116, 350, 580, 362], fill=TEAL)
y = 430
for line in ["100% Gemma, end to end: one vision analyst, four writers, four judges, one editor.",
             "Engineered for the hidden set: adaptive sampling, structured output, triple fallbacks.",
             "Rehearsed like the real evaluation: blind rubric judging on 12 varied clips."]:
    d.text((110, y), line, font=font(38), fill=INK); y += 68
y += 20
card(d, 110, y, W-110, y+230)
d.text((150, y+28), "Team Remetico", font=font(46, True), fill=NAVY)
d.text((150, y+100), "Ahmed Ahmed Abdlehadi      Ahmed Saad Elmenawy", font=font(38, True), fill=INK)
d.text((150, y+158), "A team focused on developing practical AI solutions, rather than just following trends.",
       font=font(32), fill=DIM)
d.text((110, 970), "docker.io/aa2003/amd-track2-captioner:latest   |   Gemma 4 31B  |  Fireworks AI  |  Docker",
       font=font(30, True), fill=TEAL)
slides.append(img)

for i, s in enumerate(slides, 1):
    s.save(f"presentation/slides_v2_{i:02d}.png")
slides[0].save("presentation/CineGemma_slides_v2.pdf", save_all=True,
               append_images=slides[1:], resolution=120)
print(f"{len(slides)} slides -> presentation/CineGemma_slides_v2.pdf")
