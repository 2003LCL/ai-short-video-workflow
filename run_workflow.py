import argparse
import html
import json
import math
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from llm_generate import LLMGenerationError, build_project_input, generate_video_content, legacy_plan_from_generation
from render_mp4 import MP4RenderError, make_render_entry, render_mp4
from tts_generate import TTSGenerationError, generate_voiceover_audio


ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / "input"
IMAGE_DIR = INPUT_DIR / "images"
OUTPUT_DIR = ROOT / "output"
ASSETS_DIR = OUTPUT_DIR / "assets"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

MEDICAL_RISK_TERMS = [
    "根治",
    "包好",
    "治愈",
    "无效退款",
    "最先进",
    "最权威",
    "唯一",
    "立竿见影",
    "成功率",
    "治愈率",
    "保证",
    "绝不复发",
]

ASPECT_RATIOS = {
    "9:16": (360, 640),
    "16:9": (640, 360),
    "1:1": (480, 480),
}

VISUAL_STYLES = {
    "premium_luxe": {
        "accent": "#d7bd7a",
        "shadow": "rgba(7,8,10,.78)",
        "overlay": "rgba(18,19,22,.50)",
        "text": "#fbfaf7",
    },
    "clean_clinic": {
        "accent": "#f8d66d",
        "shadow": "rgba(8,13,20,.88)",
        "overlay": "rgba(7,12,20,.64)",
        "text": "#ffffff",
    },
    "warm_local": {
        "accent": "#f59e0b",
        "shadow": "rgba(28,18,10,.86)",
        "overlay": "rgba(33,22,12,.58)",
        "text": "#fff7ed",
    },
    "bold_product": {
        "accent": "#38bdf8",
        "shadow": "rgba(8,13,20,.90)",
        "overlay": "rgba(3,7,18,.62)",
        "text": "#f8fafc",
    },
}


def load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    try:
        config = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    validate_config(config)
    return config


def validate_config(config: dict) -> None:
    required = ["shop_name", "industry", "topic", "main_offer"]
    missing = [key for key in required if not str(config.get(key, "")).strip()]
    if missing:
        raise ValueError(f"Missing required config field(s): {', '.join(missing)}")
    duration = int(config.get("duration_seconds", 24))
    if duration < 15 or duration > 45:
        raise ValueError("duration_seconds should be between 15 and 45 for this POC.")
    aspect_ratio = str(config.get("aspect_ratio", "9:16"))
    if aspect_ratio not in ASPECT_RATIOS:
        raise ValueError(f"aspect_ratio should be one of: {', '.join(ASPECT_RATIOS)}")
    visual_style = str(config.get("visual_style", "premium_luxe"))
    if visual_style not in VISUAL_STYLES:
        raise ValueError(f"visual_style should be one of: {', '.join(VISUAL_STYLES)}")


def get_canvas_size(plan_or_config: dict) -> tuple[int, int]:
    aspect_ratio = str(plan_or_config.get("aspect_ratio", "9:16"))
    return ASPECT_RATIOS.get(aspect_ratio, ASPECT_RATIOS["9:16"])


def get_visual_style(plan_or_config: dict) -> dict:
    visual_style = str(plan_or_config.get("visual_style", "premium_luxe"))
    return VISUAL_STYLES.get(visual_style, VISUAL_STYLES["premium_luxe"])


def get_layout(width: int, height: int) -> dict:
    if width > height:
        return {
            "brand_top": 22,
            "brand_left": 28,
            "title_top": 62,
            "title_font": 24,
            "caption_bottom": 24,
            "caption_font": 19,
            "caption_width": width - 56,
        }
    if width == height:
        return {
            "brand_top": 24,
            "brand_left": 24,
            "title_top": 74,
            "title_font": 25,
            "caption_bottom": 34,
            "caption_font": 20,
            "caption_width": width - 48,
        }
    return {
        "brand_top": 26,
        "brand_left": 24,
        "title_top": 82,
        "title_font": 26,
        "caption_bottom": 46,
        "caption_font": 21,
        "caption_width": width - 45,
    }


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def list_images() -> list[Path]:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(p for p in IMAGE_DIR.iterdir() if p.suffix.lower() in IMAGE_EXTS)


def wrap_text(text: str, max_chars: int) -> str:
    text = str(text)
    return "\n".join(text[i : i + max_chars] for i in range(0, len(text), max_chars))


def scene_duration(total: int, count: int) -> list[int]:
    base = max(3, math.floor(total / count))
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


