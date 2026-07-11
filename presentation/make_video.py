"""Build the demo video: slides + real clips with actual Gemma captions overlaid."""
import json
import subprocess
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
ACCENT = (255, 90, 54)
os.makedirs("presentation/overlays", exist_ok=True)
os.makedirs("presentation/segments", exist_ok=True)

def font(size, bold=False):
    return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size,
                              index=1 if bold else 0)

results = {t["task_id"]: t["captions"]
           for t in json.load(open("test/output/results_FINAL.json"))}

# (task_id, video file, [styles to show])
DEMOS = [
    ("e02", "test/videos/12122308-uhd_2560_1440_24fps.mp4", ["formal", "humorous_tech"]),
    ("e04", "test/videos/2697636-uhd_1920_1440_30fps.mp4", ["formal", "sarcastic"]),
    ("e01", "test/videos/11785757-hd_1920_1080_30fps.mp4", ["sarcastic", "humorous_non_tech"]),
]

def make_overlay(task, style, text):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bar_h = 300
    d.rectangle([0, H - bar_h, W, H], fill=(10, 12, 18, 215))
    d.rectangle([0, H - bar_h, W, H - bar_h + 6], fill=ACCENT + (255,))
    d.text((80, H - bar_h + 30), style, font=font(44, True), fill=ACCENT + (255,))
    # wrap caption to width
    f = font(46)
    words, line, y = text.split(), "", H - bar_h + 105
    for w_ in words:
        trial = (line + " " + w_).strip()
        if d.textlength(trial, font=f) <= W - 160:
            line = trial
        else:
            d.text((80, y), line, font=f, fill=(240, 242, 248, 255))
            y += 62
            line = w_
    if line:
        d.text((80, y), line, font=f, fill=(240, 242, 248, 255))
    path = f"presentation/overlays/{task}_{style}.png"
    img.save(path)
    return path

def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)

segments = []

def slide_segment(n, slide_path, dur):
    out = f"presentation/segments/{n:02d}.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", slide_path,
         "-t", str(dur), "-r", "30", "-vf", "format=yuv420p",
         "-c:v", "libx264", "-preset", "fast", out])
    segments.append(out)

def demo_segment(n, task, video, styles):
    ov1 = make_overlay(task, styles[0], results[task][styles[0]])
    ov2 = make_overlay(task, styles[1], results[task][styles[1]])
    out = f"presentation/segments/{n:02d}.mp4"
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
          f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x10121a,fps=30,format=yuv420p[base];"
          f"[base][1:v]overlay=0:0:enable='lt(t,5)'[a];"
          f"[a][2:v]overlay=0:0:enable='gte(t,5)'[v]")
    run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-t", "10", "-i", video,
         "-i", ov1, "-i", ov2,
         "-filter_complex", vf, "-map", "[v]",
         "-c:v", "libx264", "-preset", "fast", out])
    segments.append(out)

slide_segment(1, "presentation/slides/slide_01.png", 4)
slide_segment(2, "presentation/slides/slide_02.png", 7)
slide_segment(3, "presentation/slides/slide_03.png", 9)
demo_segment(4, *DEMOS[0])
demo_segment(5, *DEMOS[1])
demo_segment(6, *DEMOS[2])
slide_segment(7, "presentation/slides/slide_04.png", 8)
slide_segment(8, "presentation/slides/slide_05.png", 8)
slide_segment(9, "presentation/slides/slide_06.png", 5)

with open("presentation/segments/list.txt", "w") as f:
    for s in segments:
        f.write(f"file '{os.path.abspath(s)}'\n")

# concat + add silent audio track (some platforms require one)
run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
     "-i", "presentation/segments/list.txt",
     "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
     "-shortest", "-c:v", "libx264", "-preset", "fast", "-c:a", "aac",
     "presentation/CineGemma_demo.mp4"])
print("done -> presentation/CineGemma_demo.mp4")
