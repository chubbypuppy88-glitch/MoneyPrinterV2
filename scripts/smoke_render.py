#!/usr/bin/env python3
"""Exercise the real renderer with synthetic media, not live models or uploads."""
import importlib.metadata
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import types
from unittest.mock import patch
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def stub(name, **attributes):
    module = types.ModuleType(name)
    module.__all__ = list(attributes)
    for key, value in attributes.items():
        setattr(module, key, value)
    sys.modules[name] = module


def write_audio(path, duration):
    rate = 24000
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"".join(struct.pack("<h", int(500 * math.sin(2 * math.pi * 440 * i / rate))) for i in range(int(rate * duration))))


def main():
    # Only provider/browser imports are stubbed. MoviePy, Pillow and FFmpeg are real.
    stub("classes.Tts", TTS=object)
    stub("ollama", Client=object)
    stub("assemblyai")
    stub("selenium_firefox")
    stub("selenium", webdriver=types.SimpleNamespace(Firefox=object))
    stub("selenium.webdriver", Firefox=object)
    stub("selenium.webdriver.common")
    stub("selenium.webdriver.common.by", By=object)
    stub("selenium.webdriver.firefox")
    stub("selenium.webdriver.firefox.service", Service=object)
    stub("selenium.webdriver.firefox.options", Options=object)
    stub("webdriver_manager")
    stub("webdriver_manager.firefox", GeckoDriverManager=object)
    from PIL import Image
    from classes.YouTube import YouTube

    results = {"synthetic_media": True, "network_calls": False, "uploads": False, "moviepy": importlib.metadata.version("moviepy"), "cases": []}
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        Image.new("RGB", (400, 300), (50, 80, 100)).save(root / "frame.png")
        write_audio(root / "voice.wav", 0.6)
        write_audio(root / "music.wav", 0.1)
        for use_music in (False, True):
            youtube = YouTube("test", "Synthetic test", "", "test", "English", background_music=use_music)
            youtube.images = [str(root / "frame.png")]
            youtube.tts_path = str(root / "voice.wav")
            with patch("classes.YouTube.ROOT_DIR", str(root)), patch("classes.YouTube.get_threads", return_value=2), patch("classes.YouTube.get_imagemagick_path", return_value=""), patch("classes.YouTube.choose_random_song", return_value=str(root / "music.wav")), patch.object(youtube, "generate_subtitles", side_effect=RuntimeError("Captions deliberately excluded from this smoke test")):
                output = youtube.combine()
            probe = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", output], capture_output=True, text=True, check=True)
            data = json.loads(probe.stdout)
            video = next(s for s in data["streams"] if s["codec_type"] == "video")
            assert (video["width"], video["height"]) == (1080, 1920)
            assert any(s["codec_type"] == "audio" for s in data["streams"])
            assert 0.5 <= float(data["format"]["duration"]) <= 0.8
            assert youtube.browser is None
            results["cases"].append({"music": use_music, "width": video["width"], "height": video["height"], "duration": data["format"]["duration"], "result": "passed"})
    target = ROOT / "outputs/smoke-render-results.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
