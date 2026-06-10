import asyncio
import shutil
from abc import ABC, abstractmethod
from pathlib import Path


DEFAULT_EDGE_VOICE = "zh-CN-XiaoxiaoNeural"


class TTSGenerationError(RuntimeError):
    pass


class TTSProvider(ABC):
    provider_name = ""
    voice = ""

    @abstractmethod
    def synthesize(self, text: str, out_path: Path) -> float:
        raise NotImplementedError


class EdgeTTSProvider(TTSProvider):
    provider_name = "edge"

    def __init__(self, voice: str = DEFAULT_EDGE_VOICE, rate: str = "+0%", volume: str = "+0%"):
        self.voice = voice
        self.rate = rate
        self.volume = volume

    def synthesize(self, text: str, out_path: Path) -> float:
        text = text.strip()
        if not text:
            raise TTSGenerationError("voiceover text is empty")
        return asyncio.run(self._synthesize(text, out_path))

    async def _synthesize(self, text: str, out_path: Path) -> float:
        try:
            import edge_tts
        except ImportError as exc:
            raise TTSGenerationError("edge-tts is not installed. Run pip install -r requirements.txt or use --skip-tts.") from exc

        # edge-tts is only a free validation path. Production/commercial TTS should use ADR-009 providers.
        communicate = edge_tts.Communicate(text, self.voice, rate=self.rate, volume=self.volume)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        last_boundary_end = 0.0
        with out_path.open("wb") as audio_file:
            try:
                async for chunk in communicate.stream():
                    chunk_type = chunk.get("type")
                    if chunk_type == "audio":
                        audio_file.write(chunk.get("data", b""))
                    elif chunk_type in {"WordBoundary", "SentenceBoundary"}:
                        last_boundary_end = max(last_boundary_end, _boundary_end_seconds(chunk))
            except Exception as exc:
                raise TTSGenerationError(f"edge-tts synthesis failed: {exc}") from exc

        if not out_path.exists() or out_path.stat().st_size == 0:
            raise TTSGenerationError("edge-tts generated an empty audio file")
        return round(last_boundary_end or estimate_audio_duration(text), 3)


class AliyunProvider(TTSProvider):
    provider_name = "aliyun"

    def __init__(self, voice: str = "cosyvoice-default"):
        self.voice = voice

    def synthesize(self, text: str, out_path: Path) -> float:
        raise TTSGenerationError(
            "Aliyun/CosyVoice TTS provider is not implemented yet. Use --tts-provider edge or --skip-tts."
        )


class NoneProvider(TTSProvider):
    provider_name = "none"
    voice = ""

    def synthesize(self, text: str, out_path: Path) -> float:
        raise TTSGenerationError("none provider does not synthesize audio")


def make_tts_provider(provider_name: str, config: dict | None = None) -> TTSProvider:
    config = config or {}
    if provider_name == "edge":
        return EdgeTTSProvider(
            voice=str(config.get("tts_voice") or DEFAULT_EDGE_VOICE),
            rate=str(config.get("tts_rate") or "+0%"),
            volume=str(config.get("tts_volume") or "+0%"),
        )
    if provider_name == "aliyun":
        return AliyunProvider(voice=str(config.get("tts_voice") or "cosyvoice-default"))
    if provider_name == "none":
        return NoneProvider()
    raise TTSGenerationError("tts provider must be one of: edge, aliyun, none")


def generate_voiceover_audio(
    scenes: list[dict],
    config: dict | None,
    out_dir: Path | str,
    provider_name: str = "edge",
    provider: TTSProvider | None = None,
) -> dict:
    out_dir = Path(out_dir)
    provider = provider or make_tts_provider(provider_name, config)
    summary = {
        "provider": provider.provider_name,
        "voice": provider.voice,
        "segments": 0,
        "total_audio_duration": 0.0,
    }
    if isinstance(provider, NoneProvider):
        return summary

    audio_dir = out_dir / "voiceover_audio"
    temp_audio_dir = out_dir / "voiceover_audio.tmp"
    if temp_audio_dir.exists():
        shutil.rmtree(temp_audio_dir)
    temp_audio_dir.mkdir(parents=True, exist_ok=True)

    failures = []
    total_duration = 0.0
    for idx, scene in enumerate(scenes, start=1):
        order = _scene_order(scene, idx)
        text = str(scene.get("voiceover", "")).strip()
        filename = f"scene_{order:02d}.mp3"
        rel_file = f"voiceover_audio/{filename}"
        try:
            duration = provider.synthesize(text, temp_audio_dir / filename)
        except TTSGenerationError as exc:
            failures.append(f"scene {order:02d}: {exc}")
            continue

        duration = round(float(duration), 3)
        scene["voiceover_audio"] = {
            "file": rel_file,
            "audio_duration": duration,
            "provider": provider.provider_name,
            "voice": provider.voice,
        }
        summary["segments"] += 1
        total_duration += duration

    summary["total_audio_duration"] = round(total_duration, 3)
    if summary["segments"] > 0:
        if audio_dir.exists():
            shutil.rmtree(audio_dir)
        shutil.move(str(temp_audio_dir), str(audio_dir))
    elif temp_audio_dir.exists():
        shutil.rmtree(temp_audio_dir)
    if failures:
        print("TTS warnings:")
        for failure in failures:
            print(f"- {failure}")
    return summary


def estimate_audio_duration(text: str) -> float:
    compact = "".join(ch for ch in text if not ch.isspace())
    return round(max(1.0, len(compact) / 4.5), 3)


def _scene_order(scene: dict, fallback: int) -> int:
    try:
        order = int(scene.get("order", fallback))
    except (TypeError, ValueError):
        return fallback
    return order if order > 0 else fallback


def _boundary_end_seconds(chunk: dict) -> float:
    offset = _edge_ticks_to_seconds(chunk.get("offset", 0))
    duration = _edge_ticks_to_seconds(chunk.get("duration", 0))
    return offset + duration


def _edge_ticks_to_seconds(value) -> float:
    try:
        return float(value) / 10_000_000
    except (TypeError, ValueError):
        return 0.0
