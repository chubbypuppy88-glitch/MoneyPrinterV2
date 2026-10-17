# HouseOfBigBeans autopilot

This workflow removes the manual edit/download/re-caption loop for local-photo Shorts.

It:
1. uses private images from `local_media/houseofbigbeans/`;
2. generates a visually safe Maine Coon narration with Ollama;
3. generates title/description;
4. synthesizes the voice with the existing TTS;
5. renders a vertical 1080x1920 Short;
6. burns captions directly from the exact narration with FFmpeg, so ImageMagick and Whisper are not required for this path;
7. optionally uploads the finished video to YouTube **as Private** with the existing authenticated Firefox profile.

No Google image-generation API is used for this workflow. Local photos and outputs remain gitignored.

Generate only:

```bash
.venv/bin/python -u scripts/houseofbigbeans_autopilot.py
```

Generate and privately upload:

```bash
.venv/bin/python -u scripts/houseofbigbeans_autopilot.py --upload-private
```

The script deliberately does not select Public visibility or cross-post. Verify one private upload before adding scheduled/public automation.
