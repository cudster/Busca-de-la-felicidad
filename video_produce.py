#!/usr/bin/env python3
"""Fase 2b: produce el video faceless a partir de un plan de youtube_generate.py.

Voz IA (ElevenLabs) narra el guión → clips reales de autos (Pexels) → ffmpeg ensambla
un mp4 (Shorts vertical 1080x1920, long-form horizontal 1920x1080).

Uso:
    python3 video_produce.py --channel autos-pov --video 2026-10-S01
    python3 video_produce.py --channel autos-pov --month 2026-10        # todos
Requiere en .env: ELEVENLABS_API_KEY, PEXELS_API_KEY. Necesita ffmpeg + ffprobe.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "videos"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DEFAULT_VOICE = "onwK4e9ZLuTAKqWW03F9"  # ElevenLabs multilingüe (config puede override)
# POV manejando: se ordena para armar un mini-arco → prender → manejar lento → acelerar.
CAR_QUERIES = [
    "car ignition start button push",
    "car interior driving pov",
    "hands on steering wheel driving",
    "driving pov road first person",
    "fast car acceleration highway",
]


def _env() -> dict:
    e = {}
    p = ROOT / ".env"
    if p.exists():
        for l in p.read_text(encoding="utf-8").splitlines():
            if "=" in l and not l.strip().startswith("#"):
                k, _, v = l.partition("=")
                e[k.strip()] = v.strip().strip('"').strip("'")
    e.update({k: os.environ[k] for k in ("ELEVENLABS_API_KEY", "PEXELS_API_KEY") if os.environ.get(k)})
    return e


def load_plan(channel: str, month: str) -> list[dict]:
    p = ROOT / "youtube" / channel / f"plan-{month}.json"
    if not p.exists():
        sys.exit(f"No existe {p}. Genera el plan primero con youtube_generate.py.")
    return json.loads(p.read_text(encoding="utf-8"))


# ---- Voz IA (ElevenLabs) ----
def tts_elevenlabs(text: str, out_mp3: Path, key: str, voice_id: str = DEFAULT_VOICE) -> None:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    body = json.dumps({"text": text, "model_id": "eleven_multilingual_v2",
                       "voice_settings": {"stability": 0.4, "similarity_boost": 0.8}}).encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"xi-api-key": key, "Content-Type": "application/json",
                                          "Accept": "audio/mpeg"})
    with urllib.request.urlopen(req, timeout=120) as r:
        out_mp3.write_bytes(r.read())


# ---- Clips (Pexels) ----
def pexels_clips(n: int, vertical: bool, out_dir: Path, key: str) -> list[Path]:
    orient = "portrait" if vertical else "landscape"
    paths, seen = [], set()
    for q in CAR_QUERIES:
        if len(paths) >= n:
            break
        u = ("https://api.pexels.com/videos/search?query=" + urllib.parse.quote(q) +
             "&orientation=" + orient + "&per_page=8")
        req = urllib.request.Request(u, headers={"Authorization": key, "User-Agent": UA})
        try:
            vids = json.load(urllib.request.urlopen(req, timeout=30)).get("videos", [])
        except Exception:
            continue
        for v in vids:
            if len(paths) >= n or v["id"] in seen:
                continue
            files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4"
                     and (f.get("height") or 0) >= 720]
            if not files:
                continue
            seen.add(v["id"])
            link = sorted(files, key=lambda f: abs((f.get("height") or 0) - (1920 if vertical else 1080)))[0]["link"]
            dst = out_dir / f"clip_{v['id']}.mp4"
            try:
                rq = urllib.request.Request(link, headers={"User-Agent": UA})
                dst.write_bytes(urllib.request.urlopen(rq, timeout=60).read())
                paths.append(dst)
            except Exception:
                continue
    return paths


# ---- ffmpeg ----
def _run(cmd: list) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def audio_duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def assemble(clips: list[Path], audio: Path, out: Path, w: int, h: int, work: Path) -> None:
    norm = []
    for i, c in enumerate(clips):
        d = work / f"n{i}.mp4"
        _run(["ffmpeg", "-y", "-i", str(c), "-t", "5",
              "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps=30",
              "-an", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(d)])
        norm.append(d)
    listfile = work / "list.txt"
    listfile.write_text("".join(f"file '{p}'\n" for p in norm), encoding="utf-8")
    silent = work / "silent.mp4"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(silent)])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(silent), "-i", str(audio),
          "-map", "0:v:0", "-map", "1:a:0", "-shortest",
          "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-movflags", "+faststart", str(out)])


def produce_video(video: dict, channel: str, env: dict, voice: str) -> Path:
    vertical = video["format"] == "short"
    w, h = (1080, 1920) if vertical else (1920, 1080)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{channel}-{video['id']}.mp4"
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        audio = work / "narration.mp3"
        print(f"  · voz IA…")
        tts_elevenlabs(video["script_es"], audio, env["ELEVENLABS_API_KEY"], voice)
        dur = audio_duration(audio)
        n = max(3, int(dur // 5) + 1)
        print(f"  · {n} clips (Pexels)…")
        clips = pexels_clips(n, vertical, work, env["PEXELS_API_KEY"])
        if len(clips) < 2:
            sys.exit("No conseguí suficientes clips de Pexels.")
        print(f"  · ensamblando ({w}x{h}, {dur:.0f}s)…")
        assemble(clips, audio, out, w, h, work)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Fase 2b — produce el video faceless.")
    ap.add_argument("--channel", required=True)
    ap.add_argument("--video", help="Un id (ej. 2026-10-S01).")
    ap.add_argument("--month", help="Todos los del mes (YYYY-MM).")
    ap.add_argument("--voice", default=DEFAULT_VOICE, help="voice_id de ElevenLabs.")
    args = ap.parse_args()
    env = _env()
    if not env.get("ELEVENLABS_API_KEY"):
        sys.exit("Falta ELEVENLABS_API_KEY en .env.")
    if not env.get("PEXELS_API_KEY"):
        sys.exit("Falta PEXELS_API_KEY en .env.")

    month = args.month or (args.video.rsplit("-", 1)[0] if args.video else None)
    if not month:
        sys.exit("Indica --video o --month.")
    plan = load_plan(args.channel, month)
    if args.video:
        plan = [v for v in plan if v["id"] == args.video]
        if not plan:
            sys.exit(f"No encontré {args.video} en el plan.")
    for v in plan:
        print(f"→ {v['id']} [{v['format']}] {v['title'][:50]}")
        out = produce_video(v, args.channel, env, args.voice)
        print(f"  ✓ {out}")


if __name__ == "__main__":
    main()
