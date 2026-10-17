"""One-time, checksum-guarded application of the reviewed preview repairs."""
from pathlib import Path
import ast
import hashlib

root = Path(__file__).resolve().parents[2]
expected = {
    'src/main.py': '3e3420c46e77ce82d5c69c5a583857c0eaac81d8',
    'src/config.py': 'fb26d8d4eeaa481b363c4677d4d1841213c29042',
    'src/classes/YouTube.py': '0cd623b57cb30bec711e3aef4db66d733ca2812d',
    'requirements.txt': 'e49dc6afdba8cf872010cb63ee22f738e95e4e17',
    'tests/test_youtube_custom_topic.py': 'e822a86b8254a5c7ef8cbbee856df890cb882e8b',
}
for path, wanted in expected.items():
    data = (root / path).read_bytes()
    actual = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    if actual != wanted:
        raise RuntimeError(f'Baseline changed; refusing to overwrite {path}')


def replace_method(text, name, replacement):
    tree = ast.parse(text)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'YouTube')
    node = next(n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    lines = text.splitlines(keepends=True)
    lines[node.lineno-1:node.end_lineno] = [replacement.rstrip() + '\n']
    return ''.join(lines)

p = root / 'src/config.py'
s = p.read_text().replace('ROOT_DIR = os.path.dirname(sys.path[0])', 'ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))')
p.write_text(s)

p = root / 'src/classes/YouTube.py'
s = p.read_text().replace('# Set ImageMagick Path\nchange_settings({"IMAGEMAGICK_BINARY": get_imagemagick_path()})\n', '# ImageMagick is configured only when rendering subtitles, not at import time.\n')
s = replace_method(s, '__init__', '''    def __init__(
        self,
        account_uuid: str,
        account_nickname: str,
        fp_profile_path: str,
        niche: str,
        language: str,
        *,
        background_music: bool = True,
    ) -> None:
        """Initialize account state without starting Firefox or downloading models."""
        self._account_uuid = account_uuid
        self._account_nickname = account_nickname
        self._fp_profile_path = fp_profile_path
        self._niche = niche
        self._language = language
        self.background_music = background_music
        self.images = []
        self.browser = None
        self.options = None
        self.service = None

    def _ensure_browser(self):
        """Start Firefox only for an explicit upload/channel operation."""
        if self.browser is not None:
            return self.browser
        if not os.path.isdir(self._fp_profile_path):
            raise ValueError(
                "A valid, authenticated Firefox profile is required for uploading, "
                "but not for local preview generation."
            )
        self.options = Options()
        if get_headless():
            self.options.add_argument("--headless")
        self.options.add_argument("-profile")
        self.options.add_argument(self._fp_profile_path)
        self.service = Service(GeckoDriverManager().install())
        self.browser = webdriver.Firefox(service=self.service, options=self.options)
        return self.browser

    def close_browser(self) -> None:
        """Release the browser if one was opened, including failed uploads."""
        browser, self.browser = self.browser, None
        if browser is not None:
            try:
                browser.quit()
            except Exception:
                warning("Firefox could not be closed cleanly.")''')

s = replace_method(s, 'generate_prompts', '''    def generate_prompts(self) -> List[str]:
        """Generate a bounded number of validated prompts, not one per few letters."""
        n_prompts = min(8, max(1, int(get_script_sentence_length())))
        prompt = (
            f"Generate exactly {n_prompts} image prompts for this video. "
            "Return only a JSON array of nonempty strings. Each prompt must "
            "describe one scene, include the main subject, and suit a vertical video. "
            f"Subject: {self.subject}\\nScript: {self.script}"
        )
        for _ in range(3):
            completion = str(self.generate_response(prompt)).strip()
            completion = completion.replace("```json", "").replace("```", "").strip()
            try:
                try:
                    parsed = json.loads(completion)
                except json.JSONDecodeError:
                    start, end = completion.find("["), completion.rfind("]")
                    if start < 0 or end < start:
                        continue
                    parsed = json.loads(completion[start:end + 1])
                if isinstance(parsed, dict):
                    parsed = parsed.get("image_prompts")
                if not isinstance(parsed, list):
                    continue
                prompts = [item.strip() for item in parsed if isinstance(item, str) and item.strip()]
                if not prompts:
                    continue
                self.image_prompts = prompts[:n_prompts]
                success(f"Generated {len(self.image_prompts)} Image Prompts.")
                return self.image_prompts
            except (ValueError, TypeError):
                continue
        raise RuntimeError("The language model did not return usable image prompts after 3 attempts.")''')

s = replace_method(s, 'combine', '''    def combine(self) -> str:
        """Render a retained local MP4; background music is optional for previews."""
        import numpy as np
        from PIL import Image, ImageOps

        if not self.images:
            raise RuntimeError("No images were generated. Check the image provider before rendering.")
        output_dir = os.path.join(ROOT_DIR, "outputs")
        os.makedirs(output_dir, exist_ok=True)
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
                    # Avoid MoviePy 1's removed Pillow Image.ANTIALIAS API.
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

            try:
                magick = get_imagemagick_path()
                if magick:
                    change_settings({"IMAGEMAGICK_BINARY": magick})
                subtitles_path = self.generate_subtitles(self.tts_path)
                equalize_subtitles(subtitles_path, 10)
                generator = lambda text: TextClip(
                    text, font=os.path.join(get_fonts_dir(), get_font()),
                    fontsize=80, color="#FFFF00", stroke_color="black",
                    stroke_width=3, size=(1000, None), method="caption",
                )
                subtitles = keep(SubtitlesClip(subtitles_path, generator).set_position(("center", "center")))
                final_clip = keep(CompositeVideoClip([final_clip, subtitles]).set_duration(duration))
            except Exception:
                warning("Subtitle rendering failed; this preview will not include captions.")

            final_clip.write_videofile(
                output_path, fps=30, codec="libx264", audio_codec="aac",
                threads=max(1, int(get_threads())), ffmpeg_params=["-pix_fmt", "yuv420p"],
            )
            success(f'Wrote Video to "{output_path}"')
            return output_path
        finally:
            seen = set()
            for clip in reversed(resources):
                if id(clip) not in seen:
                    seen.add(id(clip))
                    try:
                        clip.close()
                    except Exception:
                        pass''')

s = s.replace('        # Use the custom topic if one was supplied, otherwise generate one\n', '        self.images = []\n        self.image_prompts = []\n        os.makedirs(os.path.join(ROOT_DIR, ".mp"), exist_ok=True)\n\n        # Use the custom topic if one was supplied, otherwise generate one\n')
s = s.replace('        # Generate the TTS\n        self.generate_script_to_speech(tts_instance)', '        if not self.images:\n            raise RuntimeError("The image provider returned no images; generation stopped before rendering.")\n\n        # Generate the TTS\n        self.generate_script_to_speech(tts_instance)')
s = s.replace('        driver = self.browser\n        driver.get("https://studio.youtube.com")', '        driver = self._ensure_browser()\n        driver.get("https://studio.youtube.com")')
s = s.replace('        channel_id = driver.current_url.split("/")[-1]', '        if "/channel/" not in driver.current_url:\n            raise RuntimeError("Firefox is not signed into a YouTube Studio channel.")\n        channel_id = driver.current_url.split("/channel/", 1)[1].split("/")[0]')
s = s.replace('            # Set as unlisted\n', '            # Fail closed: never select visibility by a positional radio index.\n')
s = s.replace('                info("\\t=> Setting as unlisted...")', '                info("\\t=> Setting visibility to private...")')
s = s.replace('            radio_button = driver.find_elements(By.XPATH, YOUTUBE_RADIO_BUTTON_XPATH)\n            radio_button[2].click()', '            driver.find_element(By.NAME, "PRIVATE").click()')
s = s.replace('            # Close the browser\n            driver.quit()\n\n            return True\n        except:\n            self.browser.quit()\n            return False', '            return True\n        except Exception as exc:\n            warning(f"YouTube upload failed ({type(exc).__name__}); no cross-post will run.")\n            return False\n        finally:\n            self.close_browser()')
p.write_text(s)

p = root / 'src/main.py'
s = p.read_text()
s = s.replace('                    rem_temp_files()\n', '')
s = s.replace('                    user_input = int(question("Select an option: "))\n                    tts = TTS()\n', '''                    try:
                        user_input = int(question("Select an option: ").strip())
                    except ValueError:
                        warning("Please enter a menu number, not a terminal command.")
                        continue
''', 1)
s = s.replace('                        generate_and_upload_short(youtube, tts)\n', '                        generate_and_upload_short(youtube, TTS())\n', 1)
s = s.replace('                        generate_and_upload_short(youtube, tts, topic=custom_topic)\n', '                        generate_and_upload_short(youtube, TTS(), topic=custom_topic)\n', 1)
p.write_text(s)

p = root / 'requirements.txt'
s = p.read_text().replace('\nmoviepy\n', '\n# The application uses MoviePy 1.x APIs; v2 removes moviepy.editor.\nmoviepy==1.0.3\nnumpy>=1.26,<2\n')
p.write_text(s)

p = root / 'tests/test_youtube_custom_topic.py'
s = p.read_text()
s = s.replace('    youtube.image_prompts = []', '    youtube.images = []\n    youtube.image_prompts = []')
s = s.replace('    youtube.generate_prompts = Mock()\n    youtube.generate_image = Mock()', '    youtube.generate_prompts = Mock(side_effect=lambda: setattr(youtube, "image_prompts", ["A cat"]))\n    youtube.generate_image = Mock(side_effect=lambda prompt: youtube.images.append("cat.png"))')
p.write_text(s)
