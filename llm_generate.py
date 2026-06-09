import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod


EFFECTS = ["slow_zoom_in", "pan_up", "cut", "caption_pop", "slow_zoom_out"]
ASSET_TYPES = ["门店/封面图", "环境/服务图", "核心卖点图", "流程/细节图", "引导/收尾图"]


class LLMGenerationError(RuntimeError):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class LLMProvider(ABC):
    @abstractmethod
    def generate_json(self, prompt: str, last_error: str | None = None) -> dict:
        raise NotImplementedError


class MockProvider(LLMProvider):
    def generate_json(self, prompt: str, last_error: str | None = None) -> dict:
        payload = json.loads(prompt)
        shop = payload["input"]["shop"]
        config = payload["config"]
        topic = shop.get("topic") or f"{shop.get('industry', '本地服务')}服务介绍"
        offer = shop.get("main_offer") or "服务流程清楚，沟通透明"
        area = shop.get("city_area") or "附近"
        target = shop.get("target_customer") or "第一次了解服务的用户"
        cta = shop.get("cta") or "有需要可以提前咨询了解"
        industry = shop.get("industry", "本地服务")

        scene_count = _scene_count(payload)
        script_lines = [
            f"{area}想了解{topic}，可以先看这几个重点。",
            f"如果你是{target}，最需要先确认环境、流程和沟通方式。",
            f"这里的核心卖点是：{offer}。",
            "先把关心的问题问清楚，再决定是否到店，会更稳妥。",
            cta,
        ][:scene_count]

        scenes = []
        for idx, line in enumerate(script_lines):
            scenes.append(
                {
                    "order": idx + 1,
                    "asset_type": ASSET_TYPES[idx % len(ASSET_TYPES)],
                    "caption": line,
                    "voiceover": line,
                    "effect": EFFECTS[idx % len(EFFECTS)],
                    "edited": False,
                }
            )

        return {
            "analysis": {
                "selling_points": [offer, "流程透明", "适合首次了解"],
                "pain_points": [f"{target}担心信息不清楚", "不知道到店前该问什么", "怕流程不透明"],
                "hook_angles": [topic, f"{industry}首次体验注意事项", "先了解流程再决定"],
                "recommended_structure": "痛点-流程-卖点-信任-引导",
                "reasoning": "mock 模式使用门店信息生成稳定合法结构，用于离线测试和无 API key 演示。",
            },
            "script": {
                "topic": topic,
                "cover_text": _cover_text(topic),
                "titles": _titles(shop, topic),
                "post_copy": f"{topic}整理了一版，适合第一次了解的朋友先做参考。具体情况建议结合自身需求，到正规机构当面咨询。",
                "bgm_suggestion": "克制、干净、轻奢感的低速背景音乐",
            },
            "scenes": scenes,
        }


