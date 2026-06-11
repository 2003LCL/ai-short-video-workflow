import copy
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import web_app


def sample_project() -> dict:
    top_scenes = [
        {
            "order": 1,
            "start": 0,
            "duration": 8,
            "asset_type": "门店环境",
            "caption": "原字幕一",
            "voiceover": "原口播一",
            "effect": "slow_zoom_in",
            "edited": False,
            "voiceover_audio": {
                "file": "voiceover_audio/scene_01.mp3",
                "audio_duration": 4.2,
                "provider": "edge",
                "voice": "zh-CN-XiaoxiaoNeural",
            },
        },
        {
            "order": 2,
            "start": 8,
            "duration": 7,
            "asset_type": "服务细节",
            "caption": "原字幕二",
            "voiceover": "原口播二",
            "effect": "pan_up",
            "edited": False,
            "voiceover_audio": {
                "file": "voiceover_audio/scene_02.mp3",
                "audio_duration": 5.1,
                "provider": "edge",
                "voice": "zh-CN-XiaoxiaoNeural",
            },
        },
    ]
    legacy_scenes = copy.deepcopy(top_scenes)
    return {
        "schema_version": "1.0",
        "project_id": "test-project",
        "status": "generated",
        "input": {
            "shop": {
                "shop_name": "星河口腔",
                "industry": "口腔门诊",
                "topic": "洗牙前要知道什么",
            }
        },
        "config": {"aspect_ratio": "9:16", "visual_style": "premium_luxe", "duration_seconds": 24},
        "analysis": {"selling_points": ["流程清楚"], "pain_points": ["怕疼"], "hook_angles": ["先解释流程"]},
        "script": {
            "topic": "原主题",
            "cover_text": "原封面",
            "titles": ["原标题一", "原标题二"],
            "post_copy": "原发布文案",
            "bgm_suggestion": "原 BGM",
        },
        "scenes": top_scenes,
        "audio": {"provider": "edge", "voice": "zh-CN-XiaoxiaoNeural", "segments": 2},
        "renders": [{"platform": "generic", "aspect_ratio": "9:16", "kind": "mp4", "file": "video.mp4"}],
        "compliance": {"pass": True, "risk_level": "low", "issues": [], "note": "ok"},
        "plan": {
            "shop_name": "星河口腔",
            "industry": "口腔门诊",
            "topic": "原主题",
            "platform": "generic",
            "aspect_ratio": "9:16",
            "visual_style": "premium_luxe",
            "duration_seconds": 15,
            "cover_text": "原封面",
            "titles": ["原标题一", "原标题二"],
            "post_copy": "原发布文案",
            "scenes": legacy_scenes,
            "subtitle_style": "premium_readable",
            "bgm_style": "原 BGM",
        },
    }


def configure_temp_project(base: Path, project: dict | None = None) -> Path:
    web_app.OUTPUT_DIR = base
    web_app.PLAN_PATH = base / "plan.json"
    if project is not None:
        base.mkdir(parents=True, exist_ok=True)
        web_app.PLAN_PATH.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    return web_app.PLAN_PATH


def client_for(base: Path, project: dict | None = None):
    configure_temp_project(base, project)
    web_app.app.config.update(TESTING=True)
    return web_app.app.test_client()


