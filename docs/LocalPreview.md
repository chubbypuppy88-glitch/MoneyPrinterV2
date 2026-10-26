# Local-only preview workflow

The local preview entrypoint generates an MP4 without starting Firefox, uploading
to YouTube, cross-posting, or enabling a schedule. It reads your existing local
`config.json` and `.mp/youtube.json`; neither file belongs in Git.

## Existing Codespace

Activate the existing Python 3.12 environment (`.venv` or `venv`), then install
`requirements.txt` if dependencies need updating. This application still uses the
MoviePy 1.x API, so the dependency is pinned to 1.0.3. Image fitting uses current
Pillow APIs rather than MoviePy 1's removed `Image.ANTIALIAS` path. A full migration
to maintained MoviePy 2 remains future work.

Check readiness first:

```bash
python scripts/generate_preview.py --account HouseOfBigBeans --check-only
```

Generate one local video after the checks pass:

```bash
python scripts/generate_preview.py --account HouseOfBigBeans --topic "Why Maine Coons chirp"
```

This uses the configured Ollama model, Gemini image provider, and KittenTTS.
Provider calls can consume quota. Model weights may need downloading. Checks
confirm configuration and Ollama availability, not the validity of the Gemini key
or the success of a complete generation run. No credentials are printed.

Background music is **off by default**. A missing song archive or temporary test
tone therefore does not block a preview. Add `--music` only with audio that you
have permission to use. The main interactive uploader retains its existing music
behavior; the local preview is the safe first test.

Videos and their metadata are saved under `outputs/`, which is ignored by Git.
Returning to the menu no longer deletes generated previews. Failed subtitle
rendering produces a warning and a video without captions; review the result.
Firefox is started only for explicit channel/upload operations, not while listing
accounts or generating previews. Uploads request PRIVATE visibility by name rather
than selecting a positional radio button. Live YouTube authentication and current
Studio selectors still require validation in your own signed-in environment.

## Validation scope

Unit tests mock external providers. The render smoke check uses synthetic local
images and audio, real MoviePy/Pillow/FFmpeg, and no credentials or network calls.
Neither is a substitute for running a complete provider-backed preview in the
Codespace. No test uploads content.

```bash
python -m unittest discover -s tests -v
python scripts/smoke_render.py
```
