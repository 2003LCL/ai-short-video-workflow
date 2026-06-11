import json
import os
import shutil
import tempfile
import threading
import time
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

import run_workflow
from render_mp4 import MP4RenderError, render_mp4
from tts_generate import TTSGenerationError, generate_voiceover_audio


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
PLAN_PATH = OUTPUT_DIR / "plan.json"
HOST = "127.0.0.1"
PORT = int(os.environ.get("AI_VIDEO_WEB_PORT", "5000"))

SCRIPT_TEXT_FIELDS = ("topic", "cover_text", "post_copy", "bgm_suggestion")
LEGACY_SCRIPT_FIELD_MAP = {
    "topic": "topic",
    "cover_text": "cover_text",
    "post_copy": "post_copy",
    "bgm_suggestion": "bgm_style",
}


app = Flask(__name__)
app.json.ensure_ascii = False


def load_project(path: Path = PLAN_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError("请先运行 run_workflow.py 生成 output/plan.json，再打开网页编辑器。")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"output/plan.json 不是合法 JSON：{exc}") from exc


def save_project(project: dict, path: Path = PLAN_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(project, ensure_ascii=False, indent=2)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as tmp:
        tmp.write(payload)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def get_legacy_plan(project: dict) -> dict:
    plan = project.get("plan")
    if not isinstance(plan, dict):
        raise ValueError("plan.json 缺少 legacy plan 字段，无法同步字幕和口播文本。")
    if not isinstance(plan.get("scenes"), list):
        raise ValueError("plan.json 的 plan.scenes 不是列表，无法保存分镜文案。")
    return plan


def extract_editable_project(project: dict) -> dict:
    script = project.get("script") or {}
    legacy_plan = project.get("plan") or {}
    scenes = project.get("scenes") or legacy_plan.get("scenes") or []
    shop = (project.get("input") or {}).get("shop") or {}
    return {
        "project_id": project.get("project_id", ""),
        "status": project.get("status", ""),
        "shop": {
            "shop_name": shop.get("shop_name") or legacy_plan.get("shop_name", ""),
            "industry": shop.get("industry") or legacy_plan.get("industry", ""),
            "topic": shop.get("topic", ""),
        },
        "script": {
            "topic": script.get("topic", legacy_plan.get("topic", "")),
            "cover_text": script.get("cover_text", legacy_plan.get("cover_text", "")),
            "titles": script.get("titles", legacy_plan.get("titles", [])),
            "post_copy": script.get("post_copy", legacy_plan.get("post_copy", "")),
            "bgm_suggestion": script.get("bgm_suggestion", legacy_plan.get("bgm_style", "")),
        },
        "scenes": [
            {
                "order": scene.get("order"),
                "start": scene.get("start"),
                "duration": scene.get("duration"),
                "asset_type": scene.get("asset_type", ""),
                "effect": scene.get("effect", ""),
                "caption": scene.get("caption", ""),
                "voiceover": scene.get("voiceover", ""),
                "edited": bool(scene.get("edited", False)),
            }
            for scene in scenes
        ],
        "notice": "文案保存后，字幕和口播文本会同步更新；已有配音、GIF 和 MP4 不会自动重生成。",
        "renders": project.get("renders", []),
        "audio": project.get("audio", {}),
    }


def require_text(value, field: str, errors: dict) -> str:
    if not isinstance(value, str):
        errors[field] = "请填写文字内容。"
        return ""
    text = value.strip()
    if not text:
        errors[field] = "这里不能为空。"
    return text


def validate_copy_payload(payload: dict, project: dict) -> tuple[dict | None, dict]:
    errors: dict[str, str] = {}
    if not isinstance(payload, dict):
        return None, {"body": "提交内容必须是 JSON 对象。"}

    script_payload = payload.get("script")
    scene_payloads = payload.get("scenes")
    if not isinstance(script_payload, dict):
        errors["script"] = "缺少整体文案。"
        script_payload = {}
    if not isinstance(scene_payloads, list):
        errors["scenes"] = "缺少分镜列表。"
        scene_payloads = []

    script = {
        "topic": require_text(script_payload.get("topic"), "script.topic", errors),
        "cover_text": require_text(script_payload.get("cover_text"), "script.cover_text", errors),
        "post_copy": require_text(script_payload.get("post_copy"), "script.post_copy", errors),
        "bgm_suggestion": require_text(script_payload.get("bgm_suggestion"), "script.bgm_suggestion", errors),
    }

    titles_raw = script_payload.get("titles")
    if not isinstance(titles_raw, list):
        errors["script.titles"] = "标题备选必须是列表。"
        titles: list[str] = []
    else:
        titles = []
        for idx, title in enumerate(titles_raw, start=1):
            clean = require_text(title, f"script.titles[{idx}]", errors)
            if clean:
                titles.append(clean)
        if not titles:
            errors["script.titles"] = "至少保留一个标题。"
    script["titles"] = titles

    existing_orders = {scene.get("order") for scene in (project.get("scenes") or [])}
    scenes = []
    seen_orders = set()
    for idx, scene_payload in enumerate(scene_payloads, start=1):
        if not isinstance(scene_payload, dict):
            errors[f"scenes[{idx}]"] = "每个分镜都必须是对象。"
            continue
        order = scene_payload.get("order")
        if not isinstance(order, int):
            errors[f"scenes[{idx}].order"] = "分镜序号缺失。"
            continue
        if order not in existing_orders:
            errors[f"scenes[{idx}].order"] = f"找不到第 {order} 个分镜。"
        if order in seen_orders:
            errors[f"scenes[{idx}].order"] = f"第 {order} 个分镜重复提交。"
        seen_orders.add(order)
        scenes.append(
            {
                "order": order,
                "caption": require_text(scene_payload.get("caption"), f"scenes[{idx}].caption", errors),
                "voiceover": require_text(scene_payload.get("voiceover"), f"scenes[{idx}].voiceover", errors),
            }
        )

    if errors:
        return None, errors
    return {"script": script, "scenes": scenes}, {}


def update_script(project: dict, script_payload: dict) -> None:
    project_script = project.setdefault("script", {})
    legacy_plan = get_legacy_plan(project)
    for key in SCRIPT_TEXT_FIELDS:
        project_script[key] = script_payload[key]
        legacy_key = LEGACY_SCRIPT_FIELD_MAP[key]
        legacy_plan[legacy_key] = script_payload[key]
    project_script["titles"] = list(script_payload["titles"])
    legacy_plan["titles"] = list(script_payload["titles"])


def update_scene_copy(project: dict, scene_payloads: list[dict]) -> None:
    top_scenes = project.get("scenes")
    if not isinstance(top_scenes, list):
        raise ValueError("plan.json 的顶层 scenes 不是列表，无法保存分镜文案。")
    legacy_scenes = get_legacy_plan(project)["scenes"]
    top_by_order = {scene.get("order"): scene for scene in top_scenes}
    legacy_by_order = {scene.get("order"): scene for scene in legacy_scenes}

    for scene_payload in scene_payloads:
        order = scene_payload["order"]
        changed = False
        for scenes_by_order in (top_by_order, legacy_by_order):
            scene = scenes_by_order.get(order)
            if scene is None:
                continue
            if scene.get("caption") != scene_payload["caption"]:
                scene["caption"] = scene_payload["caption"]
                changed = True
            if scene.get("voiceover") != scene_payload["voiceover"]:
                scene["voiceover"] = scene_payload["voiceover"]
                changed = True
        if changed:
            if order in top_by_order:
                top_by_order[order]["edited"] = True
            if order in legacy_by_order:
                legacy_by_order[order]["edited"] = True


def sync_text_outputs(project: dict, output_dir: Path = OUTPUT_DIR) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    legacy_plan = get_legacy_plan(project)
    compliance = project.get("compliance") or {"pass": True, "risk_level": "low", "issues": [], "note": ""}
    original_output_dir = run_workflow.OUTPUT_DIR
    try:
        run_workflow.OUTPUT_DIR = output_dir
        run_workflow.write_srt(legacy_plan)
        run_workflow.write_voiceover_files(legacy_plan)
        run_workflow.write_markdown(legacy_plan, compliance)
    finally:
        run_workflow.OUTPUT_DIR = original_output_dir


def build_output_assets(output_dir: Path = OUTPUT_DIR) -> list[dict]:
    asset_dir = output_dir / "assets"
    if not asset_dir.exists():
        return []
    image_exts = getattr(run_workflow, "IMAGE_EXTS", {".jpg", ".jpeg", ".png", ".webp", ".bmp"})
    return [
        {"source": path.name, "file": path.name}
        for path in sorted(asset_dir.iterdir())
        if path.is_file() and path.suffix.lower() in image_exts
    ]


def mirror_voiceover_audio(project: dict) -> None:
    top_scenes = project.get("scenes")
    legacy_scenes = get_legacy_plan(project)["scenes"]
    if not isinstance(top_scenes, list):
        raise ValueError("plan.json 的顶层 scenes 不是列表，无法同步配音信息。")
    top_by_order = {scene.get("order"): scene for scene in top_scenes}
    for legacy_scene in legacy_scenes:
        order = legacy_scene.get("order")
        top_scene = top_by_order.get(order)
        if top_scene is None:
            continue
        audio = legacy_scene.get("voiceover_audio")
        if audio:
            top_scene["voiceover_audio"] = dict(audio)
        else:
            top_scene.pop("voiceover_audio", None)


def clear_edited_flags(project: dict, orders: set[int]) -> None:
    top_scenes = project.get("scenes") or []
    legacy_scenes = get_legacy_plan(project)["scenes"]
    for scenes in (top_scenes, legacy_scenes):
        for scene in scenes:
            if scene.get("order") in orders:
                scene["edited"] = False


def upsert_render_entry(renders: list[dict], entry: dict) -> list[dict]:
    kept = [item for item in renders if item.get("kind") != entry.get("kind")]
    kept.append(entry)
    return kept


def backup_audio_files(scenes: list[dict], orders: set[int], output_dir: Path) -> tuple[Path, list[dict]]:
    backup_dir = Path(tempfile.mkdtemp(prefix="voiceover_audio_backup_", dir=output_dir))
    records = []
    for idx, scene in enumerate(scenes, start=1):
        order = scene.get("order", idx)
        if order not in orders:
            continue
        audio = scene.get("voiceover_audio") or {}
        rel_file = str(audio.get("file") or f"voiceover_audio/scene_{int(order):02d}.mp3")
        current_path = output_dir / rel_file
        backup_path = backup_dir / rel_file.replace("/", "_").replace("\\", "_")
        record = {"path": current_path, "backup": backup_path, "existed": current_path.exists()}
        if current_path.exists():
            shutil.copy2(current_path, backup_path)
        records.append(record)
    return backup_dir, records


def restore_audio_files(backup_dir: Path, records: list[dict]) -> None:
    for record in records:
        current_path = record["path"]
        backup_path = record["backup"]
        if record["existed"]:
            current_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_path, current_path)
        elif current_path.exists():
            current_path.unlink()
    shutil.rmtree(backup_dir, ignore_errors=True)


