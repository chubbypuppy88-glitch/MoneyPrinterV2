# HouseOfBigBeans autopilot

This is the free/local path for making the Short. It avoids the Google image API,
Metricool, Whisper, and ImageMagick.

The normal generation path is:

1. private photos in `local_media/houseofbigbeans/`
2. local Ollama for short narration/title/description
3. local KittenTTS voice
4. MoviePy + FFmpeg for the 1080x1920 video
5. deterministic FFmpeg captions generated from the exact narration script
6. optional official YouTube API upload as **Private**

Generate only:

```bash
.venv/bin/python -u scripts/houseofbigbeans_autopilot.py
```

## One-time YouTube authorization

YouTube will not accept anonymous uploads. The only unavoidable manual setup is
authorizing the channel once.

Create an OAuth client in Google Cloud of type **TVs and Limited Input devices**,
download its JSON, and save it locally as `youtube_oauth_client.json`.
Do not commit it.

Then run:

```bash
.venv/bin/python -u scripts/youtube_device_auth.py
```

The script prints Google's verification URL and a short code. After you approve
the account once, the refresh token is stored locally in
`.youtube_oauth_token.json` and future uploads can refresh automatically.

Generate and upload privately in one command:

```bash
.venv/bin/python -u scripts/houseofbigbeans_autopilot.py --upload-private
```

The uploader uses YouTube's official resumable upload protocol and hard-codes
`privacyStatus=private`. It does not use Selenium, Firefox, Metricool, or a paid
publishing service. Public/scheduled publishing should only be enabled after a
private upload has been verified.