def generate_plan(config: dict, image_paths: list[Path]) -> dict:
    duration = int(config.get("duration_seconds", 24))
    duration = min(max(duration, 15), 45)
    topic = config.get("topic", "今天想介绍一个本地门店")
    shop = config.get("shop_name", "本地门店")
    offer = config.get("main_offer", "服务流程清楚，沟通透明")
    area = config.get("city_area", "附近")
    cta = config.get("cta", "有需要可以提前咨询了解")

    scene_count = min(max(len(image_paths), 3), 5)
    durations = scene_duration(duration, scene_count)

    script_lines = [
        f"{area}想了解{topic}，可以先看这几个点。",
        f"到{shop}前，建议先了解环境、流程和沟通方式。",
        f"这里重点是：{offer}。",
        "如果你是第一次接触，先把问题问清楚，比盲目决定更稳妥。",
        cta,
    ][:scene_count]

    asset_types = ["门店/封面图", "环境/服务图", "核心卖点图", "流程/细节图", "引导/收尾图"]
    effects = ["slow_zoom_in", "pan_up", "cut", "caption_pop", "slow_zoom_out"]

    scenes = []
    cursor = 0
    for idx in range(scene_count):
        image = image_paths[idx % len(image_paths)] if image_paths else None
        scenes.append(
            {
                "order": idx + 1,
                "start": cursor,
                "duration": durations[idx],
                "asset": image.name if image else "",
                "asset_type": asset_types[idx],
                "caption": script_lines[idx],
                "voiceover": script_lines[idx],
                "effect": effects[idx],
            }
        )
        cursor += durations[idx]

    return {
        "shop_name": shop,
        "industry": config.get("industry", "本地服务"),
        "topic": topic,
        "platform": config.get("platform", "douyin"),
        "aspect_ratio": config.get("aspect_ratio", "9:16"),
        "visual_style": config.get("visual_style", "premium_luxe"),
        "duration_seconds": sum(durations),
        "cover_text": make_cover_text(topic),
        "titles": make_titles(config),
        "post_copy": make_post_copy(config),
        "scenes": scenes,
        "subtitle_style": "white_text_with_dark_shadow",
        "bgm_style": "clean_light",
    }


def make_cover_text(topic: str) -> str:
    topic = str(topic).strip()
    if len(topic) <= 14:
        return topic
    return topic[:14] + "..."


def make_titles(config: dict) -> list[str]:
    topic = config.get("topic", "门店介绍")
    area = config.get("city_area", "附近")
    shop = config.get("shop_name", "这家店")
    return [
        f"{area}想了解{topic}，先看这条",
        f"第一次来{shop}前，可以先看这几点",
        f"{topic}别急着决定，先把流程问清楚",
        f"给第一次了解{config.get('industry', '本地服务')}的人一点参考",
        f"{shop}服务流程简单介绍",
    ]


def make_post_copy(config: dict) -> str:
    return (
        f"{config.get('topic', '门店服务')}简单整理了一版，适合第一次了解的朋友先做参考。"
        f"具体情况建议结合自身需求，到正规机构当面咨询。"
    )


def check_compliance(config: dict, plan: dict) -> dict:
    text = json.dumps(plan, ensure_ascii=False)
    found = [term for term in MEDICAL_RISK_TERMS if term in text]
    mode = config.get("compliance_mode", "")
    issues = []
    if mode == "medical":
        for term in found:
            issues.append(f"出现医疗营销高风险词：{term}")
        if "优惠" in text or "低价" in text:
            issues.append("医疗类内容涉及价格促销时建议人工复核")
    return {
        "pass": len(issues) == 0,
        "risk_level": "low" if not issues else "medium",
        "issues": issues,
        "note": "医疗内容建议保留人工终审，不做疗效承诺和患者证言。",
    }


def copy_assets(image_paths: list[Path]) -> list[dict]:
    if ASSETS_DIR.exists():
        shutil.rmtree(ASSETS_DIR)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    copied = []
    for idx, path in enumerate(image_paths, start=1):
        suffix = path.suffix.lower()
        dest = ASSETS_DIR / f"image_{idx}{suffix}"
        shutil.copy2(path, dest)
        copied.append({"source": path.name, "file": dest.name})
    return copied


def write_srt(plan: dict) -> None:
    lines = []
    for idx, scene in enumerate(plan["scenes"], start=1):
        start = scene["start"]
        end = scene["start"] + scene["duration"]
        lines.extend(
            [
                str(idx),
                f"{fmt_time(start)} --> {fmt_time(end)}",
                scene["caption"],
                "",
            ]
        )
    (OUTPUT_DIR / "captions.srt").write_text("\n".join(lines), encoding="utf-8")


def write_voiceover_files(plan: dict) -> None:
    voice_dir = OUTPUT_DIR / "voiceover_segments"
    if voice_dir.exists():
        shutil.rmtree(voice_dir)
    voice_dir.mkdir(parents=True, exist_ok=True)
    all_lines = []
    for scene in plan["scenes"]:
        filename = f"scene_{scene['order']:02d}.txt"
        text = scene["voiceover"].strip()
        (voice_dir / filename).write_text(text, encoding="utf-8")
        all_lines.append(f"[{scene['order']:02d}] {text}")
    (OUTPUT_DIR / "voiceover.txt").write_text("\n".join(all_lines), encoding="utf-8")


