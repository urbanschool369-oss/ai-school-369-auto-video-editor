# Contributing

Thanks for considering a contribution to Auto Video Editor.

## Ground rules

- Keep the core stdlib-only. Pillow stays optional.
- No API keys, no cloud uploads, no telemetry, no accounts.
- No secrets, phone numbers, email addresses, or private data in code, docs, or examples.
- Keep the README "Honest limits" section in sync with what the code actually does. Do not claim transcription, AI B-roll, or licensed music until it is implemented and tested.
- Keep the signature "Shekar Kaki" on cards and in code headers.

## How to contribute

1. Fork the repo and create a branch from `main`.
2. Make a small, focused change.
3. Test it end-to-end with a sample video: `python3 app.py raw.mp4 --script examples/script.txt --out edited.mp4`
4. Check the output with `ffprobe` and at least one frame per segment (intro, main, B-roll, outro).
5. Update README, docs/process-flow.md, and CHANGELOG.md if behaviour changes.
6. Open a pull request describing what changed and how you tested it.

## Reporting issues

Include: OS, Python version, ffmpeg version (`ffmpeg -version`), the exact command, and the full error output. Do not attach private videos.
