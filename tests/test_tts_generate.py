import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tts_generate import TTSGenerationError, TTSProvider, generate_voiceover_audio


class FakeProvider(TTSProvider):
    provider_name = "fake"
    voice = "fake-voice"

    def __init__(self, fail_on: set[int] | None = None):
        self.fail_on = fail_on or set()
        self.calls = []

    def synthesize(self, text: str, out_path: Path) -> float:
        order = int(out_path.stem.split("_")[-1])
        self.calls.append(order)
        if order in self.fail_on:
            raise TTSGenerationError("forced test failure")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(f"fake mp3 {order}".encode("utf-8"))
        return 1.25 * order


def sample_scenes():
    return [
        {"order": 1, "voiceover": "第一段口播"},
        {"order": 2, "voiceover": "第二段口播"},
        {"order": 3, "voiceover": "第三段口播"},
    ]


def test_generate_voiceover_audio_backfills_scene_audio(tmp_path: Path):
    scenes = sample_scenes()
    audio = generate_voiceover_audio(scenes, {}, tmp_path, provider_name="fake", provider=FakeProvider())

    assert audio == {
        "provider": "fake",
        "voice": "fake-voice",
        "segments": 3,
        "total_audio_duration": 7.5,
    }
    assert scenes[0]["voiceover_audio"] == {
        "file": "voiceover_audio/scene_01.mp3",
        "audio_duration": 1.25,
        "provider": "fake",
        "voice": "fake-voice",
    }
    assert (tmp_path / "voiceover_audio" / "scene_03.mp3").exists()


def test_generate_voiceover_audio_continues_after_segment_failure(tmp_path: Path):
    scenes = sample_scenes()
    audio = generate_voiceover_audio(scenes, {}, tmp_path, provider_name="fake", provider=FakeProvider(fail_on={2}))

    assert audio["segments"] == 2
    assert audio["total_audio_duration"] == 5.0
    assert "voiceover_audio" in scenes[0]
    assert "voiceover_audio" not in scenes[1]
    assert "voiceover_audio" in scenes[2]


def test_generate_voiceover_audio_none_provider_skips_audio(tmp_path: Path):
    scenes = sample_scenes()
    audio = generate_voiceover_audio(scenes, {}, tmp_path, provider_name="none")

    assert audio["provider"] == "none"
    assert audio["segments"] == 0
    assert not (tmp_path / "voiceover_audio").exists()
    assert all("voiceover_audio" not in scene for scene in scenes)


def test_failed_run_keeps_existing_audio_files(tmp_path: Path):
    scenes = sample_scenes()
    first_audio = generate_voiceover_audio(scenes, {}, tmp_path, provider_name="fake", provider=FakeProvider())
    existing_file = tmp_path / "voiceover_audio" / "scene_01.mp3"
    existing_file.write_bytes(b"existing good audio")

    failed_scenes = sample_scenes()
    failed_audio = generate_voiceover_audio(
        failed_scenes,
        {},
        tmp_path,
        provider_name="fake",
        provider=FakeProvider(fail_on={1, 2, 3}),
    )

    assert first_audio["segments"] == 3
    assert failed_audio["segments"] == 0
    assert existing_file.exists()
    assert existing_file.read_bytes() == b"existing good audio"
    assert not (tmp_path / "voiceover_audio.tmp").exists()


def test_incremental_voiceover_regenerates_only_selected_order(tmp_path: Path):
    scenes = sample_scenes()
    generate_voiceover_audio(scenes, {}, tmp_path, provider_name="fake", provider=FakeProvider())
    audio_dir = tmp_path / "voiceover_audio"
    scene_1 = audio_dir / "scene_01.mp3"
    scene_2 = audio_dir / "scene_02.mp3"
    scene_3 = audio_dir / "scene_03.mp3"
    scene_1.write_bytes(b"old 1")
    scene_2.write_bytes(b"old 2")
    scene_3.write_bytes(b"old 3")
    scenes[0]["voiceover_audio"]["audio_duration"] = 11.0
    scenes[2]["voiceover_audio"]["audio_duration"] = 33.0

    provider = FakeProvider()
    audio = generate_voiceover_audio(scenes, {}, tmp_path, provider_name="fake", provider=provider, only_orders={2})

    assert provider.calls == [2]
    assert scene_1.read_bytes() == b"old 1"
    assert scene_2.read_bytes() == b"fake mp3 2"
    assert scene_3.read_bytes() == b"old 3"
    assert scenes[0]["voiceover_audio"]["audio_duration"] == 11.0
    assert scenes[1]["voiceover_audio"]["audio_duration"] == 2.5
    assert scenes[2]["voiceover_audio"]["audio_duration"] == 33.0
    assert audio == {
        "provider": "fake",
        "voice": "fake-voice",
        "segments": 3,
        "total_audio_duration": 46.5,
    }


def test_incremental_voiceover_failure_preserves_old_segment(tmp_path: Path):
    scenes = sample_scenes()
    generate_voiceover_audio(scenes, {}, tmp_path, provider_name="fake", provider=FakeProvider())
    audio_dir = tmp_path / "voiceover_audio"
    scene_2 = audio_dir / "scene_02.mp3"
    scene_2.write_bytes(b"old good 2")
    old_meta = dict(scenes[1]["voiceover_audio"])

    provider = FakeProvider(fail_on={2})
    audio = generate_voiceover_audio(scenes, {}, tmp_path, provider_name="fake", provider=provider, only_orders={2})

    assert provider.calls == [2]
    assert scene_2.read_bytes() == b"old good 2"
    assert scenes[1]["voiceover_audio"] == old_meta
    assert audio["segments"] == 3
    assert audio["total_audio_duration"] == 7.5
    assert not (tmp_path / "voiceover_audio.incremental.tmp").exists()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        test_generate_voiceover_audio_backfills_scene_audio(base / "success")
        test_generate_voiceover_audio_continues_after_segment_failure(base / "failure")
        test_generate_voiceover_audio_none_provider_skips_audio(base / "none")
        test_failed_run_keeps_existing_audio_files(base / "failed_keeps_existing")
        test_incremental_voiceover_regenerates_only_selected_order(base / "incremental")
        test_incremental_voiceover_failure_preserves_old_segment(base / "incremental_failure")
    print("tts_generate tests passed")
