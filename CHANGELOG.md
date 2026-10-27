# Changelog

## v1.0.0 — 2026-10-27

- Initial public release.
- Web UI (http://localhost:8765) and CLI.
- Intro, Key Point B-roll, and outro cards in light blue #D6EAF8, with signature Shekar Kaki.
- Captions burned in from a pasted script (SRT, timed evenly).
- Main video split into 3 parts with B-roll insertion.
- Background music pad mixed at low volume with fade-out.
- Process flow diagram (SVG + Mermaid) and step-by-step docs.
- Verified test: 30 s raw video -> 38.1 s edited video, 1280x720, H.264 + AAC.

Known limits in v1.0.0: captions need a pasted script (no bundled Whisper), B-roll is cards not AI stock footage, BGM is a synthesized pad, SFX whoosh is generated but v1 mixes BGM + main audio cleanly.
