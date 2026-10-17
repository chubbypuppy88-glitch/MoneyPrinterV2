"""Local preview variant that uses user-provided image files instead of an image API."""
from pathlib import Path

from .PreviewYouTube import PreviewYouTube

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class LocalPhotoPreview(PreviewYouTube):
    """Reuse the local preview pipeline while sourcing scenes from a private folder."""

    def __init__(self, *args, images_dir: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.images_dir = Path(images_dir).expanduser().resolve()
        self._local_images: list[str] = []

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
