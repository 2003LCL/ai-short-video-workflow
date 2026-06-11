import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod


EFFECTS = ["slow_zoom_in", "pan_up", "cut", "caption_pop", "slow_zoom_out"]
ASSET_TYPES = ["门店/封面图", "环境/服务图", "核心卖点图", "流程/细节图", "引导/收尾图"]
COPY_STYLE_PUNCHY = "punchy_local"
COPY_STYLE_TRUST = "professional_trust"
COPY_STYLE_OPTIONS = {COPY_STYLE_PUNCHY, COPY_STYLE_TRUST}
PROFESSIONAL_TRUST_INDUSTRY_KEYWORDS = [
    "医疗",
    "口腔",
    "牙科",
    "医美",
    "诊所",
    "医院",
    "教育",
    "培训",
    "法律",
    "律师",
    "金融",
    "保险",
    "健康",
    "康复",
]
PUNCHY_LOCAL_INDUSTRY_KEYWORDS = [
    "餐饮",
    "小吃",
    "火锅",
    "烧烤",
    "零售",
    "便利店",
    "维修",
    "家电",
    "美业",
    "美容",
    "美甲",
    "理发",
    "家政",
    "生活服务",
    "本地服务",
]


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
        copy_style = resolve_copy_style(config, shop)
        topic = shop.get("topic") or f"{shop.get('industry', '本地服务')}服务介绍"
        offer = shop.get("main_offer") or "服务流程清楚，沟通透明"
        area = shop.get("city_area") or "附近"
        target = shop.get("target_customer") or "第一次了解服务的用户"
        cta = shop.get("cta") or "有需要可以提前咨询了解"
        industry = shop.get("industry", "本地服务")

        scene_count = _scene_count(payload)
        script_lines = _mock_script_lines(copy_style, area, topic, target, offer, cta, scene_count)

        scenes = []
        for idx, line in enumerate(script_lines):
            caption, voiceover = _mock_caption_voiceover(copy_style, line)
            scenes.append(
                {
                    "order": idx + 1,
                    "asset_type": ASSET_TYPES[idx % len(ASSET_TYPES)],
                    "caption": caption,
                    "voiceover": voiceover,
                    "effect": EFFECTS[idx % len(EFFECTS)],
                    "edited": False,
                }
            )

        return {
            "analysis": {
                "selling_points": [offer, "流程透明", "适合首次了解"],
                "pain_points": [f"{target}担心信息不清楚", "不知道到店前该问什么", "怕流程不透明"],
                "hook_angles": [topic, f"{industry}首次体验注意事项", "先了解流程再决定"],
                "recommended_structure": _mock_structure(copy_style),
                "reasoning": f"mock 模式按 {copy_style} 风格生成稳定合法结构，用于离线测试和无 API key 演示。",
            },
            "script": {
                "topic": topic,
                "cover_text": _mock_cover_text(copy_style, topic),
                "titles": _titles(shop, topic, copy_style),
                "post_copy": _mock_post_copy(copy_style, topic, offer, cta),
                "bgm_suggestion": _mock_bgm(copy_style),
            },
            "scenes": scenes,
        }


