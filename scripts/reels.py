#!/usr/bin/env python3
"""Free YouTube-to-Reels pipeline: faster-whisper + heuristic highlights + FFmpeg."""

from __future__ import annotations
import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yt_dlp
from faster_whisper import WhisperModel

HOOK_TERMS = {
    "secret", "mistake", "never", "always", "best", "worst", "truth", "actually",
    "surprising", "important", "learned", "because", "why", "how", "problem",
    "solution", "remember", "imagine", "finally", "instead", "warning", "tip",
    "first", "only", "everyone", "nobody", "wrong", "right", "money", "free",
}

def run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.stdout.strip()

def require_tools() -> None:
    missing = [x for x in ("ffmpeg", "ffprobe") if shutil.which(x) is None]
    if missing:
        raise SystemExit("Missing system tools: " + ", ".join(missing))

def download_video(url: str, work: Path) -> tuple[Path, dict[str, Any]]:
    opts = {
        "format": "bv*+ba/b", "merge_output_format": "mp4",
        "outtmpl": str(work / "source.%(ext)s"), "noplaylist": True,
        "quiet": False, "no_warnings": False, "restrictfilenames": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        prepared = Path(ydl.prepare_filename(info))
        if prepared.exists():
            return prepared, info
        candidates = [p for p in work.glob("source.*")
                      if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}]
        if not candidates:
            raise FileNotFoundError("Downloaded video file was not found.")
        return candidates[0], info

def get_duration(video: Path) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "default=noprint_wrappers=1:nokey=1", str(video)]))

def extract_audio(video: Path, work: Path) -> Path:
    audio = work / "audio.wav"
    run(["ffmpeg", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
         "-c:a", "pcm_s16le", str(audio)])
    return audio

def transcribe(audio: Path, model_size: str, language: str | None):
    print(f"Loading faster-whisper {model_size!r} model on CPU (INT8)...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(
        str(audio), language=language, word_timestamps=True,
        vad_filter=True, vad_parameters={"min_silence_duration_ms": 500}, beam_size=5
    )
    words, lines = [], []
    for seg in segments:
        if (seg.text or "").strip():
            lines.append(f"[{seg.start:.2f}-{seg.end:.2f}] {seg.text.strip()}")
        for w in (seg.words or []):
            token = (w.word or "").strip()
            if token:
                words.append({"word": token, "start": float(w.start), "end": float(w.end)})
    print("Detected language:", getattr(info, "language", "unknown"))
    return words, "\n".join(lines)

def score_window(words: list[dict[str, Any]]) -> float:
    tokens = [re.sub(r"^[^\w']+|[^\w']+$", "", w["word"].lower()) for w in words]
    tokens = [t for t in tokens if t]
    if not tokens:
        return -999
    score = min(len(tokens) / 12, 5)
    score += 1.5 * sum(t in HOOK_TERMS for t in tokens)
    score += 0.7 * sum("?" in w["word"] or "!" in w["word"] for w in words)
    if re.search(r'[.!?]["\')\]]*$', words[-1]["word"]):
        score += 2
    duration = max(1, words[-1]["end"] - words[0]["start"])
    if len(tokens) / duration < 1:
        score -= 2
    return score

