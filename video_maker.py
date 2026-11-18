#!/usr/bin/env python3
"""
Script -> Documentary video maker (2D-animation-doc style).

Kay karto:
  script.txt  (scenes, blank line ne vegle kelele)
  + images/   (01.png, 02.png ... scene nusar)
  + music.mp3 (optional)
  =>  output.mp4  (voiceover + zoom animation + subtitles + music)

Lagnari goshti (tumchya laptop var):
  1) Python 3.9+
  2) ffmpeg  (ffmpeg -version ne check kara)
  3) pip install edge-tts pillow

Vapar:
  python video_maker.py                 -> GUI
  python video_maker.py my_project      -> CLI (my_project/ folder madhe script.txt pahije)
"""
import asyncio
import math
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

W, H, FPS = 1920, 1080, 25
DEFAULT_VOICE = "hi-IN-MadhurNeural"   # Hindi male. Others: hi-IN-SwaraNeural, mr-IN-ManoharNeural, mr-IN-AarohiNeural
SUB_FONT = "Noto Sans Devanagari"      # Windows var "Nirmala UI" vapra


def set_resolution(w, h):
    global W, H
    W, H = w, h
MUSIC_VOLUME = 0.12


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("Command failed:\n" + " ".join(map(str, cmd)) + "\n" + p.stderr[-1500:])
    return p.stdout


def audio_duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip())


def read_scenes(script_path):
    text = Path(script_path).read_text(encoding="utf-8").strip()
    scenes = [re.sub(r"\s+", " ", s).strip() for s in re.split(r"\n\s*\n", text)]
    return [s for s in scenes if s]


IMG_STYLE = "2D flat illustration, documentary animation style, vibrant colors, cinematic, no text, "


def parse_scene(raw):
    """'Text ... [IMG: english prompt]' -> (text, prompt)"""
    m = re.search(r"\[IMG:(.*?)\]", raw, flags=re.I | re.S)
    prompt = m.group(1).strip() if m else ""
    text = re.sub(r"\[IMG:.*?\]", "", raw, flags=re.I | re.S).strip()
    return text, prompt


def fetch_image(prompt, out, seed):
    """Free AI image (pollinations.ai, key nako). Fail zala tar False."""
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(IMG_STYLE + prompt)
           + f"?width={W}&height={H}&nologo=true&seed={seed}")
    for _ in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=60).read()
            if len(data) > 5000:
                Path(out).write_bytes(data)
                return True
        except Exception as e:
            print("! image fetch failed:", e)
    return False


async def _tts(text, voice, rate, out):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(str(out))


def make_voice(text, out, voice, rate, use_tts=True):
    """Voiceover banvto. edge-tts nasel kiva use_tts=False asel tar shant (silent) audio banto (test sathi)."""
    if use_tts:
        try:
            asyncio.run(_tts(text, voice, rate, out))
            return
        except ImportError:
            print("! edge-tts installed nahi (pip install edge-tts). Silent audio vaparto.")
    secs = max(2.0, len(text) / 14.0)  # ~14 aksharan per second
    run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
         "-t", f"{secs:.2f}", "-c:a", "libmp3lame", str(out)])


def placeholder_image(text, out):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), (20, 24, 38))
    d = ImageDraw.Draw(img)
    for y in range(H):
        c = int(20 + 40 * y / H)
        d.line([(0, y), (W, y)], fill=(c, c + 4, c + 25))
    d.text((60, 60), "Image nahi sapadli - images/ folder madhe 01.png, 02.png takkra", fill=(200, 200, 200))
    img.save(out)


