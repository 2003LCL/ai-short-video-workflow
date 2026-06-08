# Setup

## Minimal Setup

The current POC only requires Python and Pillow.

```powershell
pip install -r requirements.txt
```

Inside Codex Desktop, the bundled Python runtime can run the project without installing Python globally.

```powershell
.\scripts\run_demo.ps1
```

## Optional Tools

### FFmpeg

Needed for future MP4 export, audio mixing, subtitle burn-in, BGM, and platform-specific rendering.

### CozyVoice / CosyVoice

Recommended for higher-quality Chinese voiceover, especially if the product later supports repeatable brand voices.

Keep CozyVoice as a separate service or environment. This repository exports voiceover text files that can be sent to a TTS service.

### Playwright Browser Binary

Only needed if you want to record `preview.html` into WebM through `record_preview.js`.

## Environment Variables

Use `.env` locally, but never commit it.

```text
AI_API_KEY=
AI_BASE_URL=
AI_MODEL=
COSYVOICE_HOME=
COSYVOICE_MODEL=
COSYVOICE_SPEAKER=
```
