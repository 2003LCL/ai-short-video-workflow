import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import render_mp4
from render_mp4 import build_render_timeline, effective_scene_duration, make_render_entry, render_mp4 as render_video


def sample_plan():
    return {
        "platform": "generic",
        "aspect_ratio": "9:16",
        "scenes": [
            {
                "order": 1,
                "duration": 8,
                "caption": "第一段",
                "voiceover_audio": {"file": "voiceover_audio/scene_01.mp3", "audio_duration": 9.2},
            },
            {"order": 2, "duration": 7, "caption": "第二段"},
            {
                "order": 3,
                "duration": 6,
                "caption": "第三段",
                "voiceover_audio": {"file": "voiceover_audio/scene_03.mp3", "audio_duration": 2.0},
            },
        ],
    }


def test_effective_scene_duration_uses_audio_plus_tail_pad():
    scene = {"duration": 8, "voiceover_audio": {"audio_duration": 8.4}}
    assert effective_scene_duration(scene) == 9.0
    assert effective_scene_duration({"duration": 8}) == 8.0
    assert effective_scene_duration({"duration": 8, "voiceover_audio": {"audio_duration": 2.0}}) == 8.0


def test_build_render_timeline_accumulates_effective_starts():
    timeline = build_render_timeline(sample_plan()["scenes"])
    assert timeline[0]["start"] == 0.0
    assert timeline[0]["duration"] == 9.8
    assert timeline[1]["start"] == 9.8
    assert timeline[1]["duration"] == 7.0
    assert timeline[2]["start"] == 16.8
    assert timeline[2]["duration"] == 6.0


def test_make_render_entry_contract_shape():
    entry = make_render_entry(sample_plan(), "mp4", "video.mp4", rendered_at="2026-06-11T12:00:00")
    assert entry == {
        "platform": "generic",
        "aspect_ratio": "9:16",
        "kind": "mp4",
        "file": "video.mp4",
        "rendered_at": "2026-06-11T12:00:00",
    }


def test_failed_render_keeps_existing_video(tmp_path: Path):
    old_video = tmp_path / "video.mp4"
    old_video.write_bytes(b"existing mp4")

    original_clip = render_mp4.ImageSequenceClip if hasattr(render_mp4, "ImageSequenceClip") else None

    def fake_frame_renderer(plan, assets, scene, idx, n_frames, ss):
        return []

    try:
        try:
            render_video(sample_plan(), [], tmp_path, fake_frame_renderer)
        except Exception:
            pass
        else:
            raise AssertionError("Expected render failure")
    finally:
        if original_clip is not None:
            render_mp4.ImageSequenceClip = original_clip

    assert old_video.exists()
    assert old_video.read_bytes() == b"existing mp4"
    assert not (tmp_path / "video.tmp.mp4").exists()


if __name__ == "__main__":
    test_effective_scene_duration_uses_audio_plus_tail_pad()
    test_build_render_timeline_accumulates_effective_starts()
    test_make_render_entry_contract_shape()
    with tempfile.TemporaryDirectory() as tmp:
        test_failed_render_keeps_existing_video(Path(tmp))
    print("render_mp4 tests passed")
