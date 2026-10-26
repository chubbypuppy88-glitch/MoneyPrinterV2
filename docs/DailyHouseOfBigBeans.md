# Daily HouseOfBigBeans automation

The daily workflow runs in GitHub Actions at 15:00 UTC, so the Codespace does not need to stay open.

Pipeline:
- rotates through a bank of different Maine Coon topics by date;
- generates four fresh vertical AI scenes with Pollinations;
- uses free local eSpeak NG narration;
- renders a 1080x1920 H.264/AAC Short with FFmpeg;
- burns captions from the exact narration text;
- refreshes YouTube OAuth automatically;
- uploads the finished Short through the official YouTube Data API.

The scheduled workflow defaults to Public. Set repository variable `YOUTUBE_PRIVACY_STATUS` to `private` or `unlisted` if desired.

Required repository secrets:
- `POLLINATIONS_API_KEY` — free Pollinations key from enter.pollinations.ai.
- `YOUTUBE_CLIENT_JSON` — complete OAuth client JSON.
- `YOUTUBE_TOKEN_JSON` — complete token JSON created by `scripts/youtube_device_auth.py`.

No camera-roll photos, Google image-generation key, Metricool, running Codespace, Ollama server, Whisper, ImageMagick, Selenium, or Firefox session is required by the daily workflow.

Manual test:
```bash
python scripts/daily_houseofbigbeans.py --smoke --date 2026-10-25 --outdir outputs/smoke
```

Manual real run:
```bash
POLLINATIONS_API_KEY=... python scripts/daily_houseofbigbeans.py --date 2026-10-25 --outdir outputs/daily
```
