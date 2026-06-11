import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import llm_generate
from llm_generate import (
    COPY_STYLE_PUNCHY,
    COPY_STYLE_TRUST,
    ClaudeProvider,
    LLMGenerationError,
    build_claude_instruction,
    build_project_input,
    generate_video_content,
    resolve_copy_style,
    validate_generation,
)


def sample_config():
    return {
        "shop_name": "星河口腔",
        "industry": "口腔门诊",
        "city_area": "本地社区",
        "topic": "第一次洗牙前要知道什么",
        "main_offer": "洗牙前会先做基础检查和流程沟通",
        "target_customer": "第一次准备洗牙、担心流程不清楚的用户",
        "tone": "专业、亲切、不夸张",
        "cta": "如有不适或疑问，建议到正规机构面诊咨询",
        "aspect_ratio": "9:16",
        "visual_style": "premium_luxe",
        "duration_seconds": 24,
        "platform": "generic",
        "compliance_mode": "medical",
    }


def sample_assets(count=3):
    return [
        {"asset_id": f"asset_{idx}", "file": f"input/images/demo_{idx}.png", "kind": "image", "duration": None, "tags": []}
        for idx in range(1, count + 1)
    ]


def test_mock_provider_required_fields():
    project_input = build_project_input(sample_config(), assets=sample_assets())
    generated = generate_video_content(project_input, provider_name="mock")
    assert not validate_generation(generated, project_input)
    assert generated["analysis"]["selling_points"]
    assert generated["script"]["titles"]
    assert generated["scenes"]


def test_mock_provider_timeline_is_contiguous():
    project_input = build_project_input(sample_config(), assets=sample_assets(5))
    generated = generate_video_content(project_input, provider_name="mock")
    scenes = generated["scenes"]
    cursor = 0
    for scene in scenes:
        assert scene["start"] == cursor
        assert scene["duration"] >= 3
        cursor += scene["duration"]
    assert cursor == project_input["config"]["duration_seconds"]


def test_mock_provider_duration_is_legal():
    config = sample_config()
    config["duration_seconds"] = 45
    project_input = build_project_input(config, assets=sample_assets(4))
    generated = generate_video_content(project_input, provider_name="mock")
    assert sum(scene["duration"] for scene in generated["scenes"]) == 45


def test_claude_provider_default_model():
    provider = ClaudeProvider(api_key="test-key")
    assert provider.model == "claude-sonnet-4-6"


def test_retryable_provider_error_retries(monkeypatch=None):
    class FlakyProvider(llm_generate.LLMProvider):
        def __init__(self):
            self.calls = 0

        def generate_json(self, prompt: str, last_error: str | None = None) -> dict:
            self.calls += 1
            if self.calls == 1:
                raise LLMGenerationError("temporary failure", retryable=True)
            return llm_generate.MockProvider().generate_json(prompt, last_error)

    provider = FlakyProvider()
    original_make_provider = llm_generate.make_provider
    llm_generate.make_provider = lambda provider_name: provider
    try:
        project_input = build_project_input(sample_config(), assets=sample_assets())
        generated = generate_video_content(project_input, provider_name="flaky")
    finally:
        llm_generate.make_provider = original_make_provider

    assert provider.calls == 2
    assert generated["scenes"]


def test_non_retryable_provider_error_does_not_retry(monkeypatch=None):
    class BrokenProvider(llm_generate.LLMProvider):
        def __init__(self):
            self.calls = 0

        def generate_json(self, prompt: str, last_error: str | None = None) -> dict:
            self.calls += 1
            raise LLMGenerationError("bad request", retryable=False)

    provider = BrokenProvider()
    original_make_provider = llm_generate.make_provider
    llm_generate.make_provider = lambda provider_name: provider
    try:
        project_input = build_project_input(sample_config(), assets=sample_assets())
        try:
            generate_video_content(project_input, provider_name="broken")
        except LLMGenerationError:
            pass
        else:
            raise AssertionError("Expected LLMGenerationError")
    finally:
        llm_generate.make_provider = original_make_provider

    assert provider.calls == 1


