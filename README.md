# AI Short Video Workflow POC

An early prototype for producing short-video drafts for local merchants.

The workflow accepts a small amount of shop information plus 1-5 images, then generates:

- a storyboard and edit plan
- title ideas
- publishing copy
- captions
- voiceover text
- a GIF preview
- an HTML video preview
- configurable aspect ratios and visual styles

The core idea is simple: the AI should not manually operate a video editor. It should create a structured edit plan that rendering tools can execute.

![demo preview](output/preview.gif)

## Why This Exists

Small local businesses often do not have enough content material, editing skill, or operational patience to use complex creator tools.

This project explores a lower-friction workflow:

```text
Shop info + a few images
  -> topic/script/storyboard
  -> compliance check
  -> captions and voiceover text
  -> preview render
  -> future: CozyVoice TTS
  -> future: FFmpeg/Remotion MP4 export
```

## Project Structure

```text
ai_video_workflow_poc/
  config.example.json
  input/
    images/
  output/
    preview.gif
    preview.html
    video_plan.md
    plan.json
    captions.srt
    voiceover.txt
    voiceover_segments/
  docs/
  scripts/
  run_workflow.py
  record_preview.js
```

## Quick Start

From PowerShell:

```powershell
.\scripts\run_demo.ps1
```

Or run Python directly:

```powershell
python .\run_workflow.py --demo-assets --clean
```

If `python` is not available on PATH inside Codex Desktop, use the bundled runtime:

```powershell
& "C:\Users\LCL\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\run_workflow.py --demo-assets --clean
```

## Inputs

Copy `config.example.json` to `config.json`, then edit the shop information.

Put 1-5 images into:

```text
input/images/
```

One image is enough for the workflow to run. Three or more images usually produce a better preview.

You can adjust the output canvas and style in `config.json`:

```json
{
  "aspect_ratio": "9:16",
  "visual_style": "premium_luxe"
}
```

Supported aspect ratios: `9:16`, `16:9`, `1:1`.

Supported visual styles: `premium_luxe`, `clean_clinic`, `warm_local`, `bold_product`.

## Outputs

- `output/video_plan.md`: human-readable topic, titles, scenes, publishing copy, and compliance result.
- `output/plan.json`: machine-readable edit plan for future FFmpeg/Remotion rendering.
- `output/captions.srt`: generated subtitles.
- `output/voiceover.txt`: full voiceover text.
- `output/voiceover_segments/*.txt`: scene-level TTS input for CozyVoice.
- `output/preview.gif`: lightweight visual preview.
- `output/preview.html`: configurable-aspect-ratio HTML preview.

## Local Copy Editor

After generating `output/plan.json`, start the local review page:

```powershell
& "C:\Users\LCL\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\web_app.py
```

Then open:

```text
http://127.0.0.1:5000
```

The first editor phase only changes copy fields in `plan.json`. It also syncs `captions.srt`, `voiceover.txt`, `voiceover_segments/*.txt`, and `video_plan.md`. Existing audio and video files need to be regenerated before they reflect the edited copy.

## Current Capabilities

- Low material threshold: works with 1-5 images.
- Generates a structured storyboard.
- Generates captions and voiceover text.
- Creates GIF and HTML previews without FFmpeg.
- Adds a basic medical-marketing risk-word check.
- Keeps customer/private config out of Git through `.gitignore`.

## Roadmap

- Add real LLM generation through environment variables.
- Add CozyVoice TTS output.
- Add FFmpeg MP4 export with captions, BGM, and voiceover.
- Add more vertical templates for local businesses.
- Add a review dashboard for operator workflows.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)
- [CozyVoice integration notes](docs/COSYVOICE.md)
- [Style controls](docs/STYLE_CONTROLS.md)
- [GitHub setup guide](docs/GITHUB_START.md)
- [Security notes](SECURITY.md)

## Security

Do not commit API keys, `.env`, customer photos, patient records, private business data, or real medical cases.

Use environment variables for credentials. Keep `config.example.json` public and keep `config.json` local.
