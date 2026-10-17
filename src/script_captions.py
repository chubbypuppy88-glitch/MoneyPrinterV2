"""Deterministic captions derived from the exact TTS script."""
from pathlib import Path
import re
import subprocess


def _ass_time(seconds: float) -> str:
    centiseconds = max(0, int(round(float(seconds) * 100)))
    hours, rem = divmod(centiseconds, 360000)
    minutes, rem = divmod(rem, 6000)
    secs, cs = divmod(rem, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _caption_chunks(script: str) -> list[str]:
    pieces = re.split(r"(?<=[.!?])\s+|[\r\n]+", str(script).strip())
    chunks = [" ".join(piece.split()) for piece in pieces if piece.strip()]
    if not chunks:
        raise ValueError("Caption script is empty.")
    return chunks


def build_ass(script: str, duration: float) -> str:
    """Build readable 9:16 captions spread across the narration duration."""
    chunks = _caption_chunks(script)
    if duration <= 0:
        raise ValueError("Caption duration must be positive.")

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Short,DejaVu Sans,66,&H00FFFFFF,&H000000FF,&H00000000,&H70000000,-1,0,0,0,100,100,0,0,1,5,2,2,80,80,360,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header.rstrip()]
    count = len(chunks)
    for index, chunk in enumerate(chunks):
        start = duration * index / count
        end = duration * (index + 1) / count
        safe = chunk.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")
        words = safe.split()
        wrapped, current = [], []
        for word in words:
            proposed = " ".join(current + [word])
            if current and len(proposed) > 34:
                wrapped.append(" ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            wrapped.append(" ".join(current))
        text = r"\N".join(wrapped[:3])
        lines.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Short,,0,0,0,,{text}"
        )
    return "\n".join(lines) + "\n"


def _probe_duration(video_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(video_path),
        ],
        check=True, capture_output=True, text=True, timeout=30,
    )
    return float(result.stdout.strip())


def burn_script_captions(video_path: str, script: str) -> str:
    """Burn matching captions and normalize narration loudness into the same MP4."""
    video = Path(video_path).resolve()
    if not video.is_file():
        raise FileNotFoundError(video)

    duration = _probe_duration(video)
    ass = video.with_suffix(".captions.ass")
    temp = video.with_name(video.stem + ".captioned.mp4")
    ass.write_text(build_ass(script, duration), encoding="utf-8")

    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(video),
                "-vf", f"ass={ass}",
                "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", str(temp),
            ],
            check=True, timeout=300,
        )
        temp.replace(video)
    finally:
        ass.unlink(missing_ok=True)
        temp.unlink(missing_ok=True)
    return str(video)
