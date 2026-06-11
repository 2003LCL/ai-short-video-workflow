import os
from datetime import datetime
from pathlib import Path
from typing import Callable


FPS = 30
TAIL_PAD = 0.6
MP4_FILE = "video.mp4"


class MP4RenderError(RuntimeError):
    pass


def scene_audio_duration(scene: dict) -> float:
    audio = scene.get("voiceover_audio") or {}
    try:
        return max(0.0, float(audio.get("audio_duration") or 0.0))
    except (TypeError, ValueError):
        return 0.0


def effective_scene_duration(scene: dict, tail_pad: float = TAIL_PAD) -> float:
    audio_duration = scene_audio_duration(scene)
    try:
        scene_duration = float(scene.get("duration") or 0.0)
    except (TypeError, ValueError):
        scene_duration = 0.0
    return max(scene_duration, audio_duration + tail_pad if audio_duration else 0.0)


def build_render_timeline(scenes: list[dict], tail_pad: float = TAIL_PAD) -> list[dict]:
    timeline = []
    cursor = 0.0
    for scene in scenes:
        duration = effective_scene_duration(scene, tail_pad=tail_pad)
        timeline.append({"scene": scene, "start": round(cursor, 3), "duration": round(duration, 3)})
        cursor += duration
    return timeline


def total_render_duration(scenes: list[dict], tail_pad: float = TAIL_PAD) -> float:
    return round(sum(item["duration"] for item in build_render_timeline(scenes, tail_pad=tail_pad)), 3)


def make_render_entry(plan: dict, kind: str, file: str, rendered_at: str | None = None) -> dict:
    return {
        "platform": plan.get("platform", "generic"),
        "aspect_ratio": plan.get("aspect_ratio", "9:16"),
        "kind": kind,
        "file": file,
        "rendered_at": rendered_at or datetime.now().isoformat(),
    }


def render_mp4(
    plan: dict,
    assets: list[dict],
    output_dir: Path | str,
    frame_renderer: Callable[[dict, list[dict], dict, int, int, int], list],
    fps: int = FPS,
    ss: int = 2,
) -> dict:
    try:
        import numpy as np
        from moviepy.audio.AudioClip import CompositeAudioClip
        from moviepy.audio.io.AudioFileClip import AudioFileClip
        from moviepy.video.io.ImageSequenceClip import ImageSequenceClip
    except ImportError as exc:
        raise MP4RenderError("moviepy is not installed. Run pip install -r requirements.txt or use --skip-mp4.") from exc

    output_dir = Path(output_dir)
    output_path = output_dir / MP4_FILE
    temp_path = output_dir / "video.tmp.mp4"
    if temp_path.exists():
        temp_path.unlink()

    audio_clips = []
    video_clip = None
    final_clip = None
    try:
        frames = []
        timeline = build_render_timeline(plan["scenes"])
        for idx, item in enumerate(timeline):
            n_frames = max(1, round(item["duration"] * fps))
            for frame in frame_renderer(plan, assets, item["scene"], idx, n_frames, ss):
                frames.append(np.array(frame.convert("RGB")))

            audio_file = ((item["scene"].get("voiceover_audio") or {}).get("file") or "").strip()
            if audio_file:
                audio_path = output_dir / audio_file
                if audio_path.exists():
                    audio_clips.append(AudioFileClip(str(audio_path)).set_start(item["start"]))
                else:
                    print(f"MP4 warning: audio file not found, rendering scene silent: {audio_file}")

        if not frames:
            raise MP4RenderError("no frames generated for MP4")

        video_clip = ImageSequenceClip(frames, fps=fps)
        if audio_clips:
            video_clip = video_clip.set_audio(CompositeAudioClip(audio_clips).set_duration(video_clip.duration))
        final_clip = video_clip
        final_clip.write_videofile(
            str(temp_path),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            verbose=False,
            logger=None,
        )
        os.replace(temp_path, output_path)
        return make_render_entry(plan, "mp4", MP4_FILE)
    except Exception as exc:
        if temp_path.exists():
            temp_path.unlink()
        if isinstance(exc, MP4RenderError):
            raise
        raise MP4RenderError(f"MP4 render failed: {exc}") from exc
    finally:
        for clip in audio_clips:
            clip.close()
        if video_clip is not None:
            video_clip.close()
        if final_clip is not None and final_clip is not video_clip:
            final_clip.close()
