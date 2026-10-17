"""Explain preview failures without printing secrets, prompts, or response bodies."""
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
STAGES = {
    "generate_topic": "topic generation",
    "generate_script": "script generation",
    "generate_metadata": "title and description generation",
    "generate_prompts": "image-prompt generation",
    "generate_image": "image generation",
    "generate_image_nanobanana2": "image generation",
    "generate_script_to_speech": "voiceover generation",
    "combine": "video rendering",
    "synthesize": "voiceover generation",
}
KNOWN_ERRORS = {
    "No Ollama model selected. Call select_model() first or pass model_name.": (
        "NO_MODEL_SELECTED", "No Ollama model was selected for text generation."),
    "The language model did not return usable image prompts after 3 attempts.": (
        "INVALID_IMAGE_PROMPTS", "Ollama did not return usable JSON image prompts after three attempts."),
    "The image provider returned no images; generation stopped before rendering.": (
        "NO_PROVIDER_IMAGES", "The image provider returned no images."),
    "No images were generated. Check the image provider before rendering.": (
        "NO_RENDER_IMAGES", "No images were available for video rendering."),
    "The generated voiceover is empty.": (
        "EMPTY_VOICEOVER", "The generated voiceover has no usable duration."),
    "The background audio file is empty.": (
        "EMPTY_BACKGROUND_AUDIO", "The background audio has no usable duration."),
    "No audio files found in Songs directory": (
        "NO_BACKGROUND_AUDIO", "No supported background audio was found."),
}


def describe_failure(exc: Exception) -> dict:
    """Only return allowlisted descriptions and repository-relative code locations.

    Exception text is used for matching, never echoed. Provider bodies, source
    lines, local variables, absolute paths and config/environment values are not
    returned. Unknown errors still expose their code location for investigation.
    """
    result = {"stage": "preview startup or generation", "code": "UNCLASSIFIED_ERROR",
              "reason": "The cause is not yet classified; use the code location below.",
              "locations": [], "types": [], "http_status": None}
    seen = set()
    current = exc
    for _ in range(5):
        if current is None or id(current) in seen:
            break
        seen.add(id(current))
        # Python identifiers only, not an arbitrary repr or exception body.
        name = type(current).__name__
        result["types"].append(name if name.isidentifier() else "Exception")
        tb = current.__traceback__
        while tb is not None:
            code = tb.tb_frame.f_code
            try:
                relative = Path(code.co_filename).resolve().relative_to(ROOT_DIR)
            except (ValueError, OSError):
                relative = None
            if relative is not None and relative.parts[0] in ("scripts", "src"):
                # Do not include an unexpected or credential-bearing filename.
                safe_path = all(part.replace(".", "").replace("_", "").isalnum()
                                for part in relative.parts)
                if safe_path and code.co_name.isidentifier():
                    location = f"{relative.as_posix()}:{tb.tb_lineno} in {code.co_name}"
                    if location not in result["locations"]:
                        result["locations"].append(location)
                if code.co_name in STAGES:
                    result["stage"] = STAGES[code.co_name]
            tb = tb.tb_next
        status = getattr(current, "status_code", None)
        if isinstance(status, int) and 100 <= status <= 599:
            result["http_status"] = status
        message = str(current)
        if result["code"] == "UNCLASSIFIED_ERROR":
            if message in KNOWN_ERRORS:
                result["code"], result["reason"] = KNOWN_ERRORS[message]
            elif isinstance(current, (TimeoutError, ConnectionError)) or name in (
                    "ReadTimeout", "ConnectTimeout", "ConnectError"):
                result["code"] = "PROVIDER_CONNECTION"
                result["reason"] = "A provider connection failed or timed out."
            elif isinstance(current, MemoryError):
                result["code"] = "OUT_OF_MEMORY"
                result["reason"] = "The process reported insufficient memory."
        current = current.__cause__ or (
            None if current.__suppress_context__ else current.__context__)
    return result


def report_failure(exc: Exception) -> None:
    details = describe_failure(exc)
    print(f"[FAIL] Preview stopped during {details['stage']}; code={details['code']}")
    print("[CAUSE] " + details["reason"])
    print("[TYPE] " + " -> ".join(details["types"]))
    if details["http_status"] is not None:
        print(f"[HTTP] {details['http_status']}")
    for location in details["locations"][-4:]:
        print("[LOCATION] " + location)
    print("[INFO] No upload was attempted. Private error text has not been printed.")
