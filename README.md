# YouTube to Reels — Free GitHub Actions version

Create up to 3 vertical 30–60 second MP4 clips from an authorized YouTube video, with word-timed animated captions. **No OpenAI API key, Claude subscription, or paid inference API is required.**

## How it works
1. GitHub Actions downloads the source using `yt-dlp`.
2. FFmpeg extracts audio.
3. `faster-whisper` transcribes on the GitHub-hosted CPU runner.
4. A deterministic transcript-scoring algorithm selects possible highlights.
5. FFmpeg renders 1080×1920 MP4 clips with karaoke-style captions.
6. GitHub Actions uploads the clips as an artifact.

## Free-tier limits
GitHub Actions usage is subject to your plan's included minutes, storage and current policy. Private and public repositories may have different allowances. Video downloading and CPU transcription can take significant time; very long or high-resolution sources may time out or exceed runner storage. There is no paid AI API in this project, but cloud compute is not unlimited.

Only use videos you own or have explicit permission to download, edit and republish. Respect YouTube's terms, copyright, privacy and applicable law. This project does not bypass DRM, paywalls, sign-in gates or access controls.

## Setup

### 1. Create a repository
Create a repository at https://github.com/new named `youtube-to-reels`. Private is recommended for your code.

### 2. Upload all files
Preserve hidden folders:
- `.github/workflows/youtube-to-reels.yml`
- `.claude/skills/youtube-to-reels/SKILL.md`
- `.claude/skills/youtube-to-reels/references/editing-rules.md`
- `scripts/reels.py`
- `requirements.txt`
- `README.md`
- `.gitignore`
- `LICENSE`

Or use Git:
```bash
git clone https://github.com/YOUR_USERNAME/youtube-to-reels.git
cd youtube-to-reels
# Copy project files here, then:
git add .
git commit -m "Add free YouTube to Reels workflow"
git push -u origin main
```

### 3. No API secret required
This version does not need an OpenAI API key, billing account, or GitHub Actions secret.

### 4. Run from GitHub
1. Open the repository.
2. Select **Actions**.
3. Select **YouTube to Reels (Free)**.
4. Click **Run workflow**.
5. Paste a URL you are authorized to repurpose.
6. Choose clip count (up to 5) and model:
   - `tiny`: quickest, lower accuracy
   - `base`: recommended starting point
   - `small`: potentially better accuracy, slower and larger
7. Click **Run workflow**.
8. When complete, open the run and download its `reels-clips-*` artifact.

### 5. Claude Code is optional
Claude Code is not needed to run the GitHub workflow. If you already use it, open it in this repository and run:
```text
/youtube-to-reels https://www.youtube.com/watch?v=YOUR_VIDEO_ID
```
The skill uses GitHub CLI (`gh`) to dispatch and download. Install from https://cli.github.com/ and authenticate using `gh auth login`.

## Output
- `reel_01_highlight-1.mp4`, etc.
- `clips.json` with source timestamps and selection notes.
- `captions-transcript.txt` with the transcript.

MP4 format: 1080×1920, H.264 video, AAC audio, centre crop, word-timed white/yellow captions.

## Limitations
- Highlight selection is heuristic, not an LLM. It does not deeply understand context, narrative or virality. Review every clip.
- Centre crop is not face tracking and can cut off faces or on-screen text.
- Transcription accuracy varies with noise, accents and language. Faster-whisper supports multilingual transcription; optional language codes include `en`, `ml`, and `ar`.
- GitHub Actions runner time, disk and artifact retention are limited. Artifacts expire after seven days; download promptly.

## Optional local test
Requires Python 3.11+, FFmpeg and pip:
```bash
pip install -r requirements.txt
python scripts/reels.py --url "https://www.youtube.com/watch?v=YOUR_VIDEO_ID" \
  --max-clips 3 --min-seconds 30 --max-seconds 60 --model-size tiny
```
No API key is needed.

## Files
```text
.github/workflows/youtube-to-reels.yml
.claude/skills/youtube-to-reels/SKILL.md
.claude/skills/youtube-to-reels/references/editing-rules.md
scripts/reels.py
requirements.txt
README.md
.gitignore
LICENSE
```