def choose_highlights(words, duration, min_seconds, max_seconds, max_clips):
    if not words:
        return []
    candidates = []
    # Generate candidates every five seconds, align boundaries to speech words.
    for nominal in [i * 5.0 for i in range(int(duration // 5) + 1)]:
        si = min(range(len(words)), key=lambda i: abs(words[i]["start"] - nominal))
        start = words[si]["start"]
        if start > duration - min_seconds:
            continue
        ei = si
        while ei < len(words) - 1 and words[ei]["end"] < start + min_seconds:
            ei += 1
        while ei < len(words) - 1 and words[ei]["end"] < min(start + max_seconds, duration):
            ei += 1
        end = words[ei]["end"]
        if min_seconds <= end - start <= max_seconds + 1.0:
            subset = words[si:ei + 1]
            candidates.append({"start": start, "end": min(end, duration),
                               "score": score_window(subset)})
    candidates.sort(key=lambda x: x["score"], reverse=True)
    selected = []
    for c in candidates:
        if all(c["end"] <= s["start"] or c["start"] >= s["end"] for s in selected):
            selected.append(c)
        if len(selected) >= max_clips:
            break
    selected.sort(key=lambda x: x["start"])
    for i, c in enumerate(selected, 1):
        c["title"] = f"Highlight {i}"
        c["reason"] = "Transcript heuristic: speech density, hook vocabulary and sentence-ending signals."
        c.pop("score", None)
    return selected

def ass_time(seconds: float) -> str:
    cs = max(0, int(round(seconds * 100)))
    h, rem = divmod(cs, 360000); m, rem = divmod(rem, 6000); s, centi = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{centi:02d}"

def ass_escape(s: str) -> str:
    return s.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", " ")

def make_ass(words, start, end, path):
    selected = [w for w in words if w["end"] > start and w["start"] < end]
    events = []
    for i in range(0, len(selected), 3):
        group = selected[i:i+3]
        a, b = max(start, group[0]["start"])-start, min(end, group[-1]["end"])-start
        if b <= a: continue
        pieces = []
        for w in group:
            dur = max(1, int(round((min(end, w["end"])-max(start, w["start"])) * 100)))
            pieces.append(r"{\k" + str(dur) + "}" + ass_escape(w["word"]))
        events.append(f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Karaoke,,0,0,0,," + " ".join(pieces))
    header = r"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Karaoke,DejaVu Sans,76,&H00FFFFFF,&H0000D7FF,&H00101010,&H80000000,-1,0,0,0,100,100,1,0,1,7,2,2,70,70,330,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")

def render_clip(video, words, clip, index, output):
    start, end = clip["start"], clip["end"]
    ass = output / f"clip_{index:02d}.ass"
    make_ass(words, start, end, ass)
    mp4 = output / f"reel_{index:02d}_highlight-{index}.mp4"
    sub = str(ass.resolve()).replace("\\", "/").replace(":", r"\:")
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,ass='" + sub + "'"
    run(["ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(video), "-t", f"{end-start:.3f}",
         "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-pix_fmt", "yuv420p", str(mp4)])
    return {"file": mp4.name, "title": clip["title"], "start_seconds": round(start, 2),
            "end_seconds": round(end, 2), "duration_seconds": round(end-start, 2),
            "reason": clip["reason"]}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--max-clips", type=int, default=3)
    p.add_argument("--min-seconds", type=int, default=30)
    p.add_argument("--max-seconds", type=int, default=60)
    p.add_argument("--model-size", choices=["tiny", "base", "small"], default="base")
    p.add_argument("--language", default=None, help="Optional code such as en, ml, ar; default auto-detect.")
    p.add_argument("--output-dir", default="output")
    a = p.parse_args()
    if not 1 <= a.max_clips <= 5: raise SystemExit("--max-clips must be 1–5.")
    if not 10 <= a.min_seconds <= a.max_seconds <= 90: raise SystemExit("Invalid clip duration range.")
    require_tools()
    output = Path(a.output_dir); output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="youtube-reels-") as tmp:
        work = Path(tmp)
        print("Downloading source. Only use content you own or are authorized to repurpose.")
        video, info = download_video(a.url, work)
        duration = get_duration(video)
        print(f"Source: {info.get('title', video.name)} ({duration/60:.1f} min)")
        audio = extract_audio(video, work)
        words, transcript = transcribe(audio, a.model_size, a.language)
        if not words: raise RuntimeError("No speech transcript found.")
        clips = choose_highlights(words, duration, a.min_seconds, a.max_seconds, a.max_clips)
        if not clips: raise RuntimeError("No suitable speech windows found; try a longer video.")
        results = []
        for i, clip in enumerate(clips, 1):
            print(f"Rendering clip {i}/{len(clips)}...")
            results.append(render_clip(video, words, clip, i, output))
        (output / "clips.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        (output / "captions-transcript.txt").write_text(transcript, encoding="utf-8")
        for ass in output.glob("*.ass"): ass.unlink(missing_ok=True)
        print(f"Created {len(results)} clip(s) in {output.resolve()}")

if __name__ == "__main__":
    main()
