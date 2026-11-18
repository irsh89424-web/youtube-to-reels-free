---
name: youtube-to-reels
description: Create 30–60 second vertical clips from an authorized YouTube video using free GitHub Actions processing, faster-whisper transcription and animated captions.
---

# YouTube to Reels (free)

This version needs no Claude subscription and no OpenAI API key. GitHub Actions runs faster-whisper on CPU; highlight selection uses a transcript-scoring heuristic, not a generative AI model, so review results before publishing.

Only process videos you own or have permission to download, edit and republish. Never bypass DRM, sign-in gates, paywalls or access restrictions.

## Steps
1. Extract the YouTube URL; ask for it if absent.
2. Confirm republishing rights if unclear.
3. Check `gh auth status`.
4. Dispatch:
   ```bash
   gh workflow run youtube-to-reels.yml --ref main \
     -f video_url="YOUTUBE_URL" -f max_clips="3" -f model_size="base"
   ```
5. Find and verify the latest run:
   ```bash
   gh run list --workflow "YouTube to Reels (Free)" --limit 1 \
     --json databaseId,status,conclusion,headBranch,createdAt
   ```
6. Monitor with `gh run watch RUN_ID --exit-status`.
7. Download with `mkdir -p downloads && gh run download RUN_ID --dir downloads/RUN_ID`.
8. List actual MP4 files. Do not claim success unless the workflow succeeded and files exist.
9. On failure, inspect `gh run view RUN_ID --log-failed`.

Defaults: up to 3 clips, 30–60 seconds, base Whisper model, 1080×1920 MP4, centre crop, original audio, word-timed white/yellow captions. Artifacts expire after 7 days.
