"""Rebuild the demo video timed to the narration, then mux the voiceover."""
import json, subprocess, os
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
ACCENT = (255, 90, 54)
AUDIO = "presentation/Generated Audio July 11, 2026 - 1_09PM.wav"
os.makedirs("presentation/overlays", exist_ok=True)
os.makedirs("presentation/segments2", exist_ok=True)

def font(size, bold=False):
    return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size, index=1 if bold else 0)

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-800:])

# audio duration
dur = float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
    "-of","default=noprint_wrappers=1:nokey=1", AUDIO], capture_output=True, text=True).stdout.strip())

results = {t["task_id"]: t["captions"] for t in json.load(open("test/output/results_FINAL.json"))}

# section: (kind, payload, narration_word_count)
# kinds: slide -> slide png ; demo -> (task, video, [s1,s2])
SECTIONS = [
    ("slide", "presentation/slides/slide_01.png", 13),
    ("slide", "presentation/slides/slide_02.png", 29),
    ("slide", "presentation/slides/slide_03.png", 43),
    ("demo", ("e02", "test/videos/12122308-uhd_2560_1440_24fps.mp4", ["formal","humorous_tech"]), 25),
    ("demo", ("e04", "test/videos/2697636-uhd_1920_1440_30fps.mp4", ["formal","sarcastic"]), 17),
    ("demo", ("e01", "test/videos/11785757-hd_1920_1080_30fps.mp4", ["sarcastic","humorous_non_tech"]), 19),
    ("slide", "presentation/slides/slide_04.png", 33),
    ("slide", "presentation/slides/slide_05.png", 22),
    ("slide", "presentation/slides/slide_06.png", 12),
]
total_words = sum(s[2] for s in SECTIONS)
# proportional durations, +0.3s breathing room per section, min 3.5s
durs = [max(3.5, w / total_words * dur) for _, _, w in SECTIONS]
scale = dur / sum(durs)
durs = [d * scale for d in durs]

def overlay(task, style, text, path):
    img = Image.new("RGBA", (W, H), (0,0,0,0)); d = ImageDraw.Draw(img)
    bh = 300
    d.rectangle([0, H-bh, W, H], fill=(10,12,18,220))
    d.rectangle([0, H-bh, W, H-bh+6], fill=ACCENT+(255,))
    d.text((80, H-bh+30), style, font=font(44, True), fill=ACCENT+(255,))
    f = font(46); words, line, y = text.split(), "", H-bh+105
    for w_ in words:
        t = (line+" "+w_).strip()
        if d.textlength(t, font=f) <= W-160: line = t
        else: d.text((80,y), line, font=f, fill=(240,242,248,255)); y+=62; line=w_
    if line: d.text((80,y), line, font=f, fill=(240,242,248,255))
    img.save(path)

segs = []
for i, ((kind, payload, _), sd) in enumerate(zip(SECTIONS, durs), 1):
    out = f"presentation/segments2/{i:02d}.mp4"
    if kind == "slide":
        run(["ffmpeg","-y","-v","error","-loop","1","-i",payload,"-t",f"{sd:.2f}",
             "-r","30","-vf","format=yuv420p","-c:v","libx264","-preset","fast",out])
    else:
        task, video, styles = payload
        o1 = f"presentation/overlays/n_{task}_{styles[0]}.png"
        o2 = f"presentation/overlays/n_{task}_{styles[1]}.png"
        overlay(task, styles[0], results[task][styles[0]], o1)
        overlay(task, styles[1], results[task][styles[1]], o2)
        half = sd/2
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
              f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x10121a,fps=30,format=yuv420p[b];"
              f"[b][1:v]overlay=0:0:enable='lt(t,{half:.2f})'[a];"
              f"[a][2:v]overlay=0:0:enable='gte(t,{half:.2f})'[v]")
        run(["ffmpeg","-y","-v","error","-stream_loop","-1","-t",f"{sd:.2f}","-i",video,
             "-i",o1,"-i",o2,"-filter_complex",vf,"-map","[v]",
             "-c:v","libx264","-preset","fast",out])
    segs.append(out)

with open("presentation/segments2/list.txt","w") as f:
    for s in segs: f.write(f"file '{os.path.abspath(s)}'\n")

# concat video (silent)
run(["ffmpeg","-y","-v","error","-f","concat","-safe","0","-i","presentation/segments2/list.txt",
     "-c:v","libx264","-preset","fast","presentation/_video_silent.mp4"])
# mux narration; pad/trim video to audio length
run(["ffmpeg","-y","-v","error","-i","presentation/_video_silent.mp4","-i",AUDIO,
     "-c:v","copy","-c:a","aac","-b:a","192k","-map","0:v:0","-map","1:a:0","-shortest",
     "presentation/CineGemma_demo_narrated.mp4"])
print(f"audio {dur:.1f}s | section durations: {[round(x,1) for x in durs]}")
print("done -> presentation/CineGemma_demo_narrated.mp4")