class ClaudeProvider(LLMProvider):
    def __init__(self, model: str | None = None, api_key: str | None = None, base_url: str | None = None):
        self.model = model or os.environ.get("CLAUDE_MODEL") or "claude-sonnet-4-6"
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
        # 中转站/代理需设 ANTHROPIC_BASE_URL（如 https://nexus.itssx.com/api/common）；为空回落官方端点。
        self.base_url = (base_url or os.environ.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com").rstrip("/")
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
            f"{self.base_url}/v1/messages",
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
            "copy_style": str(config.get("copy_style", "")),
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
    project_input = json.loads(prompt)
    copy_style = resolve_copy_style(project_input.get("config", {}), project_input.get("input", {}).get("shop", {}))
    style_rules = copy_style_prompt_rules(copy_style)
    retry_note = f"\nPrevious output validation error: {last_error}\n" if last_error else ""
    return f"""
You are a top-tier short-video copywriter for local Chinese small businesses (个体商户). You have written thousands of videos that actually went viral for restaurants, salons, repair shops, clinics, and stores.

THE REALITY OF YOUR INPUT:
A small shop owner usually gives you almost nothing — a few photos and one or two lines like "周年庆五折" or "新到一批活虾". They are NOT marketers. The compelling copy is YOUR job, not theirs. A flat restatement of their words is a failure. Your value is finding the angle, the hook, and the words that make a stranger stop scrolling.

Use the emit_video_content tool. Do not answer with free-form text.

Selected copy_style: {copy_style}

Creative rules for this style:
{style_rules}

HOW TO WRITE WELL (this is the core of your job):
- Creativity is in HOW you say it, NOT in inventing facts. Same offer "周年庆五折" can be boring or irresistible — your job is the irresistible version, built only on what is true.
- EACH SCENE MUST ADVANCE — no looping. The single most common failure is grabbing ONE angle (e.g. "省钱" or "我会提前告诉你情况") and then restating it 4 times in different words. That feels repetitive and hollow. Every scene must deliver a NEW idea, a NEW piece of information, or move the story one step forward. If scene 2 and scene 3 could swap their captions without anyone noticing, you have failed — rewrite.
- Give the video LAYERS. A good 4-5 scene structure covers genuinely different ground, e.g.: (1) hook that stops the scroll → (2) a concrete, specific point or little-known fact → (3) what you actually do / how it works → (4) a different angle or detail → (5) the call to action. Do not let one theme dominate every scene.
- Be concrete and specific over vague and emotional. One real detail (a specific dish, an actual step, a real number) beats three sentences of feeling. Avoid filling scenes with mood when you could deliver substance.
- SELL THE EXPERIENCE FIRST, THE DISCOUNT LAST. The hook and body must make people WANT the thing — the taste, the smell, the vibe, the feeling, the result. A price or discount is the final nudge, not the whole pitch. If a promotion is in the input, mention it ONCE or twice at most, near the end. Do NOT let money/price dominate every line.
- When the input is thin, do NOT invent prices, guarantees, awards, certifications, or testimonials. Instead, draw on common, believable scenarios and pain points TRUE for this kind of business, and frame the real offer through them.
- Find a fresh angle. Ask: what does the customer secretly want or worry about? what would make THEM the main character? Avoid the obvious "我们家东西好/便宜，快来买".
- Every line must earn its place. Delete anything generic. If a sentence could belong to any other shop, rewrite it.
- The caption (on-screen) is short and punchy; the voiceover (spoken) is fuller and conversational. They mean the same thing but are NOT identical text. Do not make them the same string.
- Build at least one memory point: a number, an image, a turn of phrase the viewer could repeat.

UNIVERSAL RULES:
- Write in Chinese unless the input clearly asks otherwise.
- This is a 15-45 second vertical short video, not a brochure or an article.
- Scene 1 carries the strongest hook. Never open with a shop introduction.
- Turn the offer into a benefit the viewer can feel. Ban empty words: 专业, 优质, 高端, 匠心, 尊享 — unless immediately backed by something concrete.
- End with one clear next action grounded in the cta.
- Each scene does one job: hook / pain / proof or process / benefit / action.

HARD STRUCTURAL RULES:
- Required top-level keys: analysis, script, scenes.
- Do not include start or duration; the program computes the timeline.
- scenes must be 3 to 5 items.
- Each scene requires order, asset_type, caption, voiceover, effect, edited. edited must be false.
- effect must be one of: {", ".join(EFFECTS)}.

COMPLIANCE:
- No medical treatment guarantees, cure rates, absolute claims (最/第一/唯一/根治), or patient testimonials.
- For medical/health/finance/legal/education, keep claims restrained and guide to formal consultation.
- Never invent certifications, prices, discounts, awards, case results, or reviews not present in the input.

EXAMPLE — the difference between bad and good (do not copy the industry):
- ✗ Flat: "我们是社区口腔，欢迎来洗牙。"
- ✓ Hook: "第一次洗牙最担心的，其实不是疼，是不知道会发生什么。"
- ✗ Empty caption: "服务专业，流程透明"
- ✓ Concrete caption: "先检查，再开口，告诉你牙龈到底什么情况"
- ✓ Voiceover (fuller than caption): "我们洗牙前会先看一眼你的牙龈状况，需不需要先处理、洗起来会是什么感觉，提前跟你说清楚，你心里有数再开始。"
{retry_note}
Input project JSON:
{prompt}
""".strip()


def copy_style_prompt_rules(copy_style: str) -> str:
    if copy_style == COPY_STYLE_TRUST:
        return """
- Style name: professional_trust (for medical/health/education/finance/legal, etc.).
- The hook still has to earn attention — but through INSIGHT, not hype. Open with a sharp, professional observation the customer hasn't considered, or name the exact worry they have but can't articulate. Example angle: "很多人第一次来都问错了问题" beats "我们很专业".
- Build trust by being on the customer's side: explain what they should check, what a proper process looks like, what to be wary of. Make them feel "这家是真的为我考虑".
- Tone: calm, credible, warm, like an experienced professional talking straight — NOT a stiff brochure, NOT cold.
- Hard limits: no cure rates, no result guarantees, no "最/第一/唯一", no fake testimonials. Restraint here is a feature, not a weakness.
- Still must be specific and vivid. "流程透明" is empty; "洗牙前先做检查，告诉你牙龈什么情况、要不要先处理" is concrete.
- CTA: gentle, low-pressure — invite to ask, consult, or come confirm in person.
""".strip()
    return """
- Style name: punchy_local (for 餐饮/零售/维修/美业/生活服务, etc.).
- The first 3 seconds are life or death. The opening line MUST stop the scroll. Use one of: a sharp pain point as a question, a surprising number, a contrast, a bit of suspense, or a "这说的就是我" moment. NEVER open with "欢迎光临" / "我们是XX店" / "今天给大家介绍" — that is instant death.
- Talk like a real person to a friend, not like an ad. Short punchy sentences, spoken rhythm, internet-native phrasing, a little attitude. Cut every word that sounds like marketing copy ("匠心" "品质之选" "尊享").
- Translate the offer into a vivid "什么好处归我" picture the viewer can feel — but lead with craving and experience (taste, smell, scene, emotion), not with the price tag. Make them hungry first.
- You may use playful exaggeration of TONE and energy, but NEVER fabricate facts: no invented prices, discounts, guarantees, awards, or claims not supported by the input.
- Build a memory point: one number, one image, or one line they'd repeat. Generic = forgettable.
- CTA: direct and specific — come try, save this, DM, navigate over, claim it (only if the offer is real and in the input). The discount, if any, belongs here as the final push — not sprinkled across every line.
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


def resolve_copy_style(config: dict, shop: dict | None = None) -> str:
    explicit = str(config.get("copy_style") or "").strip()
    if explicit in COPY_STYLE_OPTIONS:
        return explicit
    shop = shop or {}
    industry = str(config.get("industry") or shop.get("industry") or "")
    if any(keyword in industry for keyword in PROFESSIONAL_TRUST_INDUSTRY_KEYWORDS):
        return COPY_STYLE_TRUST
    if any(keyword in industry for keyword in PUNCHY_LOCAL_INDUSTRY_KEYWORDS):
        return COPY_STYLE_PUNCHY
    # 兜底：识别不出的 industry 默认走下沉口语强钩子（项目主赛道是本地生活服务）。
    return COPY_STYLE_PUNCHY


def _mock_script_lines(
    copy_style: str, area: str, topic: str, target: str, offer: str, cta: str, scene_count: int
) -> list[str]:
    if copy_style == COPY_STYLE_TRUST:
        lines = [
            f"第一次了解{topic}，建议先把流程和适合情况问清楚。",
            f"如果你是{target}，重点不是马上决定，而是确认检查、沟通和服务步骤。",
            f"这里会先说明：{offer}，让你知道每一步在做什么。",
            "有不确定的地方，建议当面咨询，按正规流程判断是否适合自己。",
            cta,
        ]
    else:
        lines = [
            f"{area}想做{topic}，别一上来就冲，先看这几个坑。",
            f"很多{target}最怕的不是花时间，是到店后才发现流程没问清。",
            f"这家的重点很直接：{offer}，先把你关心的点摊开说。",
            "环境、流程、怎么咨询，提前看明白，少走冤枉路。",
            cta,
        ]
    return lines[:scene_count]


def _mock_caption_voiceover(copy_style: str, line: str) -> tuple[str, str]:
    if copy_style == COPY_STYLE_TRUST:
        caption = line if len(line) <= 22 else line[:22] + "..."
        return caption, line
    caption = line.replace("，", "，\n", 1)
    if len(caption) > 24:
        caption = caption[:24] + "..."
    return caption, line


def _mock_structure(copy_style: str) -> str:
    if copy_style == COPY_STYLE_TRUST:
        return "信任建立-流程说明-具体卖点-风险克制-温和引导"
    return "强钩子-痛点直击-卖点具体化-少走弯路-明确行动"


def _mock_cover_text(copy_style: str, topic: str) -> str:
    if copy_style == COPY_STYLE_TRUST:
        return _cover_text(topic)
    text = f"{topic}先别急"
    return text if len(text) <= 14 else text[:14] + "..."


def _mock_post_copy(copy_style: str, topic: str, offer: str, cta: str) -> str:
    if copy_style == COPY_STYLE_TRUST:
        return f"{topic}前可以先了解流程、沟通方式和是否适合自己。重点是：{offer}。{cta}"
    return f"准备了解{topic}的，先把这几个点看完再决定。重点是：{offer}。想少走弯路，先问清楚。{cta}"


def _mock_bgm(copy_style: str) -> str:
    if copy_style == COPY_STYLE_TRUST:
        return "克制、干净、轻奢感的低速背景音乐"
    return "节奏轻快、干净、有本地生活感的背景音乐"


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


def _titles(shop: dict, topic: str, copy_style: str | None = None) -> list[str]:
    area = shop.get("city_area") or "附近"
    name = shop.get("shop_name") or "这家店"
    industry = shop.get("industry") or "本地服务"
    if copy_style == COPY_STYLE_TRUST:
        return [
            f"第一次了解{topic}，先确认这几点",
            f"来{name}前，可以先把流程问清楚",
            f"{topic}前，建议先了解是否适合自己",
            f"给第一次了解{industry}的人一点参考",
            f"{name}服务流程说明",
        ]
    return [
        f"{area}想做{topic}，先看这条",
        f"第一次来{name}，别漏问这几点",
        f"{topic}别急着决定，先避开这些坑",
        f"给第一次了解{industry}的人提个醒",
        f"{name}到底值不值得来，先看流程",
    ]
