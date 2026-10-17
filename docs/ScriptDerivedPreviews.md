# Script-derived image prompts for local previews

`scripts/generate_preview.py` now uses `PreviewYouTube`, a small subclass that
changes only the image-prompt step. Text generation, image generation, narration,
and rendering continue to use the existing pipeline. There is no upload or
scheduling call in the preview entrypoint.

Image prompts are built directly from the generated script and topic. They do
not require Ollama to return a JSON array and do not retry malformed JSON.
Consecutive script sentences are grouped in order, with at most eight images and
no more images than script segments. The configured `script_sentence_length`
remains the requested scene limit. Empty scripts are rejected instead of being
silently turned into unrelated images.

This trades a separate creative prompt-writing step for a deterministic,
lower-latency preview path. The basic sentence splitter is not a language-specific
grammatical parser. Review the resulting images for relevance and visual
consistency. The interactive and scheduled YouTube paths are unchanged.

Run the same local-only preview command:

```bash
.venv/bin/python -u scripts/generate_preview.py --account HouseOfBigBeans --topic "A playful Maine Coon cat discovers that a tiny cardboard box is its favorite new bed."
```

Progress now includes `[IMAGES] Built ... scene prompts from the script` before
image requests start. That message is not a completed video. Completion is
`[OK] Local preview:` followed by an MP4 path. Image API authentication, quota,
voiceover, and rendering can still fail independently. Provider calls may use
paid quota; this change does not modify keys, local configuration, or uploads.

Regression coverage includes prompt ordering, scene limits, empty input,
non-JSON script text, and a mocked pipeline that reaches images, narration, and
rendering using only the three text responses for script, title, and description.
