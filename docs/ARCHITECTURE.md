# Architecture

This POC treats AI video production as a controlled workflow rather than a free-form chatbot.

```text
Shop info + images
  -> Topic and script generation
  -> Scene/storyboard plan
  -> Compliance check
  -> Captions and voiceover text
  -> HTML/GIF preview render
  -> Future: CozyVoice TTS
  -> Future: FFmpeg/Remotion MP4 export
```

## Core Idea

The agent should not manually operate a video editor. It should produce a structured edit plan that render tools can execute.

```json
{
  "duration_seconds": 24,
  "scenes": [
    {
      "start": 0,
      "duration": 8,
      "asset_type": "门店/封面图",
      "caption": "本地社区想了解第一次洗牙前要知道什么，可以先看这几个点。",
      "effect": "slow_zoom_in"
    }
  ]
}
```

## Current Modules

- `run_workflow.py`: generates the script, storyboard, captions, voiceover text, compliance result, HTML preview, and GIF preview.
- `record_preview.js`: optional browser-based recording hook.
- `config.example.json`: sample shop input.
- `output/plan.json`: machine-readable edit plan.
- `output/voiceover_segments/`: text files ready for TTS.

## Medical Content Guardrail

The first version includes a simple risk-word gate for medical marketing expressions. This is not a legal compliance engine. It is a first-pass warning layer before human review.
