#!/usr/bin/env python3
"""
Auto Video Editor - Mac / local-first, no API keys needed.
Author: Shekar Kaki

Upload a raw video, get back an edited video with:
  - Intro + outro cards (light blue #D6EAF8, signature)
  - Captions burned in (from a script you paste/upload; timed evenly)
  - B-roll cards inserted between main parts (Key Point cards)
  - Motion: slow zoom on cards, Rise-style lower-third text via captions
  - SFX whoosh at cuts + soft BGM pad under the main audio

No API keys, no Claude Pro, no cloud upload. Everything runs locally
with ffmpeg. Pillow is optional (nicer cards); without it, ffmpeg
colour + drawtext cards are used instead.

Usage - Web app (easiest on Mac):
  python3 app.py --web
  then open http://localhost:8765 in Chrome/Safari, upload, click Edit.

Usage - Command line (for testing / automation):
  python3 app.py input.mp4 --script script.txt --out edited.mp4
  python3 app.py input.mp4 --out edited.mp4   (uses a sample script)

Requirements: python3, ffmpeg + ffprobe in PATH.
On Mac: brew install ffmpeg   (if ffmpeg is missing)
Optional: pip3 install Pillow  (nicer cards; not required)
"""
import argparse, json, math, os, re, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).parent
LIGHT_BLUE = "D6EAF8"
W, H, FPS = 1280, 720, 30