def read_project(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def valid_payload() -> dict:
    return {
        "script": {
            "topic": "新主题",
            "cover_text": "新封面",
            "titles": ["新标题一", "新标题二"],
            "post_copy": "新发布文案",
            "bgm_suggestion": "新 BGM",
        },
        "scenes": [
            {
                "order": 1,
                "caption": "新字幕一",
                "voiceover": "新口播一",
                "start": 999,
                "duration": 999,
            },
            {"order": 2, "caption": "原字幕二", "voiceover": "原口播二"},
        ],
    }


def test_get_project_returns_editable_copy():
    with tempfile.TemporaryDirectory() as tmp:
        client = client_for(Path(tmp), sample_project())
        response = client.get("/api/project")
        data = response.get_json()

        assert response.status_code == 200
        assert data["ok"] is True
        assert data["project"]["shop"]["shop_name"] == "星河口腔"
        assert data["project"]["script"]["cover_text"] == "原封面"
        assert data["project"]["scenes"][0]["caption"] == "原字幕一"


def test_get_project_missing_plan_has_clear_error():
    with tempfile.TemporaryDirectory() as tmp:
        client = client_for(Path(tmp))
        response = client.get("/api/project")
        data = response.get_json()

        assert response.status_code == 404
        assert data["ok"] is False
        assert "run_workflow.py" in data["error"]


def test_post_copy_updates_only_copy_fields_and_both_scene_mirrors():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        project = sample_project()
        preserved = {key: copy.deepcopy(project[key]) for key in ["analysis", "audio", "renders", "compliance"]}
        plan_path = configure_temp_project(base, project)
        client = web_app.app.test_client()

        response = client.post("/api/project/copy", json=valid_payload())
        data = response.get_json()
        saved = read_project(plan_path)

        assert response.status_code == 200
        assert data["ok"] is True
        assert saved["script"]["topic"] == "新主题"
        assert saved["script"]["bgm_suggestion"] == "新 BGM"
        assert saved["plan"]["topic"] == "新主题"
        assert saved["plan"]["bgm_style"] == "新 BGM"
        assert saved["scenes"][0]["caption"] == "新字幕一"
        assert saved["plan"]["scenes"][0]["caption"] == "新字幕一"
        assert saved["scenes"][0]["voiceover"] == "新口播一"
        assert saved["plan"]["scenes"][0]["voiceover"] == "新口播一"
        assert saved["scenes"][0]["edited"] is True
        assert saved["plan"]["scenes"][0]["edited"] is True
        assert saved["scenes"][1]["edited"] is False
        assert saved["plan"]["scenes"][1]["edited"] is False
        assert saved["scenes"][0]["start"] == 0
        assert saved["scenes"][0]["duration"] == 8
        assert saved["plan"]["scenes"][0]["start"] == 0
        assert saved["plan"]["scenes"][0]["duration"] == 8
        for key, value in preserved.items():
            assert saved[key] == value


def test_post_copy_syncs_text_sidecar_outputs():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        client = client_for(base, sample_project())

        response = client.post("/api/project/copy", json=valid_payload())

        assert response.status_code == 200
        assert "新字幕一" in (base / "captions.srt").read_text(encoding="utf-8")
        assert "新口播一" in (base / "voiceover.txt").read_text(encoding="utf-8")
        assert (base / "voiceover_segments" / "scene_01.txt").read_text(encoding="utf-8") == "新口播一"
        assert "新发布文案" in (base / "video_plan.md").read_text(encoding="utf-8")


def test_post_copy_rejects_empty_copy_fields():
    with tempfile.TemporaryDirectory() as tmp:
        client = client_for(Path(tmp), sample_project())
        payload = valid_payload()
        payload["script"]["titles"] = []
        payload["scenes"][0]["caption"] = " "

        response = client.post("/api/project/copy", json=payload)
        data = response.get_json()

        assert response.status_code == 400
        assert data["ok"] is False
        assert "script.titles" in data["errors"]
        assert "scenes[1].caption" in data["errors"]


def test_post_copy_ignores_timeline_mutation_attempts():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        plan_path = configure_temp_project(base, sample_project())
        client = web_app.app.test_client()
        payload = valid_payload()
        payload["scenes"][0]["start"] = 1234
        payload["scenes"][0]["duration"] = 5678

        response = client.post("/api/project/copy", json=payload)
        saved = read_project(plan_path)

        assert response.status_code == 200
        assert saved["scenes"][0]["start"] == 0
        assert saved["scenes"][0]["duration"] == 8
        assert saved["plan"]["scenes"][0]["start"] == 0
        assert saved["plan"]["scenes"][0]["duration"] == 8


def test_browser_auto_open_env_switch():
    original = os.environ.get("AI_VIDEO_NO_BROWSER")
    try:
        os.environ["AI_VIDEO_NO_BROWSER"] = "1"
        assert web_app.should_auto_open_browser() is False
        os.environ.pop("AI_VIDEO_NO_BROWSER", None)
        assert web_app.should_auto_open_browser() is True
    finally:
        if original is None:
            os.environ.pop("AI_VIDEO_NO_BROWSER", None)
        else:
            os.environ["AI_VIDEO_NO_BROWSER"] = original


if __name__ == "__main__":
    test_get_project_returns_editable_copy()
    test_get_project_missing_plan_has_clear_error()
    test_post_copy_updates_only_copy_fields_and_both_scene_mirrors()
    test_post_copy_syncs_text_sidecar_outputs()
    test_post_copy_rejects_empty_copy_fields()
    test_post_copy_ignores_timeline_mutation_attempts()
    test_browser_auto_open_env_switch()
    print("web_app tests passed")
