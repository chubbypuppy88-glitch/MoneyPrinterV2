"""Local preview variant that does not rely on LLM-generated JSON image prompts."""
from .YouTube import YouTube
from config import get_script_sentence_length
from image_prompts import build_scene_prompts


class PreviewYouTube(YouTube):
    """Reuse the video pipeline with script-derived prompts for local previews."""

    def generate_prompts(self) -> list[str]:
        self.image_prompts = build_scene_prompts(
            self.subject, self.script, get_script_sentence_length(),
        )
        print(
            f"[IMAGES] Built {len(self.image_prompts)} scene prompts from the script; "
            "no Ollama JSON request or retry needed.",
            flush=True,
        )
        return self.image_prompts