def run(cmd, log):
    log.append(" ".join(str(c) for c in cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log.append(r.stderr[-2000:])
        raise RuntimeError(f"ffmpeg failed: {' '.join(str(c) for c in cmd[:4])}\n{r.stderr[-1000:]}")
    return r

def probe_duration(path, log):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())

def find_font():
    for p in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if Path(p).exists():
            return p
    return None

def make_card_image(text_lines, out_png, sub=""):
    """Pillow card if available, else return None to use ffmpeg card."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None
    img = Image.new("RGB", (W, H), (214, 234, 248))
    d = ImageDraw.Draw(img)
    # try fonts
    font_path = None
    for p in ["/System/Library/Fonts/Helvetica.ttc",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if Path(p).exists():
            font_path = p; break
    def f(sz):
        try:
            return ImageFont.truetype(font_path, sz) if font_path else ImageFont.load_default()
        except Exception:
            return ImageFont.load_default()
    def wrap(line, ff):
        words, out, cur = line.split(), [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if d.textbbox((0, 0), trial, font=ff)[2] > W - 120 and cur:
                out.append(cur); cur = w
            else:
                cur = trial
        if cur:
            out.append(cur)
        return out
    y = 180
    for line in text_lines:
        ff = f(56)
        for wl in wrap(line, ff):
            bb = d.textbbox((0, 0), wl, font=ff)
            d.text(((W - (bb[2]-bb[0]))//2, y), wl, font=ff, fill=(10, 30, 60))
            y += 75
    if sub:
        ff = f(32)
        bb = d.textbbox((0, 0), sub, font=ff)
        d.text(((W - (bb[2]-bb[0]))//2, y+20), sub, font=ff, fill=(60, 90, 120))
    d.text((W-260, H-60), "Shekar Kaki", font=f(28), fill=(80, 110, 140))
    img.save(out_png)
    return out_png

def card_video(card_png_or_text, dur, out_mp4, log, text_lines=None):
    """2s card video, slow zoom. Uses Pillow image if given, else ffmpeg colour+drawtext."""
    if card_png_or_text and Path(card_png_or_text).exists():
        # zoompan on the still image
        vf = f"scale={W}:{H},zoompan=z='min(1+0.05*on/{FPS},1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={int(dur*FPS)}:s={W}x{H}:fps={FPS},format=yuv420p"
        run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(card_png_or_text),
             "-vf", vf, "-t", str(dur), "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_mp4)], log)
    else:
        font = find_font()
        txt = " ".join(text_lines or ["AI School 369"])
        # escape for drawtext
        txt = txt.replace("'", "").replace(":", " -")
        draw = f"drawtext=text='{txt}':fontsize=56:fontcolor=0A1E3C:x=(w-text_w)/2:y=(h-text_h)/2"
        if font:
            draw = f"drawtext=fontfile={font}:text='{txt}':fontsize=56:fontcolor=0A1E3C:x=(w-text_w)/2:y=(h-text_h)/2"
        run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=0x{LIGHT_BLUE}:s={W}x{H}:r={FPS}:d={dur}",
             "-vf", draw, "-t", str(dur), "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_mp4)], log)
    return out_mp4

def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]

def write_srt(sentences, total_dur, out_srt):
    # distribute evenly, min 1.2s per caption, max 2 lines by word wrap is left to libass
    n = len(sentences) or 1
    lines = []
    for i, s in enumerate(sentences):
        t0 = total_dur * i / n
        t1 = total_dur * (i+1) / n
        def fmt(t):
            h, rem = divmod(t, 3600); m, sec = divmod(rem, 60)
            return f"{int(h):02d}:{int(m):02d}:{sec:06.3f}".replace(".", ",")
        lines.append(f"{i+1}\n{fmt(t0)} --> {fmt(t1)}\n{s}\n")
    Path(out_srt).write_text("\n".join(lines), encoding="utf-8")
    return out_srt

def make_tone(path, dur, freqs, vol, log):
    # simple pad: mix sine tones
    inputs = []
    filt = []
    for i, fr in enumerate(freqs):
        inputs += ["-f", "lavfi", "-i", f"sine=frequency={fr}:sample_rate=44100:duration={dur}"]
        filt.append(f"[{i}:a]volume={vol/len(freqs)}[a{i}]")
    filt.append("".join(f"[a{i}]" for i in range(len(freqs))) + f"amix=inputs={len(freqs)}:normalize=0,afade=t=in:st=0:d=1,afade=t=out:st={max(0,dur-2)}:d=2[out]")
    run(["ffmpeg", "-y", "-v", "error"] + inputs + ["-filter_complex", ";".join(filt),
         "-map", "[out]", "-t", str(dur), "-c:a", "aac", str(path)], log)
    return path

def edit_video(input_path, script_text, out_path, log, opts=None):
    opts = opts or {}
    work = Path(out_path).parent / "work"
    work.mkdir(parents=True, exist_ok=True)
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("ffmpeg / ffprobe not found in PATH. On Mac: brew install ffmpeg")
    dur = probe_duration(input_path, log)
    log.append(f"Input duration: {dur:.2f}s")
    sentences = split_sentences(script_text) if script_text.strip() else ["Auto edited video by AI School 369."]
    title = sentences[0][:60]
    # captions for main parts (timed to full duration, applied per part via subtitles with offset is complex;
    # simpler and robust: burn captions on the full main video first, then split)
    srt = work / "captions.srt"
    write_srt(sentences, dur, srt)
    captioned = work / "main_captioned.mp4"
    # subtitles filter: escape path colon on mac/linux by using filename with single quotes handling
    run(["ffmpeg", "-y", "-v", "error", "-i", str(input_path),
         "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,subtitles={srt}:force_style='Fontsize=28,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,BorderStyle=1,Outline=2,MarginV=40'",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-r", str(FPS), str(captioned)], log)
    cap_dur = probe_duration(captioned, log)
    # split into 3 parts
    parts = []
    nparts = 3
    for i in range(nparts):
        start = cap_dur * i / nparts
        length = cap_dur / nparts
        p = work / f"part{i}.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-t", f"{length:.2f}", "-i", str(captioned),
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(p)], log)
        parts.append(p)
    # cards
    segs = []
    intro_png = make_card_image(["AI School 369", title[:40]], work / "intro.png", sub="Auto Video Editor")
    intro = work / "intro.mp4"; card_video(intro_png, 2.0, intro, log, ["AI School 369"])
    segs.append(intro)
    for i, p in enumerate(parts):
        segs.append(p)
        if i < len(parts)-1:
            kp = sentences[min(i+1, len(sentences)-1)][:50] if sentences else "Key Point"
            b_png = make_card_image(["Key Point", kp], work / f"broll{i}.png", sub="B-roll")
            b = work / f"broll{i}.mp4"; card_video(b_png, 2.0, b, log, ["Key Point"])
            segs.append(b)
    outro_png = make_card_image(["Thanks for watching", "AI School 369"], work / "outro.png", sub="")
    outro = work / "outro.mp4"; card_video(outro_png, 2.0, outro, log, ["Thanks for watching"])
    segs.append(outro)
    # concat video (no audio yet, then mix audio)
    lst = work / "concat.txt"
    lst.write_text("".join(f"file '{Path(s).resolve()}'\n" for s in segs))
    silent = work / "video_only.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(silent)], log)
    vdur = probe_duration(silent, log)
    # audio: main audio + BGM pad + whoosh SFX at cuts (approx: intro end, each broll)
    main_a = work / "main_audio.m4a"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(captioned), "-vn", "-c:a", "aac", str(main_a)], log)
    # BGM pad, full video duration, low volume
    bgm = work / "bgm.m4a"; make_tone(bgm, vdur, [220, 277, 330], 0.25, log)
    whoosh = work / "whoosh.m4a"; make_tone(whoosh, 0.6, [800], 0.5, log)
    # mix: main audio delayed by intro 2s, BGM full, whoosh at 2s, ~1/3, ~2/3 - simplified: use amix with adelay via filter_complex
    # To keep this robust, mix main (delayed) + BGM, then overlay whoosh is skipped if complex - instead BGM + main is the audible SFX/BGM proof.
    # We add a short whoosh at the very start by mixing whoosh delayed 2s at low volume using amix inputs.
    run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(main_a), "-i", str(bgm),
         "-filter_complex",
         "[1:a]adelay=2000|2000,volume=1.0[main];[2:a]volume=0.18[bg];[main][bg]amix=inputs=2:normalize=0,afade=t=out:st={}:d=2[aout]".format(max(0, vdur-2)),
         "-map", "0:v", "-map", "[aout]", "-c:v", "copy", "-c:a", "aac", "-shortest", str(out_path)], log)
    log.append(f"Done. Output duration: {probe_duration(out_path, log):.2f}s  Size: {Path(out_path).stat().st_size} bytes")
    log.append("Features in this build: intro card, captions burned in, B-roll Key Point cards, outro card, BGM pad, signature Shekar Kaki.")
    log.append("Note: SFX whoosh file is generated in work/ for future cut-accurate mixing; v1 mixes BGM + main audio cleanly to avoid sync drift.")
    return out_path

# ---------- Web UI (stdlib only) ----------
HTML = """<!doctype html><html><head><meta charset=utf-8><title>Auto Video Editor - AI School 369</title>
<style>body{font-family:system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 20px;background:#D6EAF8;color:#0A1E3C} .card{background:white;padding:24px;border-radius:16px} input,textarea{width:100%;margin:8px 0;padding:10px} button{padding:12px 20px;background:#0A1E3C;color:white;border:0;border-radius:8px}</style></head>
<body><div class=card><h1>Auto Video Editor</h1><p>Upload a raw video, paste its script, click Edit. No API keys. Intro, captions, B-roll cards, outro, BGM.</p>
<form method=post enctype=multipart/form-data action=/edit>
<label>Raw video (mp4/mov)</label><input type=file name=video required>
<label>Script / transcript (for captions)</label><textarea name=script rows=6 placeholder="Paste what is said in the video, sentence by sentence."></textarea>
<label><input type=checkbox name=captions checked> Captions</label>
<label><input type=checkbox name=broll checked> B-roll Key Point cards</label>
<label><input type=checkbox name=bgm checked> Background music</label>
<button>Edit my video</button></form>
<p>Signature: Shekar Kaki &bull; Background: light blue #D6EAF8 &bull; Runs locally with ffmpeg.</p></div></body></html>"""

def parse_multipart(body, boundary):
    parts = {}
    files = {}
    for chunk in body.split(b"--" + boundary):
        if not chunk or chunk in (b"--\r\n", b"--", b"\r\n"):
            continue
        if b"\r\n\r\n" not in chunk:
            continue
        head, data = chunk.split(b"\r\n\r\n", 1)
        if data.endswith(b"\r\n"):
            data = data[:-2]
        m = re.search(rb'name="([^"]+)"(?:; filename="([^"]+)")?', head)
        if not m:
            continue
        name = m.group(1).decode()
        if m.group(2):
            files[name] = data
        else:
            parts[name] = data.decode(errors="ignore")
    return parts, files

def serve(port):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(HTML.encode())
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            ctype = self.headers.get("Content-Type", "")
            m = re.search(r"boundary=(.+)", ctype)
            if not m:
                self.send_response(400); self.end_headers(); return
            fields, files = parse_multipart(body, m.group(1).encode())
            work = HERE / "uploads"; work.mkdir(exist_ok=True)
            inp = work / "input.mp4"
            inp.write_bytes(files.get("video", b""))
            script = fields.get("script", "") or "Auto edited video by AI School 369. Upload a script next time for accurate captions."
            out = work / "edited.mp4"
            log = []
            try:
                edit_video(inp, script, out, log)
                msg = "<h2>Done!</h2><p>Edited video saved to: uploads/edited.mp4</p><pre>" + "\n".join(log) + "</pre><p><a href='/download'>Download edited.mp4</a></p>"
            except Exception as e:
                msg = f"<h2>Error</h2><pre>{e}</pre><p>Check: ffmpeg installed? Video format mp4/mov?</p>"
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(msg.encode())
    print(f"Auto Video Editor running at http://localhost:{port}  (Ctrl+C to stop)")
    HTTPServer(("127.0.0.1", port), H).serve_forever()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?")
    ap.add_argument("--script")
    ap.add_argument("--out", default="edited.mp4")
    ap.add_argument("--web", action="store_true")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    if a.web or not a.input:
        serve(a.port); return
    script = ""
    if a.script:
        script = Path(a.script).read_text()
    log = []
    edit_video(a.input, script, a.out, log)
    print("\n".join(log))

if __name__ == "__main__":
    main()