def test_copy_style_explicit_overrides_industry():
    assert resolve_copy_style({"copy_style": COPY_STYLE_PUNCHY, "industry": "口腔门诊"}) == COPY_STYLE_PUNCHY
    assert resolve_copy_style({"copy_style": COPY_STYLE_TRUST, "industry": "火锅餐饮"}) == COPY_STYLE_TRUST


def test_copy_style_auto_industry_rules_and_fallback():
    assert resolve_copy_style({}, {"industry": "口腔门诊"}) == COPY_STYLE_TRUST
    assert resolve_copy_style({}, {"industry": "少儿培训"}) == COPY_STYLE_TRUST
    assert resolve_copy_style({}, {"industry": "火锅餐饮"}) == COPY_STYLE_PUNCHY
    assert resolve_copy_style({}, {"industry": "未知行业"}) == COPY_STYLE_PUNCHY


def test_build_project_input_passes_copy_style():
    config = sample_config()
    config["copy_style"] = COPY_STYLE_PUNCHY
    project_input = build_project_input(config, assets=sample_assets())
    assert project_input["config"]["copy_style"] == COPY_STYLE_PUNCHY


def test_mock_provider_styles_are_distinct_and_valid():
    trust_config = sample_config()
    trust_config["copy_style"] = COPY_STYLE_TRUST
    punchy_config = sample_config()
    punchy_config["industry"] = "火锅餐饮"
    punchy_config["copy_style"] = COPY_STYLE_PUNCHY
    punchy_config["compliance_mode"] = ""

    trust_input = build_project_input(trust_config, assets=sample_assets())
    punchy_input = build_project_input(punchy_config, assets=sample_assets())
    trust_generated = generate_video_content(trust_input, provider_name="mock")
    punchy_generated = generate_video_content(punchy_input, provider_name="mock")

    assert not validate_generation(trust_generated, trust_input)
    assert not validate_generation(punchy_generated, punchy_input)
    assert "流程" in trust_generated["analysis"]["recommended_structure"]
    assert "强钩子" in punchy_generated["analysis"]["recommended_structure"]
    assert trust_generated["scenes"][0]["voiceover"] != punchy_generated["scenes"][0]["voiceover"]
    assert trust_generated["script"]["post_copy"] != punchy_generated["script"]["post_copy"]


def test_claude_instruction_injects_copy_style_rules():
    trust_input = build_project_input(sample_config(), assets=sample_assets())
    trust_instruction = build_claude_instruction(__import__("json").dumps(trust_input, ensure_ascii=False), None)
    assert "Selected copy_style: professional_trust" in trust_instruction
    assert "Restraint here is a feature" in trust_instruction
    assert "The compelling copy is YOUR job" in trust_instruction
    assert "Use the emit_video_content tool" in trust_instruction

    punchy_config = sample_config()
    punchy_config["industry"] = "餐饮小吃"
    punchy_config["copy_style"] = ""
    punchy_input = build_project_input(punchy_config, assets=sample_assets())
    punchy_instruction = build_claude_instruction(__import__("json").dumps(punchy_input, ensure_ascii=False), None)
    assert "Selected copy_style: punchy_local" in punchy_instruction
    assert "The first 3 seconds are life or death" in punchy_instruction
    assert "Creativity is in HOW you say it" in punchy_instruction


if __name__ == "__main__":
    test_mock_provider_required_fields()
    test_mock_provider_timeline_is_contiguous()
    test_mock_provider_duration_is_legal()
    test_claude_provider_default_model()
    test_retryable_provider_error_retries()
    test_non_retryable_provider_error_does_not_retry()
    test_copy_style_explicit_overrides_industry()
    test_copy_style_auto_industry_rules_and_fallback()
    test_build_project_input_passes_copy_style()
    test_mock_provider_styles_are_distinct_and_valid()
    test_claude_instruction_injects_copy_style_rules()
    print("llm_generate tests passed")