def cleanup_audio_backup(backup_dir: Path) -> None:
    shutil.rmtree(backup_dir, ignore_errors=True)


def backup_file(path: Path) -> tuple[Path, bool]:
    backup_path = Path(tempfile.mktemp(prefix=f"{path.name}.backup.", dir=path.parent))
    if path.exists():
        shutil.copy2(path, backup_path)
        return backup_path, True
    return backup_path, False


def restore_file(path: Path, backup_path: Path, existed: bool) -> None:
    if existed:
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_path, path)
    elif path.exists():
        path.unlink()
    if backup_path.exists():
        backup_path.unlink()


def rerender_project(
    project: dict,
    output_dir: Path = OUTPUT_DIR,
    tts_provider_name: str = "edge",
    tts_provider=None,
    mp4_renderer=render_mp4,
    frame_renderer=run_workflow.render_scene_frames,
) -> tuple[dict, dict]:
    started = time.perf_counter()
    legacy_plan = get_legacy_plan(project)
    edited_orders = {
        int(scene.get("order"))
        for scene in (project.get("scenes") or [])
        if scene.get("edited") is True and isinstance(scene.get("order"), int)
    }
    tts_provider_name = str((project.get("config") or {}).get("tts_provider") or tts_provider_name)
    audio_backup_dir, audio_backup_records = backup_audio_files(legacy_plan["scenes"], edited_orders, output_dir)
    video_path = output_dir / "video.mp4"
    video_backup_path, video_existed = backup_file(video_path)
    success = False
    try:
        audio = generate_voiceover_audio(
            legacy_plan["scenes"],
            project.get("config") or {},
            output_dir,
            provider_name=tts_provider_name,
            provider=tts_provider,
            only_orders=edited_orders,
        )
        if audio.get("warnings"):
            raise TTSGenerationError("; ".join(str(item) for item in audio["warnings"]))
        mirror_voiceover_audio(project)
        assets = build_output_assets(output_dir)
        original_assets_dir = run_workflow.ASSETS_DIR
        run_workflow.ASSETS_DIR = output_dir / "assets"
        try:
            mp4_entry = mp4_renderer(legacy_plan, assets, output_dir, frame_renderer)
        finally:
            run_workflow.ASSETS_DIR = original_assets_dir

        sync_text_outputs(project, output_dir)
        clear_edited_flags(project, edited_orders)
        project["audio"] = audio
        project["renders"] = upsert_render_entry(project.get("renders") or [], mp4_entry)
        project["status"] = "rerendered"
        success = True
        return project, {
            "edited_orders": sorted(edited_orders),
            "mp4": mp4_entry,
            "audio": audio,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
    except TTSGenerationError as exc:
        raise RuntimeError(f"增量配音失败，旧音频和旧视频未被破坏：{exc}") from exc
    except MP4RenderError as exc:
        raise RuntimeError(f"视频重新生成失败，旧视频未被破坏：{exc}") from exc
    finally:
        if success:
            cleanup_audio_backup(audio_backup_dir)
            if video_backup_path.exists():
                video_backup_path.unlink()
        else:
            restore_audio_files(audio_backup_dir, audio_backup_records)
            restore_file(video_path, video_backup_path, video_existed)



def apply_copy_update(project: dict, payload: dict) -> tuple[dict | None, dict]:
    validated, errors = validate_copy_payload(payload, project)
    if errors:
        return None, errors
    assert validated is not None
    update_script(project, validated["script"])
    update_scene_copy(project, validated["scenes"])
    return project, {}


def api_error(message: str, status: int = 400, errors: dict | None = None):
    body = {"ok": False, "error": message}
    if errors:
        body["errors"] = errors
    return jsonify(body), status


def should_auto_open_browser() -> bool:
    return os.environ.get("AI_VIDEO_NO_BROWSER", "").strip() != "1"


def open_browser_later(url: str, delay_seconds: float = 1.0) -> None:
    if not should_auto_open_browser():
        return
    timer = threading.Timer(delay_seconds, lambda: webbrowser.open(url))
    timer.daemon = True
    timer.start()


@app.get("/")
def index():
    return render_template_string(INDEX_HTML)


@app.get("/api/project")
def api_get_project():
    try:
        project = load_project(PLAN_PATH)
    except FileNotFoundError as exc:
        return api_error(str(exc), 404)
    except ValueError as exc:
        return api_error(str(exc), 500)
    return jsonify({"ok": True, "project": extract_editable_project(project)})


@app.post("/api/project/copy")
def api_save_copy():
    try:
        project = load_project(PLAN_PATH)
    except FileNotFoundError as exc:
        return api_error(str(exc), 404)
    except ValueError as exc:
        return api_error(str(exc), 500)

    updated, errors = apply_copy_update(project, request.get_json(silent=True) or {})
    if errors:
        return api_error("有些文案还不能保存，请检查标红字段。", 400, errors)

    assert updated is not None
    try:
        save_project(updated, PLAN_PATH)
        sync_text_outputs(updated, OUTPUT_DIR)
    except ValueError as exc:
        return api_error(str(exc), 500)

    return jsonify(
        {
            "ok": True,
            "project": extract_editable_project(updated),
            "message": "文案已保存。字幕和口播文本已同步；配音和视频需要重新生成才会更新。",
        }
    )


@app.post("/api/project/rerender")
def api_rerender_project():
    try:
        project = load_project(PLAN_PATH)
    except FileNotFoundError as exc:
        return api_error(str(exc), 404)
    except ValueError as exc:
        return api_error(str(exc), 500)

    try:
        updated, result = rerender_project(project, OUTPUT_DIR)
        save_project(updated, PLAN_PATH)
    except Exception as exc:
        return api_error(f"{exc}。旧视频未被破坏，可以修改后再试。", 500)

    return jsonify(
        {
            "ok": True,
            "project": extract_editable_project(updated),
            "rerender": result,
            "message": "视频已重新生成，改过的段落已经重新配音，MP4 已更新。",
        }
    )


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>视频文案审改</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #17202a;
      --muted: #64748b;
      --line: #d9e1ea;
      --soft: #f5f7fa;
      --panel: #ffffff;
      --accent: #0f766e;
      --accent-2: #b88a2c;
      --danger: #b91c1c;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: #eef2f6;
      color: var(--ink);
      font-family: "Microsoft YaHei", "PingFang SC", Arial, sans-serif;
    }
    header {
      padding: 22px 28px;
      background: #111827;
      color: #fff;
      border-bottom: 4px solid var(--accent-2);
    }
    h1 {
      margin: 0 0 6px;
      font-size: 24px;
      line-height: 1.2;
      letter-spacing: 0;
    }
    .meta {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 18px;
      color: #d6dee8;
      font-size: 14px;
    }
    main {
      width: min(1180px, calc(100vw - 32px));
      margin: 24px auto 42px;
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 18px;
    }
    section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      box-shadow: 0 10px 28px rgba(15, 23, 42, .06);
    }
    h2 {
      margin: 0 0 14px;
      font-size: 18px;
      letter-spacing: 0;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }
    label {
      display: block;
      color: #334155;
      font-weight: 700;
      font-size: 14px;
      margin-bottom: 6px;
    }
    input, textarea {
      width: 100%;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      padding: 10px 11px;
      color: var(--ink);
      background: #fff;
      font: inherit;
      line-height: 1.45;
    }
    textarea { min-height: 96px; resize: vertical; }
    input:focus, textarea:focus {
      outline: 2px solid rgba(15, 118, 110, .18);
      border-color: var(--accent);
    }
    .full { grid-column: 1 / -1; }
    .scene {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: #fbfcfe;
      margin-bottom: 12px;
    }
    .scene-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
      color: var(--muted);
      font-size: 13px;
    }
    .readonly {
      color: #475569;
      background: #edf2f7;
      border: 1px solid #d7dee8;
      border-radius: 999px;
      padding: 4px 9px;
      white-space: nowrap;
    }
    .actions {
      position: sticky;
      bottom: 0;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      padding: 14px 18px;
      background: rgba(255,255,255,.94);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 -8px 24px rgba(15, 23, 42, .08);
    }
    button {
      border: 0;
      border-radius: 6px;
      padding: 10px 18px;
      background: var(--accent);
      color: #fff;
      font-weight: 800;
      cursor: pointer;
    }
    button:disabled { opacity: .6; cursor: wait; }
    .button-row { display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
    .secondary { background: #334155; }
    .notice { color: var(--muted); font-size: 14px; }
    .status { font-weight: 700; }
    .error { color: var(--danger); }
    .ok { color: var(--accent); }
    @media (max-width: 760px) {
      header { padding: 18px; }
      main { width: min(100vw - 20px, 720px); margin-top: 14px; }
      .grid { grid-template-columns: 1fr; }
      .actions { align-items: stretch; flex-direction: column; }
      .button-row { flex-direction: column; }
      button { width: 100%; }
    }
  </style>
</head>
<body>
  <header>
    <h1 id="pageTitle">视频文案审改</h1>
    <div class="meta">
      <span id="shopName">读取中</span>
      <span id="industry"></span>
      <span id="projectId"></span>
    </div>
  </header>
  <main>
    <section>
      <h2>整体文案</h2>
      <div class="grid">
        <div>
          <label for="topic">视频主题</label>
          <input id="topic" autocomplete="off">
        </div>
        <div>
          <label for="coverText">封面主文案</label>
          <input id="coverText" autocomplete="off">
        </div>
        <div class="full">
          <label for="titles">标题备选（一行一个）</label>
          <textarea id="titles"></textarea>
        </div>
        <div class="full">
          <label for="postCopy">发布文案</label>
          <textarea id="postCopy"></textarea>
        </div>
        <div class="full">
          <label for="bgmSuggestion">BGM 建议</label>
          <input id="bgmSuggestion" autocomplete="off">
        </div>
      </div>
    </section>
    <section>
      <h2>分镜文案</h2>
      <div id="scenes"></div>
    </section>
    <div class="actions">
      <div>
        <div class="notice">保存会同步字幕和口播文本；已有配音、GIF、MP4 需要重新生成才会更新。</div>
        <div id="status" class="status"></div>
      </div>
      <div class="button-row">
        <button id="rerenderBtn" class="secondary" type="button">重新生成视频</button>
        <button id="saveBtn" type="button">保存文案</button>
      </div>
    </div>
  </main>
  <script>
    const els = {
      pageTitle: document.getElementById('pageTitle'),
      shopName: document.getElementById('shopName'),
      industry: document.getElementById('industry'),
      projectId: document.getElementById('projectId'),
      topic: document.getElementById('topic'),
      coverText: document.getElementById('coverText'),
      titles: document.getElementById('titles'),
      postCopy: document.getElementById('postCopy'),
      bgmSuggestion: document.getElementById('bgmSuggestion'),
      scenes: document.getElementById('scenes'),
      status: document.getElementById('status'),
      saveBtn: document.getElementById('saveBtn'),
      rerenderBtn: document.getElementById('rerenderBtn'),
    };
    let currentProject = null;

    function setStatus(text, kind) {
      els.status.textContent = text || '';
      els.status.className = 'status ' + (kind || '');
    }

    function renderProject(project) {
      currentProject = project;
      const shop = project.shop || {};
      const script = project.script || {};
      els.pageTitle.textContent = (shop.shop_name || '本地项目') + ' 文案审改';
      els.shopName.textContent = shop.shop_name || '未填写店名';
      els.industry.textContent = shop.industry || '';
      els.projectId.textContent = project.project_id || '';
      els.topic.value = script.topic || '';
      els.coverText.value = script.cover_text || '';
      els.titles.value = (script.titles || []).join('\n');
      els.postCopy.value = script.post_copy || '';
      els.bgmSuggestion.value = script.bgm_suggestion || '';
      els.scenes.innerHTML = '';
      (project.scenes || []).forEach((scene) => {
        const item = document.createElement('div');
        item.className = 'scene';
        item.dataset.order = scene.order;
        item.innerHTML = `
          <div class="scene-head">
            <strong>第 ${scene.order} 镜</strong>
            <span>
              <span class="readonly">${scene.start ?? 0}-${(scene.start ?? 0) + (scene.duration ?? 0)} 秒</span>
              <span class="readonly">${scene.asset_type || '素材'}</span>
              <span class="readonly">${scene.effect || '默认运镜'}</span>
            </span>
          </div>
          <div class="grid">
            <div>
              <label>这句话的字幕</label>
              <textarea class="caption"></textarea>
            </div>
            <div>
              <label>这句话的口播</label>
              <textarea class="voiceover"></textarea>
            </div>
          </div>`;
        item.querySelector('.caption').value = scene.caption || '';
        item.querySelector('.voiceover').value = scene.voiceover || '';
        els.scenes.appendChild(item);
      });
    }

    async function loadProject() {
      setStatus('正在读取项目...', '');
      const res = await fetch('/api/project');
      const data = await res.json();
      if (!res.ok || !data.ok) {
        setStatus(data.error || '项目读取失败', 'error');
        return;
      }
      renderProject(data.project);
      setStatus('项目已读取', 'ok');
    }

    function collectPayload() {
      return {
        script: {
          topic: els.topic.value,
          cover_text: els.coverText.value,
          titles: els.titles.value.split('\n').map((line) => line.trim()).filter(Boolean),
          post_copy: els.postCopy.value,
          bgm_suggestion: els.bgmSuggestion.value,
        },
        scenes: Array.from(els.scenes.querySelectorAll('.scene')).map((item) => ({
          order: Number(item.dataset.order),
          caption: item.querySelector('.caption').value,
          voiceover: item.querySelector('.voiceover').value,
        })),
      };
    }

    async function saveProject() {
      els.saveBtn.disabled = true;
      els.rerenderBtn.disabled = true;
      setStatus('正在保存...', '');
      try {
        const res = await fetch('/api/project/copy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(collectPayload()),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          const detail = data.errors ? Object.values(data.errors)[0] : '';
          setStatus((data.error || '保存失败') + (detail ? ' ' + detail : ''), 'error');
          return;
        }
        renderProject(data.project);
        setStatus(data.message || '文案已保存', 'ok');
      } finally {
        els.saveBtn.disabled = false;
        els.rerenderBtn.disabled = false;
      }
    }

    async function rerenderProject() {
      els.saveBtn.disabled = true;
      els.rerenderBtn.disabled = true;
      setStatus('正在重新生成视频，可能需要一两分钟...', '');
      try {
        const res = await fetch('/api/project/rerender', { method: 'POST' });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          setStatus(data.error || '重新生成失败，旧视频未被破坏。', 'error');
          return;
        }
        renderProject(data.project);
        const mp4 = data.rerender && data.rerender.mp4 ? data.rerender.mp4.file : 'video.mp4';
        setStatus((data.message || '视频已更新') + ' 输出文件：output/' + mp4, 'ok');
      } finally {
        els.saveBtn.disabled = false;
        els.rerenderBtn.disabled = false;
      }
    }

    els.saveBtn.addEventListener('click', saveProject);
    els.rerenderBtn.addEventListener('click', rerenderProject);
    loadProject();
  </script>
</body>
</html>"""


def main() -> None:
    url = f"http://{HOST}:{PORT}"
    print(f"Web editor: {url}")
    if should_auto_open_browser():
        print("Opening browser automatically...")
    else:
        print("Browser auto-open disabled by AI_VIDEO_NO_BROWSER=1.")
    open_browser_later(url)
    app.run(host=HOST, port=PORT, debug=False)


if __name__ == "__main__":
    main()