def fmt_time(seconds: int) -> str:
    return f"00:00:{seconds:02d},000"


def write_html(plan: dict, assets: list[dict]) -> None:
    scene_data = []
    for idx, scene in enumerate(plan["scenes"]):
        asset = assets[idx % len(assets)]["file"] if assets else ""
        scene_data.append({**scene, "asset_file": asset})

    payload = {
        "plan": plan,
        "scenes": scene_data,
    }
    width, height = get_canvas_size(plan)
    layout = get_layout(width, height)
    style = get_visual_style(plan)
    accent = style["accent"]
    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(plan["shop_name"])} - AI 视频预览</title>
  <style>
    :root {{
      --accent: {accent};
      --pad: {layout["brand_left"]}px;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: radial-gradient(circle at 50% 30%, #1b2433, #0a0d14 70%);
      color: #fff;
      font-family: "Microsoft YaHei", "PingFang SC", Arial, sans-serif;
    }}
    .stage {{
      width: {width}px;
      height: {height}px;
      position: relative;
      overflow: hidden;
      border-radius: 18px;
      background: #0b1118;
      isolation: isolate;
      box-shadow: 0 30px 80px rgba(0,0,0,.55), 0 0 0 1px rgba(255,255,255,.04);
    }}
    .photo {{
      position: absolute;
      inset: -10%;
      width: 120%;
      height: 120%;
      object-fit: cover;
      transform: scale(1.06);
      transition: transform 4200ms cubic-bezier(.22,.61,.36,1), filter 600ms ease;
      filter: saturate(1.06) contrast(1.04) brightness(.94);
    }}
    .shade {{
      position: absolute;
      inset: 0;
      z-index: 1;
      pointer-events: none;
      background:
        linear-gradient(180deg, rgba(6,8,12,.72), rgba(6,8,12,.06) 30%, rgba(6,8,12,.10) 56%, rgba(6,8,12,.90)),
        radial-gradient(circle at 18% 12%, rgba(120,150,235,.16), transparent 42%);
    }}
    .segs {{
      position: absolute;
      top: {max(10, layout["brand_top"] - 14)}px;
      left: var(--pad);
      right: var(--pad);
      z-index: 3;
      display: flex;
      gap: 4px;
    }}
    .seg {{
      flex: 1;
      height: 3px;
      border-radius: 3px;
      background: rgba(255,255,255,.22);
      overflow: hidden;
    }}
    .seg > i {{
      display: block;
      height: 100%;
      width: 0;
      background: var(--accent);
      border-radius: 3px;
    }}
    .topbar {{
      position: absolute;
      top: {layout["brand_top"] + 6}px;
      left: var(--pad);
      right: var(--pad);
      z-index: 3;
    }}
    .brand {{
      display: inline-block;
      max-width: 100%;
      padding-left: 10px;
      border-left: 4px solid var(--accent);
      font-size: 13px;
      line-height: 1.15;
      font-weight: 700;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      text-shadow: 0 2px 12px rgba(0,0,0,.6);
    }}
    .coverTitle {{
      position: absolute;
      left: var(--pad);
      right: var(--pad);
      top: {layout["title_top"]}px;
      z-index: 3;
      font-size: {layout["title_font"]}px;
      line-height: 1.16;
      font-weight: 800;
      text-shadow: 0 3px 18px rgba(0,0,0,.6);
      opacity: 0;
      transform: translateY(10px);
      transition: opacity 700ms ease, transform 700ms ease;
    }}
    .coverTitle.show {{ opacity: 1; transform: translateY(0); }}
    .captionPanel {{
      position: absolute;
      left: var(--pad);
      right: var(--pad);
      bottom: {layout["caption_bottom"]}px;
      z-index: 3;
      display: flex;
      gap: 12px;
      padding: 14px 16px;
      border-radius: 14px;
      background: linear-gradient(180deg, rgba(12,14,20,.62), rgba(8,10,16,.78));
      backdrop-filter: blur(6px);
      box-shadow: 0 18px 50px rgba(0,0,0,.4);
      opacity: 0;
      transform: translateY(14px);
      transition: opacity 420ms ease, transform 420ms ease;
    }}
    .captionPanel.show {{ opacity: 1; transform: translateY(0); }}
    .captionPanel::before {{
      content: "";
      flex: 0 0 4px;
      border-radius: 3px;
      background: var(--accent);
    }}
    .caption {{
      font-size: {layout["caption_font"]}px;
      line-height: 1.32;
      font-weight: 700;
      text-wrap: balance;
      text-shadow: 0 2px 10px rgba(0,0,0,.5);
    }}
    .meta {{
      position: absolute;
      left: var(--pad);
      right: var(--pad);
      bottom: calc({layout["caption_bottom"]}px + 4px);
      z-index: 3;
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      color: rgba(225,230,240,.9);
      text-shadow: 0 1px 6px rgba(0,0,0,.6);
      transform: translateY(-100%);
      padding-bottom: 8px;
    }}
  </style>
</head>
<body>
  <div class="stage" id="stage">
    <img class="photo" id="photo" alt="">
    <div class="shade"></div>
    <div class="segs" id="segs"></div>
    <div class="topbar"><span class="brand" id="brand"></span></div>
    <div class="coverTitle" id="coverTitle"></div>
    <div class="meta"><span id="timecode"></span><span id="platformTag"></span></div>
    <div class="captionPanel" id="captionPanel"><div class="caption" id="caption"></div></div>
  </div>
  <script>
    window.VIDEO_PAYLOAD = {json.dumps(payload, ensure_ascii=False)};
  </script>
  <script>
    const payload = window.VIDEO_PAYLOAD;
    const scenes = payload.scenes;
    const plan = payload.plan;
    const total = plan.duration_seconds;
    const photo = document.getElementById('photo');
    const brand = document.getElementById('brand');
    const coverTitle = document.getElementById('coverTitle');
    const caption = document.getElementById('caption');
    const captionPanel = document.getElementById('captionPanel');
    const timecode = document.getElementById('timecode');
    const platformTag = document.getElementById('platformTag');
    const segs = document.getElementById('segs');

    brand.textContent = plan.shop_name + ' · ' + plan.industry;
    coverTitle.textContent = plan.cover_text;
    platformTag.textContent = plan.platform;

    // 分段进度条：每个场景一段
    const bars = scenes.map(() => {{
      const seg = document.createElement('div');
      seg.className = 'seg';
      const fill = document.createElement('i');
      seg.appendChild(fill);
      segs.appendChild(seg);
      return fill;
    }});

    let started = performance.now();
    let active = -1;

    function pickIndex(t) {{
      let idx = scenes.length - 1;
      for (let i = 0; i < scenes.length; i++) {{
        if (t >= scenes[i].start && t < scenes[i].start + scenes[i].duration) {{ idx = i; break; }}
      }}
      return idx;
    }}

    function render() {{
      const elapsed = (performance.now() - started) / 1000;
      const t = Math.min(elapsed, total - 0.01);
      const idx = pickIndex(t);
      const scene = scenes[idx];
      if (idx !== active) {{
        active = idx;
        photo.src = 'assets/' + scene.asset_file;
        // 重置再触发运镜，形成缓动 Ken Burns
        const out = String(scene.effect).includes('out');
        photo.style.transition = 'none';
        photo.style.transform = out ? 'scale(1.14) translateY(6px)' : 'scale(1.04) translateY(-4px)';
        void photo.offsetWidth;
        photo.style.transition = 'transform 4200ms cubic-bezier(.22,.61,.36,1), filter 600ms ease';
        requestAnimationFrame(() => {{
          photo.style.transform = out ? 'scale(1.04) translateY(-4px)' : 'scale(1.14) translateY(6px)';
        }});
        // 字幕换场动画
        caption.textContent = scene.caption;
        timecode.textContent = scene.start + '-' + (scene.start + scene.duration) + 's';
        captionPanel.classList.remove('show');
        void captionPanel.offsetWidth;
        captionPanel.classList.add('show');
        coverTitle.classList.toggle('show', idx === 0);
      }}
      // 进度条逐段填充
      bars.forEach((b, i) => {{
        let r = 0;
        if (i < idx) r = 1;
        else if (i === idx) r = Math.min(1, (t - scene.start) / scene.duration);
        b.style.width = (r * 100).toFixed(1) + '%';
      }});
      if (elapsed < total) requestAnimationFrame(render);
      else window.__VIDEO_DONE__ = true;
    }}
    requestAnimationFrame(render);
  </script>
</body>
</html>
"""
    (OUTPUT_DIR / "preview.html").write_text(html_doc, encoding="utf-8")


def write_markdown(plan: dict, compliance: dict) -> None:
    rows = []
    for scene in plan["scenes"]:
        rows.append(
            f"| {scene['order']} | {scene['start']}-{scene['start'] + scene['duration']}s | "
            f"{scene['asset_type']} | {scene['caption']} | {scene['effect']} |"
        )
    md = f"""# AI 短视频工作流输出

## 基本信息

- 店铺：{plan['shop_name']}
- 行业：{plan['industry']}
- 主题：{plan['topic']}
- 平台：{plan['platform']}
- 时长：{plan['duration_seconds']} 秒
- 封面文案：{plan['cover_text']}

## 标题备选

{chr(10).join(f"- {title}" for title in plan['titles'])}

## 分镜

| 序号 | 时间 | 素材类型 | 字幕/口播 | 效果 |
|---|---:|---|---|---|
{chr(10).join(rows)}

## 发布文案

{plan['post_copy']}

## 合规检查

- 是否通过：{"是" if compliance['pass'] else "否"}
- 风险等级：{compliance['risk_level']}
- 备注：{compliance['note']}

{chr(10).join(f"- {issue}" for issue in compliance['issues']) if compliance['issues'] else "- 暂未发现内置规则命中的风险词。"}
"""
    (OUTPUT_DIR / "video_plan.md").write_text(md, encoding="utf-8")


def make_render_record(plan: dict, kind: str, file: str) -> dict:
    # renders[] 条目构造统一走 render_mp4.make_render_entry，避免契约逻辑双份实现。
    return make_render_entry(plan, kind, file)


def crop_cover(img: Image.Image, width: int, height: int) -> Image.Image:
    src_w, src_h = img.size
    scale = max(width / src_w, height / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    return resized.crop((left, top, left + width, top + height))


def font_for_size(size: int, bold: bool = False):
    candidates = ["msyhbd.ttc", "msyh.ttc"] if bold else ["msyh.ttc", "msyhbd.ttc"]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.strip().lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _vertical_gradient(size: tuple[int, int], top: tuple, bottom: tuple) -> Image.Image:
    w, h = size
    grad = Image.new("RGB", (1, h))
    px = grad.load()
    for y in range(h):
        t = y / max(1, h - 1)
        px[0, y] = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    return grad.resize((w, h), Image.Resampling.BILINEAR)


def _soft_light_blob(size: tuple[int, int], center: tuple[int, int], radius: int, color: tuple, alpha: int) -> Image.Image:
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = center
    d.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(*color, alpha))
    return layer.filter(ImageFilter.GaussianBlur(radius * 0.55))


def make_placeholder_images(config: dict, count: int = 3) -> list[Path]:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    # 占位图模拟“用户的真实照片”，因此不烤任何店名/标题文字进去——
    # 这些信息由合成层（品牌条/标题/字幕）负责，避免画面文字重复打架。
    labels = ["门店空间", "环境细节", "服务流程", "专业团队", "欢迎到店"]
    # 深色电影感配色：(顶部, 底部, 主光斑色, 辅光斑色)
    palettes = [
        ((28, 33, 48), (12, 14, 22), (120, 150, 235), (90, 200, 180)),
        ((38, 30, 28), (16, 12, 12), (220, 160, 110), (200, 120, 90)),
        ((26, 36, 36), (10, 16, 18), (90, 200, 190), (120, 180, 150)),
        ((34, 28, 44), (14, 10, 20), (170, 130, 230), (210, 140, 200)),
        ((30, 34, 30), (12, 16, 12), (160, 200, 120), (200, 190, 110)),
    ]
    w, h = 1080, 1920
    out = []
    for idx in range(count):
        path = IMAGE_DIR / f"demo_{idx + 1}.png"
        top, bottom, glow_a, glow_b = palettes[idx % len(palettes)]
        label = labels[idx % len(labels)]

        img = _vertical_gradient((w, h), top, bottom).convert("RGBA")
        # 两团柔焦光，营造景深与空间感
        img = Image.alpha_composite(img, _soft_light_blob((w, h), (int(w * 0.26), int(h * 0.22)), 520, glow_a, 78))
        img = Image.alpha_composite(img, _soft_light_blob((w, h), (int(w * 0.82), int(h * 0.74)), 600, glow_b, 64))
        # 小的散景光点
        for bx, by, br, ba in [(190, 1380, 70, 60), (320, 1500, 44, 50), (860, 520, 90, 46), (760, 360, 50, 40)]:
            img = Image.alpha_composite(img, _soft_light_blob((w, h), (bx, by), br, (255, 255, 255), ba))
        img = img.convert("RGB")

        # 暗角，把视线收拢到中心
        vignette = Image.new("L", (w, h), 0)
        ImageDraw.Draw(vignette).ellipse((-int(w * 0.35), -int(h * 0.18), int(w * 1.35), int(h * 1.18)), fill=255)
        vignette = vignette.filter(ImageFilter.GaussianBlur(260))
        dark = Image.new("RGB", (w, h), (0, 0, 0))
        img = Image.composite(img, dark, vignette)

        # 中段构图：柔和对角光带 + 同心细圆环，填充空旷感（模拟真实场景的层次与焦点）
        deco = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ddraw = ImageDraw.Draw(deco)
        ddraw.polygon(
            [(0, int(h * 0.30)), (w, int(h * 0.10)), (w, int(h * 0.17)), (0, int(h * 0.37))],
            fill=(*glow_a, 24),
        )
        cx, cy = int(w * 0.5), int(h * 0.45)
        for r, a in [(380, 30), (290, 24), (200, 18)]:
            ddraw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(235, 240, 250, a), width=3)
        deco = deco.filter(ImageFilter.GaussianBlur(2))
        img = Image.alpha_composite(img.convert("RGBA"), deco).convert("RGB")

        draw = ImageDraw.Draw(img)
        font_tag = font_for_size(30)
        # 仅在右下角留一个极低调的占位水印，说明这是示例素材；不喧宾夺主。
        tag = f"示例素材 · {label}"
        tag_w = draw.textbbox((0, 0), tag, font=font_tag)[2]
        draw.text((w - tag_w - 64, h - 110), tag, fill=(140, 148, 165), font=font_tag)
        img.save(path)
        out.append(path)
    return out


def wrap_by_pixel(text: str, font, max_width: int) -> str:
    lines = []
    current = ""
    probe = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(probe)
    for ch in str(text):
        candidate = current + ch
        box = draw.textbbox((0, 0), candidate, font=font)
        if box[2] - box[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return "\n".join(lines[:4])


def _scrim(size: tuple[int, int], top_strength: int, bottom_strength: int) -> Image.Image:
    """上下双向压暗的平滑遮罩，保证叠字区域可读，中间留出画面。"""
    w, h = size
    mask = Image.new("L", (1, h), 0)
    px = mask.load()
    for y in range(h):
        t = y / max(1, h - 1)
        top = top_strength * max(0.0, 1 - t / 0.42) ** 1.6
        bottom = bottom_strength * max(0.0, (t - 0.46) / 0.54) ** 1.4
        px[0, y] = int(min(255, max(top, bottom)))
    mask = mask.resize((w, h), Image.Resampling.BILINEAR)
    scrim = Image.new("RGBA", (w, h), (6, 8, 12, 0))
    scrim.putalpha(mask)
    return scrim


def _ease_in_out(t: float) -> float:
    """平滑缓动，0→1，两端慢中间快，让运镜更自然。"""
    return 3 * t * t - 2 * t * t * t


def _ken_burns_crop(img: Image.Image, width: int, height: int, effect: str, prog: float) -> Image.Image:
    """根据 effect 和进度 prog(0→1) 输出一帧带运镜的裁切。
    先把图铺满画布并留出余量，再在余量内平滑缩放/平移。"""
    over = 1.16  # 放大余量，给平移/缩放留空间
    big = crop_cover(img, int(width * over), int(height * over))
    bw, bh = big.size
    e = _ease_in_out(prog)

    # 缩放系数：zoom_in 由小变大，zoom_out 反之，其余维持轻微推进
    if "zoom_in" in effect:
        scale = 1.0 + 0.10 * e
    elif "zoom_out" in effect:
        scale = 1.10 - 0.10 * e
    else:
        scale = 1.03 + 0.04 * e

    crop_w, crop_h = width / scale, height / scale
    # 平移：pan_up 纵向移动，cut/默认轻微横移
    max_dx, max_dy = bw - crop_w, bh - crop_h
    if "pan_up" in effect:
        cx, cy = max_dx * 0.5, max_dy * (1 - e)
    elif "pan" in effect:
        cx, cy = max_dx * e, max_dy * 0.5
    else:
        cx, cy = max_dx * (0.5 + 0.12 * (e - 0.5)), max_dy * 0.5

    box = (cx, cy, cx + crop_w, cy + crop_h)
    return big.resize((width, height), Image.Resampling.LANCZOS, box=box)


def make_render_context(plan: dict, ss: int = 2) -> dict:
    out_w, out_h = get_canvas_size(plan)
    width, height = out_w * ss, out_h * ss
    base_layout = get_layout(out_w, out_h)
    layout = {k: (v * ss if k != "caption_width" else width - 45 * ss) for k, v in base_layout.items()}
    accent = hex_to_rgb(get_visual_style(plan)["accent"])
    return {
        "ss": ss,
        "out_w": out_w,
        "out_h": out_h,
        "width": width,
        "height": height,
        "layout": layout,
        "accent": accent,
        "pad": layout["brand_left"],
        "n": len(plan["scenes"]),
        "font_brand": font_for_size(int(15 * ss), bold=True),
        "font_title": font_for_size(layout["title_font"], bold=True),
        "font_caption": font_for_size(layout["caption_font"], bold=True),
        "font_meta": font_for_size(int(13 * ss)),
        "scrim_layer": _scrim((width, height), top_strength=150, bottom_strength=225),
        "glow_layer": _soft_light_blob(
            (width, height), (int(width * 0.18), int(height * 0.12)), int(width * 0.5), accent, 30
        ),
    }


def draw_scene_overlay(canvas: Image.Image, plan: dict, scene: dict, idx: int, seg_prog: float, ctx: dict) -> Image.Image:
    ss = ctx["ss"]
    width = ctx["width"]
    height = ctx["height"]
    layout = ctx["layout"]
    accent = ctx["accent"]
    pad = ctx["pad"]
    canvas = Image.alpha_composite(canvas.convert("RGBA"), ctx["scrim_layer"])
    canvas = Image.alpha_composite(canvas, ctx["glow_layer"]).convert("RGB")
    draw = ImageDraw.Draw(canvas)

    bar_y = layout["brand_top"]
    draw.rounded_rectangle((pad, bar_y, pad + 6 * ss, bar_y + 30 * ss), radius=3 * ss, fill=accent)
    draw.text(
        (pad + 18 * ss, bar_y + 4 * ss),
        f"{plan['shop_name']} · {plan['industry']}",
        fill=(255, 255, 255),
        font=ctx["font_brand"],
        stroke_width=ss,
        stroke_fill=(0, 0, 0),
    )

    title_t = min(1.0, (idx + seg_prog) / 0.6) if idx == 0 else 1.0
    ty = layout["title_top"] + int((1 - _ease_in_out(title_t)) * 18 * ss)
    draw.multiline_text(
        (pad, ty),
        wrap_by_pixel(plan["cover_text"], ctx["font_title"], layout["caption_width"]),
        fill=(255, 255, 255),
        font=ctx["font_title"],
        spacing=8 * ss,
        stroke_width=2 * ss,
        stroke_fill=(8, 10, 16),
    )

    cap_lines = wrap_by_pixel(scene["caption"], ctx["font_caption"], width - 2 * (pad + 20 * ss))
    line_count = cap_lines.count("\n") + 1
    cap_h = line_count * int(layout["caption_font"] * 1.5) + 36 * ss
    panel_bottom = height - layout["caption_bottom"]
    panel_top = panel_bottom - cap_h
    intro = _ease_in_out(min(1.0, seg_prog / 0.25))
    slide = int((1 - intro) * 16 * ss)
    panel = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(panel)
    pdraw.rounded_rectangle(
        (pad - 4 * ss, panel_top + slide, width - pad + 4 * ss, panel_bottom + slide),
        radius=18 * ss,
        fill=(10, 12, 18, int(150 * intro)),
    )
    canvas = Image.alpha_composite(canvas.convert("RGBA"), panel).convert("RGB")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        (pad + 6 * ss, panel_top + 18 * ss + slide, pad + 12 * ss, panel_bottom - 18 * ss + slide),
        radius=3 * ss,
        fill=accent,
    )
    draw.multiline_text(
        (pad + 26 * ss, panel_top + 18 * ss + slide),
        cap_lines,
        fill=(255, 255, 255),
        font=ctx["font_caption"],
        spacing=10 * ss,
        stroke_width=ss,
        stroke_fill=(6, 8, 12),
    )

    draw.text(
        (pad, panel_top - 26 * ss + slide),
        f"{scene['start']:02d}-{scene['start'] + scene['duration']:02d}s",
        fill=(218, 224, 235),
        font=ctx["font_meta"],
        stroke_width=ss,
        stroke_fill=(0, 0, 0),
    )
    plat = str(plan["platform"])
    plat_w = draw.textbbox((0, 0), plat, font=ctx["font_meta"])[2]
    draw.text(
        (width - pad - plat_w, panel_top - 26 * ss + slide),
        plat,
        fill=(218, 224, 235),
        font=ctx["font_meta"],
        stroke_width=ss,
        stroke_fill=(0, 0, 0),
    )

    rail_y = layout["brand_top"] - 14 * ss
    gap = 6 * ss
    seg_w = (width - 2 * pad - gap * (ctx["n"] - 1)) / ctx["n"]
    for s in range(ctx["n"]):
        x0 = pad + s * (seg_w + gap)
        draw.rounded_rectangle((x0, rail_y, x0 + seg_w, rail_y + 4 * ss), radius=2 * ss, fill=(40, 44, 54))
        fill_ratio = 1.0 if s < idx else (seg_prog if s == idx else 0.0)
        if fill_ratio > 0:
            draw.rounded_rectangle(
                (x0, rail_y, x0 + seg_w * fill_ratio, rail_y + 4 * ss),
                radius=2 * ss,
                fill=accent,
            )
    return canvas


def render_scene_frames(plan: dict, assets: list[dict], scene: dict, idx: int, n_frames: int, ss: int = 2) -> list[Image.Image]:
    return render_scene_frames_with_context(plan, assets, scene, idx, n_frames, make_render_context(plan, ss=ss))


def render_scene_frames_with_context(
    plan: dict, assets: list[dict], scene: dict, idx: int, n_frames: int, ctx: dict
) -> list[Image.Image]:
    asset = assets[idx % len(assets)]["file"] if assets else ""
    src = Image.open(ASSETS_DIR / asset).convert("RGB")
    frames = []
    for frame_idx in range(max(1, n_frames)):
        prog = frame_idx / (n_frames - 1) if n_frames > 1 else 0.0
        kb = _ken_burns_crop(src, ctx["width"], ctx["height"], scene["effect"], prog)
        frames.append(draw_scene_overlay(kb, plan, scene, idx, prog, ctx))
    return frames


def render_gif_preview(plan: dict, assets: list[dict]) -> None:
    frames = []
    durations = []
    fps = 12  # 补间帧率，越高越顺滑
    out_w, out_h = get_canvas_size(plan)
    ss = 2  # 超采样：放大渲染再缩小，文字与圆角更锐利
    ctx = make_render_context(plan, ss=ss)

    for idx, scene in enumerate(plan["scenes"]):
        # 每段固定约 fps 帧：顺滑且体积可控
        seg_frames = max(8, fps)
        for frame in render_scene_frames_with_context(plan, assets, scene, idx, seg_frames, ctx):
            frames.append(frame.resize((out_w, out_h), Image.Resampling.LANCZOS))
            durations.append(int(scene["duration"] / seg_frames * 1000))

    if frames:
        frames[0].save(
            OUTPUT_DIR / "preview.gif",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0,
            optimize=True,
            disposal=2,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a local-business short-video workflow draft.")
    parser.add_argument("--config", default=str(ROOT / "config.json"))
    parser.add_argument("--demo-assets", action="store_true", help="Create placeholder images if no images exist.")
    parser.add_argument("--refresh-demo-assets", action="store_true", help="Regenerate demo_*.png without touching real images.")
    parser.add_argument("--clean", action="store_true", help="Clear generated output before running.")
    parser.add_argument("--provider", default="mock", choices=["mock", "claude"], help="LLM provider for analysis/script/scenes.")
    parser.add_argument("--tts-provider", default="edge", choices=["edge", "aliyun", "none"], help="TTS provider for voiceover audio.")
    parser.add_argument("--skip-tts", action="store_true", help="Skip voiceover audio generation.")
    parser.add_argument("--skip-mp4", action="store_true", help="Skip MP4 rendering.")
    args = parser.parse_args()

    if args.clean and OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    ensure_dirs()
    config_path = Path(args.config)
    config = load_config(config_path)
    if args.refresh_demo_assets:
        for path in IMAGE_DIR.glob("demo_*.png"):
            path.unlink()
        make_placeholder_images(config)
    images = list_images()
    if not images and args.demo_assets:
        images = make_placeholder_images(config)
    if not images:
        raise SystemExit("No images found. Put 1-5 images into input/images or run with --demo-assets.")

    asset_refs = [
        {"asset_id": f"asset_{idx}", "file": str(path), "kind": "image", "duration": None, "tags": []}
        for idx, path in enumerate(images, start=1)
    ]
    project_input = build_project_input(config, assets=asset_refs)
    try:
        generated = generate_video_content(project_input, provider_name=args.provider)
    except LLMGenerationError as exc:
        raise SystemExit(f"LLM generation failed: {exc}") from exc
    plan = legacy_plan_from_generation(config, generated)
    compliance = check_compliance(config, plan)
    # TODO(T-002): when compliance fails in medical mode, ask the LLM provider to regenerate with the issues as constraints.
    assets = copy_assets(images)
    write_srt(plan)
    write_voiceover_files(plan)
    tts_provider = "none" if args.skip_tts else args.tts_provider
    try:
        audio = generate_voiceover_audio(plan["scenes"], config, OUTPUT_DIR, provider_name=tts_provider)
    except TTSGenerationError as exc:
        print(f"TTS warning: {exc}")
        audio = {"provider": tts_provider, "voice": "", "segments": 0, "total_audio_duration": 0.0}
    write_html(plan, assets)
    write_markdown(plan, compliance)
    render_gif_preview(plan, assets)
    renders = [
        make_render_record(plan, "preview_html", "preview.html"),
        make_render_record(plan, "preview_gif", "preview.gif"),
    ]
    if not args.skip_mp4:
        try:
            renders.append(render_mp4(plan, assets, OUTPUT_DIR, render_scene_frames))
        except MP4RenderError as exc:
            print(f"MP4 warning: {exc}")
    (OUTPUT_DIR / "plan.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "project_id": project_input["project_id"],
                "status": "generated",
                "input": project_input["input"],
                "config": project_input["config"],
                "analysis": generated["analysis"],
                "script": generated["script"],
                "scenes": generated["scenes"],
                "audio": audio,
                "renders": renders,
                "plan": plan,
                "compliance": compliance,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Generated: {OUTPUT_DIR}")
    print("Key outputs:")
    print(f"- {OUTPUT_DIR / 'video_plan.md'}")
    print(f"- {OUTPUT_DIR / 'preview.gif'}")
    print(f"- {OUTPUT_DIR / 'preview.html'}")
    print(f"- {OUTPUT_DIR / 'plan.json'}")
    print(f"- {OUTPUT_DIR / 'voiceover.txt'}")
    if audio.get("segments"):
        print(f"- {OUTPUT_DIR / 'voiceover_audio'}")
    if any(item.get("kind") == "mp4" for item in renders):
        print(f"- {OUTPUT_DIR / 'video.mp4'}")


if __name__ == "__main__":
    main()