class ClaudeProvider(LLMProvider):
    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or os.environ.get("CLAUDE_MODEL") or "claude-sonnet-4-6"
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
        if not self.api_key:
            raise LLMGenerationError("Claude provider requires ANTHROPIC_API_KEY or CLAUDE_API_KEY in the environment.")

    def generate_json(self, prompt: str, last_error: str | None = None) -> dict:
        instruction = build_claude_instruction(prompt, last_error)
        body = {
            "model": self.model,
            "max_tokens": 3000,
            "temperature": 0.4,
            "messages": [{"role": "user", "content": instruction}],
            "tools": [video_content_tool_schema()],
            "tool_choice": {"type": "tool", "name": "emit_video_content"},
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "content-type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            retryable = exc.code == 429 or 500 <= exc.code <= 599
            raise LLMGenerationError(f"Claude API HTTP {exc.code}: {detail}", retryable=retryable) from exc
        except urllib.error.URLError as exc:
            raise LLMGenerationError(f"Claude API request failed: {exc}", retryable=True) from exc

        for item in data.get("content", []):
            if item.get("type") == "tool_use" and item.get("name") == "emit_video_content":
                tool_input = item.get("input")
                if isinstance(tool_input, dict):
                    return tool_input
                raise LLMGenerationError("Claude tool_use input was not an object.", retryable=True)
        raise LLMGenerationError("Claude response did not contain emit_video_content tool_use input.", retryable=True)


def generate_video_content(project_input: dict, provider_name: str = "mock", max_retries: int = 3) -> dict:
    provider = make_provider(provider_name)
    prompt = json.dumps(project_input, ensure_ascii=False, indent=2)
    last_error = None
    for attempt in range(max_retries):
        try:
            candidate = provider.generate_json(prompt, last_error)
        except LLMGenerationError as exc:
            if exc.retryable and attempt < max_retries - 1:
                last_error = str(exc)
                continue
            raise
        errors = validate_generation(candidate, project_input)
        if not errors:
            apply_timeline(candidate, int(project_input["config"]["duration_seconds"]))
            timeline_errors = validate_timeline(candidate["scenes"], int(project_input["config"]["duration_seconds"]))
            if timeline_errors:
                raise LLMGenerationError("; ".join(timeline_errors))
            return candidate
        last_error = "; ".join(errors)
    raise LLMGenerationError(f"LLM output failed validation after {max_retries} attempts: {last_error}")


def make_provider(provider_name: str) -> LLMProvider:
    if provider_name == "mock":
        return MockProvider()
    if provider_name == "claude":
        return ClaudeProvider()
    raise LLMGenerationError("provider must be one of: mock, claude")


def build_project_input(config: dict, assets: list[dict] | None = None, sources: list[dict] | None = None) -> dict:
    return {
        "schema_version": "1.0",
        "project_id": str(config.get("project_id") or "local-demo"),
        "status": "analyzing",
        "input": {
            "shop": {
                "shop_name": config.get("shop_name", ""),
                "industry": config.get("industry", ""),
                "city_area": config.get("city_area", ""),
                "topic": config.get("topic", ""),
                "main_offer": config.get("main_offer", ""),
                "target_customer": config.get("target_customer", ""),
                "tone": config.get("tone", ""),
                "cta": config.get("cta", ""),
            },
            "sources": sources or [],
            "assets": assets or [],
        },
        "config": {
            "aspect_ratio": config.get("aspect_ratio", "9:16"),
            "visual_style": config.get("visual_style", "premium_luxe"),
            "duration_seconds": int(config.get("duration_seconds", 24)),
            "platform": config.get("platform", "generic"),
            "compliance_mode": config.get("compliance_mode", ""),
        },
    }


def validate_generation(candidate: dict, project_input: dict) -> list[str]:
    errors = []
    if not isinstance(candidate, dict):
        return ["output must be an object"]
    analysis = candidate.get("analysis")
    script = candidate.get("script")
    scenes = candidate.get("scenes")
    if not isinstance(analysis, dict):
        errors.append("analysis must be an object")
    else:
        for key in ["selling_points", "pain_points", "hook_angles"]:
            if not isinstance(analysis.get(key), list) or not analysis.get(key):
                errors.append(f"analysis.{key} must be a non-empty array")
        for key in ["recommended_structure", "reasoning"]:
            if not str(analysis.get(key, "")).strip():
                errors.append(f"analysis.{key} is required")
    if not isinstance(script, dict):
        errors.append("script must be an object")
    else:
        for key in ["topic", "cover_text", "post_copy", "bgm_suggestion"]:
            if not str(script.get(key, "")).strip():
                errors.append(f"script.{key} is required")
        if not isinstance(script.get("titles"), list) or not script.get("titles"):
            errors.append("script.titles must be a non-empty array")
    if not isinstance(scenes, list) or not scenes:
        errors.append("scenes must be a non-empty array")
    else:
        for idx, scene in enumerate(scenes, start=1):
            if int(scene.get("order", 0)) != idx:
                errors.append(f"scene {idx} order must equal {idx}")
            for key in ["caption", "voiceover", "effect"]:
                if not str(scene.get(key, "")).strip():
                    errors.append(f"scene {idx}.{key} is required")
    duration = int(project_input["config"]["duration_seconds"])
    if duration < 15 or duration > 45:
        errors.append("config.duration_seconds must be between 15 and 45")
    return errors


def validate_timeline(scenes: list[dict], total_duration: int) -> list[str]:
    errors = []
    cursor = 0
    for idx, scene in enumerate(scenes, start=1):
        start = scene.get("start")
        duration = scene.get("duration")
        if start != cursor:
            errors.append(f"scene {idx} start must be {cursor}, got {start}")
        if not isinstance(duration, int) or duration < 3:
            return [f"scene {idx} duration must be an integer >= 3"]
        cursor += duration
    if cursor != total_duration:
        errors.append(f"scene timeline must sum to {total_duration}, got {cursor}")
    return errors


def apply_timeline(generated: dict, total_duration: int) -> None:
    scenes = generated["scenes"]
    durations = _scene_duration(total_duration, len(scenes))
    cursor = 0
    for idx, scene in enumerate(scenes):
        scene["order"] = idx + 1
        scene["start"] = cursor
        scene["duration"] = durations[idx]
        scene.setdefault("asset_type", ASSET_TYPES[idx % len(ASSET_TYPES)])
        scene.setdefault("effect", EFFECTS[idx % len(EFFECTS)])
        scene.setdefault("edited", False)
        cursor += durations[idx]


def legacy_plan_from_generation(config: dict, generated: dict) -> dict:
    script = generated["script"]
    return {
        "shop_name": config.get("shop_name", "本地门店"),
        "industry": config.get("industry", "本地服务"),
        "topic": script["topic"],
        "platform": config.get("platform", "generic"),
        "aspect_ratio": config.get("aspect_ratio", "9:16"),
        "visual_style": config.get("visual_style", "premium_luxe"),
        "duration_seconds": sum(scene["duration"] for scene in generated["scenes"]),
        "cover_text": script["cover_text"],
        "titles": script["titles"],
        "post_copy": script["post_copy"],
        "scenes": generated["scenes"],
        "subtitle_style": "premium_readable",
        "bgm_style": script.get("bgm_suggestion", "clean_light"),
    }


def build_claude_instruction(prompt: str, last_error: str | None) -> str:
    retry_note = f"\nPrevious output validation error: {last_error}\n" if last_error else ""
    return f"""
You generate structured content for a local business promotional video.
Use the emit_video_content tool. Do not answer with free-form text.

Required top-level keys:
- analysis
- script
- scenes

Rules:
- Generate Chinese copy unless the input clearly asks otherwise.
- Do not include start or duration; the program computes timeline.
- scenes must be 3 to 5 items.
- Each scene requires order, asset_type, caption, voiceover, effect, edited.
- edited must be false.
- Avoid medical treatment guarantees, cure rates, absolute claims, and patient testimonials.
{retry_note}
Input project JSON:
{prompt}
""".strip()


def video_content_tool_schema() -> dict:
    return {
        "name": "emit_video_content",
        "description": "Emit M1 structured video analysis, script, and scene content.",
        "input_schema": {
            "type": "object",
            "required": ["analysis", "script", "scenes"],
            "properties": {
                "analysis": {
                    "type": "object",
                    "required": ["selling_points", "pain_points", "hook_angles", "recommended_structure", "reasoning"],
                    "properties": {
                        "selling_points": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                        "pain_points": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                        "hook_angles": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                        "recommended_structure": {"type": "string"},
                        "reasoning": {"type": "string"},
                    },
                },
                "script": {
                    "type": "object",
                    "required": ["topic", "cover_text", "titles", "post_copy", "bgm_suggestion"],
                    "properties": {
                        "topic": {"type": "string"},
                        "cover_text": {"type": "string"},
                        "titles": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                        "post_copy": {"type": "string"},
                        "bgm_suggestion": {"type": "string"},
                    },
                },
                "scenes": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 5,
                    "items": {
                        "type": "object",
                        "required": ["order", "asset_type", "caption", "voiceover", "effect", "edited"],
                        "properties": {
                            "order": {"type": "integer"},
                            "asset_type": {"type": "string"},
                            "caption": {"type": "string"},
                            "voiceover": {"type": "string"},
                            "effect": {"type": "string", "enum": EFFECTS},
                            "edited": {"type": "boolean"},
                        },
                    },
                },
            },
        },
    }


def _scene_count(project_input: dict) -> int:
    assets = project_input.get("input", {}).get("assets") or []
    return min(max(len(assets), 3), 5)


def _scene_duration(total: int, count: int) -> list[int]:
    base = max(3, total // count)
    durations = [base for _ in range(count)]
    diff = total - sum(durations)
    idx = 0
    while diff != 0:
        step = 1 if diff > 0 else -1
        if durations[idx] + step >= 3:
            durations[idx] += step
            diff -= step
        idx = (idx + 1) % count
    return durations


def _cover_text(topic: str) -> str:
    topic = str(topic).strip()
    return topic if len(topic) <= 14 else topic[:14] + "..."


def _titles(shop: dict, topic: str) -> list[str]:
    area = shop.get("city_area") or "附近"
    name = shop.get("shop_name") or "这家店"
    industry = shop.get("industry") or "本地服务"
    return [
        f"{area}想了解{topic}，先看这条",
        f"第一次来{name}前，可以先看这几点",
        f"{topic}别急着决定，先把流程问清楚",
        f"给第一次了解{industry}的人一点参考",
        f"{name}服务流程简单介绍",
    ]