def ass_time(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def make_subs(text, duration, out, words_per_line=7):
    words = text.split()
    chunks = [" ".join(words[i:i + words_per_line]) for i in range(0, len(words), words_per_line)]
    total = sum(len(c) for c in chunks) or 1
    t = 0.0
    lines = []
    for c in chunks:
        d = duration * len(c) / total
        lines.append(f"Dialogue: 0,{ass_time(t)},{ass_time(t + d)},Sub,,0,0,0,,{c}")
        t += d
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{SUB_FONT},56,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,1,2,120,120,70,1

[Events]
Format: Layer, Start, End, Style, Name, Text, MarginL, MarginR, MarginV, Effect, Text
"""
    # (Format line above keeps standard ASS field order)
    header = header.replace("Format: Layer, Start, End, Style, Name, Text, MarginL, MarginR, MarginV, Effect, Text",
                            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")
    Path(out).write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


def make_clip(img, audio, ass, duration, idx, out):
    frames = max(1, math.ceil(duration * FPS))
    zoom_in = idx % 2 == 0
    z = ("min(zoom+0.0005,1.18)" if zoom_in else "if(eq(on,1),1.18,max(zoom-0.0005,1.0))")
    vf = (f"scale={int(W * 1.67)}:-1,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
          f":d={frames}:s={W}x{H}:fps={FPS},"
          f"subtitles='{Path(ass).as_posix().replace(':', chr(92) + ':')}',format=yuv420p")
    run(["ffmpeg", "-y", "-loop", "1", "-i", str(img), "-i", str(audio),
         "-vf", vf, "-t", f"{duration + 0.4:.2f}", "-r", str(FPS),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
         "-af", "apad=pad_dur=0.4", "-shortest", str(out)])


def build(project, voice=DEFAULT_VOICE, rate="+0%", use_tts=True, log=print):
    project = Path(project)
    script = project / "script.txt"
    if not script.exists():
        raise FileNotFoundError(f"{script} sapadli nahi")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg installed nahi. ffmpeg.org varun install kara.")
    work = project / "_work"
    work.mkdir(exist_ok=True)
    imgs = sorted([p for p in (project / "images").glob("*")
                   if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]) if (project / "images").exists() else []
    scenes = read_scenes(script)
    log(f"{len(scenes)} scenes, {len(imgs)} images")
    clips = []
    for i, raw in enumerate(scenes):
        text, prompt = parse_scene(raw)
        log(f"Scene {i + 1}/{len(scenes)} ...")
        audio = work / f"a{i:03d}.mp3"
        make_voice(text, audio, voice, rate, use_tts)
        dur = audio_duration(audio)
        if imgs:
            img = imgs[min(i, len(imgs) - 1)] if len(imgs) < len(scenes) else imgs[i]
        else:
            img = work / f"ph{i:03d}.png"
            if not (prompt and fetch_image(prompt, img, i)):
                placeholder_image(text, img)
        ass = work / f"s{i:03d}.ass"
        make_subs(text, dur, ass, 4 if H > W else 7)
        clip = work / f"c{i:03d}.mp4"
        make_clip(img, audio, ass, dur, i, clip)
        clips.append(clip)
    listfile = work / "list.txt"
    listfile.write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    joined = work / "joined.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(joined)])
    out = project / "output.mp4"
    music = next(iter(list(project.glob("music.*"))), None)
    if music:
        log("Music mix karto ...")
        run(["ffmpeg", "-y", "-i", str(joined), "-stream_loop", "-1", "-i", str(music),
             "-filter_complex",
             f"[1:a]volume={MUSIC_VOLUME}[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
             "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", str(out)])
    else:
        shutil.copy(joined, out)
    log(f"Zale! -> {out}")
    return out


def gui():
    import threading
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext

    root = tk.Tk()
    root.title("Documentary Video Maker")
    folder = tk.StringVar()
    voice = tk.StringVar(value=DEFAULT_VOICE)
    tk.Label(root, text="Project folder (script.txt + images/ + music.mp3):").pack(anchor="w", padx=8, pady=(8, 0))
    row = tk.Frame(root); row.pack(fill="x", padx=8)
    tk.Entry(row, textvariable=folder, width=60).pack(side="left", fill="x", expand=True)
    tk.Button(row, text="Nivda", command=lambda: folder.set(filedialog.askdirectory() or folder.get())).pack(side="left")
    tk.Label(root, text="Voice (hi-IN-MadhurNeural, hi-IN-SwaraNeural, mr-IN-ManoharNeural, mr-IN-AarohiNeural):").pack(anchor="w", padx=8, pady=(8, 0))
    tk.Entry(root, textvariable=voice, width=40).pack(anchor="w", padx=8)
    logbox = scrolledtext.ScrolledText(root, height=12, width=80); logbox.pack(padx=8, pady=8)

    def log(msg):
        root.after(0, lambda: (logbox.insert("end", msg + "\n"), logbox.see("end")))

    def go():
        def work():
            try:
                build(folder.get(), voice.get(), log=log)
            except Exception as e:
                log("ERROR: " + str(e))
        threading.Thread(target=work, daemon=True).start()

    tk.Button(root, text="Video banva", command=go, bg="#2d7", height=2).pack(pady=(0, 8))
    root.mainloop()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        build(args[0], use_tts="--no-tts" not in sys.argv)
    else:
        gui()
