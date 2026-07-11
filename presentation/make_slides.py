"""Render presentation slides as PNGs (for the video) and a PDF deck."""
from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1920, 1080
BG = (16, 18, 26)
ACCENT = (255, 90, 54)      # AMD-ish orange/red
SOFT = (230, 232, 240)
DIM = (150, 155, 170)
CARD = (28, 31, 42)

def font(size, bold=False):
    path = "/System/Library/Fonts/Helvetica.ttc"
    try:
        return ImageFont.truetype(path, size, index=1 if bold else 0)
    except Exception:
        return ImageFont.load_default()

def new_slide():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, H-14, W, H], fill=ACCENT)
    return img, d

def center(d, text, y, f, fill=SOFT):
    w = d.textlength(text, font=f)
    d.text(((W - w) / 2, y), text, font=f, fill=fill)

def wrap(d, text, x, y, f, max_w, fill=SOFT, lh=1.35):
    words, line, yy = text.split(), "", y
    for word in words:
        trial = (line + " " + word).strip()
        if d.textlength(trial, font=f) <= max_w:
            line = trial
        else:
            d.text((x, yy), line, font=f, fill=fill)
            yy += int(f.size * lh)
            line = word
    if line:
        d.text((x, yy), line, font=f, fill=fill)
        yy += int(f.size * lh)
    return yy

os.makedirs("presentation/slides", exist_ok=True)
slides = []

# ---- Slide 1: title
img, d = new_slide()
center(d, "CineGemma", 330, font(150, True), ACCENT)
center(d, "An All-Gemma Video Captioning Agent", 530, font(60), SOFT)
center(d, "AMD Developer Hackathon: ACT II  |  Track 2: Video Captioning", 660, font(40), DIM)
center(d, "Powered by Google DeepMind Gemma 4 31B on Fireworks AI", 730, font(40), DIM)
slides.append(img)

# ---- Slide 2: the task
img, d = new_slide()
d.text((120, 100), "The Task", font=font(80, True), fill=ACCENT)
y = 280
for line in [
    "Watch any video clip (30 seconds to 2 minutes) and write a caption in 4 styles:",
]:
    y = wrap(d, line, 120, y, font(48), W-240)
y += 30
for s, desc in [("formal", "professional, objective, factual"),
                ("sarcastic", "dry, ironic, lightly mocking"),
                ("humorous_tech", "funny, with technology and programming references"),
                ("humorous_non_tech", "funny, everyday humour, zero jargon")]:
    d.rounded_rectangle([120, y, W-120, y+95], 18, fill=CARD)
    d.text((160, y+22), s, font=font(44, True), fill=ACCENT)
    d.text((640, y+26), desc, font=font(40), fill=SOFT)
    y += 125
y += 20
wrap(d, "Judged by an LLM on caption accuracy (0-1) and style match (0-1) across ~12 hidden clips.",
     120, y, font(44), W-240, fill=DIM)
slides.append(img)

# ---- Slide 3: architecture
img, d = new_slide()
d.text((120, 90), "How It Works: a Team of Gemma Agents", font=font(72, True), fill=ACCENT)
steps = [
    ("1. Motion-adaptive frame sampling", "frame budget spent where the action is; first and last frames always kept"),
    ("2. Gemma vision fact sheet", "subjects, setting, action timeline, visible signs, camera style, landmarks"),
    ("3. Four Gemma style writers (parallel)", "6 candidate captions each, style-tuned temperatures, detail-density rules"),
    ("4. Four Gemma judges (parallel)", "score every candidate on the official rubric while looking at the frames"),
    ("5. Gemma refine pass", "weak winners get one rewrite using the judge's critique"),
]
y = 240
for title, desc in steps:
    d.rounded_rectangle([120, y, W-120, y+130], 18, fill=CARD)
    d.text((160, y+18), title, font=font(46, True), fill=SOFT)
    d.text((160, y+76), desc, font=font(36), fill=DIM)
    y += 155
slides.append(img)

# ---- Slide 4: engineering
img, d = new_slide()
d.text((120, 90), "Engineering for the Rules", font=font(72, True), fill=ACCENT)
rows = [
    ("12 videos in parallel", "under 3 minutes total (limit: 10)"),
    ("Every API call capped at 25s", "rule: under 30 seconds per request"),
    ("Structured JSON enforced server-side", "malformed output is impossible"),
    ("Gemma thinking mode tuned off", "7-second calls, zero timeouts"),
    ("Triple fallback ladder + watchdog", "a valid caption for every style, every clip, always"),
    ("245 MB linux/amd64 image", "limit: 10 GB"),
]
y = 240
for a, b in rows:
    d.rounded_rectangle([120, y, W-120, y+105], 18, fill=CARD)
    d.text((160, y+28), a, font=font(42, True), fill=SOFT)
    d.text((1080, y+32), b, font=font(36), fill=DIM)
    y += 128
slides.append(img)

# ---- Slide 5: results
img, d = new_slide()
d.text((120, 90), "Tested Like the Real Evaluation", font=font(72, True), fill=ACCENT)
y = 250
for line in [
    "12 varied test clips: nature, urban, animals, people, sports, food, weather, technology.",
    "Blind LLM judging with the official rubric, repeated across multiple rounds.",
]:
    y = wrap(d, line, 120, y, font(46), W-240)
y += 40
stats = [("0.85+", "blind-judged rubric score"), ("48/48", "captions delivered, zero failures"),
         ("2:57", "full run of 12 videos"), ("100%", "Gemma, end to end")]
x = 120
for num, label in stats:
    d.rounded_rectangle([x, y, x+400, y+250], 22, fill=CARD)
    tw = d.textlength(num, font=font(76, True))
    d.text((x + (400-tw)/2, y+45), num, font=font(76, True), fill=ACCENT)
    f = font(32)
    words_w = d.textlength(label, font=f)
    d.text((x + (400-words_w)/2 if words_w < 380 else x+20, y+160), label, font=f, fill=DIM)
    x += 430
slides.append(img)

# ---- Slide 6: closing
img, d = new_slide()
center(d, "CineGemma", 300, font(110, True), ACCENT)
center(d, "Google DeepMind Gemma 4 31B  •  Fireworks AI  •  Docker", 500, font(46), SOFT)
center(d, "docker.io/aa2003/amd-track2-captioner:latest", 590, font(42), DIM)
center(d, "Every caption computed fresh. Nothing hardcoded. Built for the hidden set.", 700, font(40), DIM)
slides.append(img)

for i, s in enumerate(slides, 1):
    s.save(f"presentation/slides/slide_{i:02d}.png")
slides[0].save("presentation/CineGemma_slides.pdf", save_all=True,
               append_images=slides[1:], resolution=120)
print(f"{len(slides)} slides -> presentation/slides/*.png + CineGemma_slides.pdf")
