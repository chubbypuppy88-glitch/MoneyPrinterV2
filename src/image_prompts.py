"""Build bounded image prompts from an existing script, without another model call."""
import re

MAX_SCENES = 8


def build_scene_prompts(topic: str, script: str, requested_scenes: int = 4) -> list[str]:
    """Group consecutive script sentences into at most eight visual scenes.

    The topic is repeated for context and every script sentence is retained in
    order. This deliberately does not ask an LLM to produce or repair JSON.
    Fewer sentences produce fewer images instead of duplicate paid requests.
    """
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("A nonempty topic is required for image prompts.")
    if not isinstance(script, str) or not script.strip():
        raise ValueError("A nonempty script is required for image prompts.")
    if isinstance(requested_scenes, bool) or not isinstance(requested_scenes, int):
        raise ValueError("The scene count must be an integer.")

    topic = " ".join(topic.split())
    # Keep sentence/newline boundaries before normalizing whitespace. This is a
    # lightweight splitter, not a language-specific grammatical sentence parser.
    pieces = re.split(r"(?<=[.!?])\s+|(?<=[\u3002\uff01\uff1f])|[\r\n]+", script)
    sentences = [" ".join(piece.split()) for piece in pieces if piece.strip()]
    count = min(len(sentences), MAX_SCENES, max(1, requested_scenes))
    prompts = []
    for index in range(count):
        start = index * len(sentences) // count
        end = (index + 1) * len(sentences) // count
        scene = " ".join(sentences[start:end])
        prompts.append(
            "Create one cinematic still image for a vertical 9:16 video. "
            "Keep the main subjects, their appearance, and the setting consistent "
            "with the topic. Depict visible action rather than written narration. "
            f"Video topic: {topic}\n"
            f"Scene {index + 1} of {count}: {scene}\n"
            "No captions, lettering, logos, or watermarks."
        )
    return prompts
