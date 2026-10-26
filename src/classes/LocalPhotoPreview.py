"""Local photo workflow for HouseOfBigBeans previews and private uploads."""
from pathlib import Path
import os
import re

import numpy as np
from PIL import Image, ImageOps

from .PreviewYouTube import PreviewYouTube
from config import ROOT_DIR, get_script_sentence_length, get_threads
from script_captions import burn_script_captions
from status import success, warning
from utils import choose_random_song

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
UNSAFE_MONTAGE_CLAIMS = (
    "cardboard box", " box ", "sleeping", "asleep", "toy", "treat", "eating",
    "food", "accident", "injury", "sick",
)
SAFE_FALLBACK_SCRIPT = (
    "Meet the Maine Coon behind House of Big Beans. "
    "Fluffy, curious, and always ready to supervise the room. "
    "Whether posing on the cat tree or exploring the furniture, "
    "this little lion knows how to steal the spotlight."
)


class LocalPhotoPreview(PreviewYouTube):
    """Use private local photos, safe photo-montage narration, and FFmpeg captions."""

    def __init__(self, *args, images_dir: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.images_dir = Path(images_dir).expanduser().resolve()
        self._local_images: list[str] = []

    def generate_script(self) -> str:
        sentence_length = max(3, min(5, int(get_script_sentence_length())))\n        subject = getattr(self, "subject", self.niche)
        prompt = f"""
Write exactly {sentence_length} short sentences for a YouTube Short voiceover about
the Maine Coon featured in a montage of real household photos on the HouseOfBigBeans channel.

You cannot see the photos, so keep every claim visually safe and generic.
You may describe the cat as a fluffy silver Maine Coon, curious, expressive, posing,
watching the room, sitting on a cat tree, or exploring household furniture.
Do not invent a cardboard box, food, sleeping, toys, tricks, accidents, medical facts,
age, sex, or any specific event that was not explicitly provided.
Mention House of Big Beans naturally no more than once.
Keep the whole narration suitable for roughly 12 to 18 seconds.
Return only the raw narration with no title, labels, markdown, or quotation marks.

Subject: {subject}
Language: {self.language}
"""
        completion = str(self.generate_response(prompt))
        completion = re.sub(r"\*", "", completion).strip().strip('"')
        normalized = f" {completion.lower()} "
        if (
            not completion
            or len(completion) > 1200
            or any(term in normalized for term in UNSAFE_MONTAGE_CLAIMS)
        ):
            warning("Generated narration made an unsupported photo claim; using the safe HouseOfBigBeans fallback.")
            completion = SAFE_FALLBACK_SCRIPT
        self.script = completion
        return completion

    def generate_prompts(self) -> list[str]:
        if not self.images_dir.is_dir():
            raise RuntimeError("Local image folder does not exist.")
        files = sorted(
            path for path in self.images_dir.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        )
        if not files:
            raise RuntimeError("No supported local images were found.")
        self._local_images = [str(path) for path in files]
        self.image_prompts = list(self._local_images)
        print(
            f"[IMAGES] Using {len(self.image_prompts)} local photo(s); "
            "Google image generation is bypassed.",
            flush=True,
        )
        return self.image_prompts

    def generate_image(self, prompt: str) -> str:
        path = Path(prompt).resolve()
        if str(path) not in self._local_images or not path.is_file():
            raise RuntimeError("A selected local image is unavailable.")
        self.images.append(str(path))
        return str(path)

    def combine(self) -> str:
        """Render local photos, narration, optional music, then burn script-aligned captions."""
        # Keep MoviePy optional until the legacy local-photo renderer is actually invoked.
        from moviepy.editor import (
            AudioFileClip, ImageClip, concatenate_videoclips,
            CompositeAudioClip, afx,
        )
        if not self.images:
            raise RuntimeError("No local images are available for rendering.")

        output_dir = os.path.join(ROOT_DIR, "outputs")
        os.makedirs(output_dir, exist_ok=True)
        from uuid import uuid4
        output_path = os.path.join(output_dir, str(uuid4()) + ".mp4")
        resources = []

        def keep(clip):
            resources.append(clip)
            return clip

        try:
            tts_clip = keep(AudioFileClip(self.tts_path))
            duration = tts_clip.duration
            if not duration or duration <= 0:
                raise RuntimeError("The generated voiceover is empty.")

            scene_duration = duration / len(self.images)
            clips = []
            for image_path in self.images:
                with Image.open(image_path) as image:
                    frame = np.array(ImageOps.fit(
                        image.convert("RGB"), (1080, 1920),
                        method=Image.Resampling.LANCZOS,
                    ))
                clips.append(keep(ImageClip(frame).set_duration(scene_duration).set_fps(30)))

            final_clip = keep(concatenate_videoclips(clips, method="chain"))
            audio = tts_clip.set_fps(44100)
            if self.background_music:
                song = keep(AudioFileClip(choose_random_song()))
                if not song.duration or song.duration <= 0:
                    raise RuntimeError("The background audio file is empty.")
                music = keep(afx.audio_loop(song, duration=duration).volumex(0.1))
                audio = keep(CompositeAudioClip([audio, music]))
            final_clip = keep(final_clip.set_audio(audio).set_duration(duration))

            final_clip.write_videofile(
                output_path, fps=30, codec="libx264", audio_codec="aac",
                threads=max(1, int(get_threads())),
                ffmpeg_params=["-pix_fmt", "yuv420p"],
            )
            success(f'Wrote Video to "{output_path}"')
        finally:
            seen = set()
            for clip in reversed(resources):
                if id(clip) not in seen:
                    seen.add(id(clip))
                    try:
                        clip.close()
                    except Exception:
                        pass

        try:
            burn_script_captions(output_path, self.script)
            success("Burned script-aligned captions with FFmpeg; ImageMagick/Whisper not required.")
        except Exception as exc:
            warning(f"Caption finalization failed ({type(exc).__name__}); keeping the uncaptioned render.")

        return output_path
