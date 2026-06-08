import argparse
import html
import json
import math
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


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
    visual_style = str(config.get("visual_style", "clean_clinic"))
    if visual_style not in VISUAL_STYLES:
        raise ValueError(f"visual_style should be one of: {', '.join(VISUAL_STYLES)}")


def get_canvas_size(plan_or_config: dict) -> tuple[int, int]:
    aspect_ratio = str(plan_or_config.get("aspect_ratio", "9:16"))
    return ASPECT_RATIOS.get(aspect_ratio, ASPECT_RATIOS["9:16"])


def get_visual_style(plan_or_config: dict) -> dict:
    visual_style = str(plan_or_config.get("visual_style", "clean_clinic"))
    return VISUAL_STYLES.get(visual_style, VISUAL_STYLES["clean_clinic"])


def get_layout(width: int, height: int) -> dict:
    if width > height:
        return {
            "brand_top": 22,
            "brand_left": 28,
            "title_top": 62,
            "title_font": 30,
            "caption_bottom": 24,
            "caption_font": 24,
            "caption_width": width - 56,
        }
    if width == height:
        return {
            "brand_top": 24,
            "brand_left": 24,
            "title_top": 74,
            "title_font": 31,
            "caption_bottom": 34,
            "caption_font": 25,
            "caption_width": width - 48,
        }
    return {
        "brand_top": 26,
        "brand_left": 24,
        "title_top": 82,
        "title_font": 34,
        "caption_bottom": 46,
        "caption_font": 27,
        "caption_width": width - 45,
    }


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def list_images() -> list[Path]:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(p for p in IMAGE_DIR.iterdir() if p.suffix.lower() in IMAGE_EXTS)


def make_placeholder_images(config: dict, count: int = 3) -> list[Path]:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    labels = [
        ("门店外观", config.get("shop_name", "门店")),
        ("服务环境", config.get("industry", "本地服务")),
        ("流程说明", config.get("main_offer", "核心卖点")),
    ]
    out = []
    for idx in range(count):
        path = IMAGE_DIR / f"demo_{idx + 1}.png"
        if path.exists():
            out.append(path)
            continue
        img = Image.new("RGB", (1080, 1920), color=(24 + idx * 18, 34 + idx * 24, 46 + idx * 18))
        draw = ImageDraw.Draw(img)
        try:
            font_big = ImageFont.truetype("msyh.ttc", 92)
            font_mid = ImageFont.truetype("msyh.ttc", 58)
            font_small = ImageFont.truetype("msyh.ttc", 38)
        except OSError:
            font_big = ImageFont.load_default()
            font_mid = ImageFont.load_default()
            font_small = ImageFont.load_default()
        title, subtitle = labels[idx % len(labels)]
        draw.rounded_rectangle((88, 190, 992, 1650), radius=42, fill=(245, 248, 250))
        draw.text((140, 290), title, fill=(23, 31, 42), font=font_big)
        draw.text((140, 430), wrap_text(subtitle, 12), fill=(55, 70, 84), font=font_mid, spacing=22)
        draw.line((140, 1420, 940, 1420), fill=(67, 111, 165), width=8)
        draw.text((140, 1480), "示例素材，可替换为真实照片", fill=(86, 96, 106), font=font_small)
        img.save(path)
        out.append(path)
    return out


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
        "visual_style": config.get("visual_style", "clean_clinic"),
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
    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(plan["shop_name"])} - AI 视频预览</title>
  <style>
    html, body {{
      margin: 0;
      background: #111827;
      color: #fff;
      font-family: "Microsoft YaHei", Arial, sans-serif;
    }}
    .stage {{
      width: {width}px;
      height: {height}px;
      position: relative;
      overflow: hidden;
      background: #0b1118;
      isolation: isolate;
    }}
    .photo {{
      position: absolute;
      inset: -18px;
      width: calc(100% + 36px);
      height: calc(100% + 36px);
      object-fit: cover;
      transform: scale(1.04);
      transition: transform 1200ms ease, filter 500ms ease;
      filter: saturate(1.08) contrast(1.04) brightness(.92);
    }}
    .shade {{
      position: absolute;
      inset: 0;
      z-index: 1;
      background:
        linear-gradient(180deg, rgba(8,14,22,.68), rgba(8,14,22,.10) 34%, rgba(8,14,22,.08) 58%, rgba(8,14,22,.88)),
        radial-gradient(circle at 24% 18%, rgba(86,142,255,.18), transparent 34%),
        radial-gradient(circle at 76% 72%, rgba(54,211,153,.12), transparent 30%);
    }}
    .topbar {{
      position: absolute;
      top: {layout["brand_top"]}px;
      left: {layout["brand_left"]}px;
      right: {layout["brand_left"]}px;
      z-index: 2;
      display: flex;
      align-items: center;
      justify-content: flex-start;
      gap: 10px;
    }}
    .brand {{
      min-width: 0;
      max-width: 300px;
      padding-left: 10px;
      border-left: 4px solid {style["accent"]};
      font-size: 13px;
      line-height: 1.12;
      font-weight: 700;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      text-shadow: 0 2px 12px rgba(0,0,0,.45);
    }}
    .sceneNo {{
      display: none;
    }}
    .coverTitle {{
      position: absolute;
      left: {layout["brand_left"]}px;
      right: {layout["brand_left"]}px;
      top: {layout["title_top"]}px;
      z-index: 2;
      font-size: {layout["title_font"]}px;
      line-height: 1.12;
      font-weight: 900;
      letter-spacing: 0;
      text-shadow: 0 4px 20px rgba(0,0,0,.58);
    }}
    .captionPanel {{
      position: absolute;
      left: 18px;
      right: 18px;
      bottom: {layout["caption_bottom"]}px;
      z-index: 2;
      padding: 18px 18px 17px;
      border-top: 1px solid rgba(255,255,255,.26);
      border-radius: 0;
      background: linear-gradient(180deg, {style["shadow"]}, {style["overlay"]});
      box-shadow: 0 -18px 56px rgba(0,0,0,.25);
    }}
    .caption {{
      font-size: {layout["caption_font"]}px;
      line-height: 1.22;
      font-weight: 900;
      letter-spacing: 0;
      text-wrap: balance;
      text-shadow: 0 2px 8px rgba(0,0,0,.32);
    }}
    .meta {{
      display: none;
    }}
    .cta {{
      display: none;
    }}
    .cta strong {{
      color: #fff;
      font-size: 13px;
    }}
    .progressRail {{
      display: none;
    }}
    .progress {{
      height: 100%;
      background: #f8d66d;
      width: 0;
    }}
  </style>
</head>
<body>
  <div class="stage" id="stage">
    <img class="photo" id="photo" alt="">
    <div class="shade"></div>
    <div class="topbar">
      <div class="brand" id="brand"></div>
      <div class="sceneNo" id="sceneNo"></div>
    </div>
    <div class="coverTitle" id="coverTitle"></div>
    <div class="captionPanel">
      <div class="caption" id="caption"></div>
      <div class="meta">
        <span id="meta"></span>
        <span id="timecode"></span>
      </div>
    </div>
    <div class="cta"><strong id="ctaMain"></strong><span id="platformTag"></span></div>
    <div class="progressRail"><div class="progress" id="progress"></div></div>
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
    const sceneNo = document.getElementById('sceneNo');
    const coverTitle = document.getElementById('coverTitle');
    const caption = document.getElementById('caption');
    const meta = document.getElementById('meta');
    const timecode = document.getElementById('timecode');
    const ctaMain = document.getElementById('ctaMain');
    const platformTag = document.getElementById('platformTag');
    const progress = document.getElementById('progress');
    let started = performance.now();
    let active = -1;
    brand.textContent = plan.shop_name + ' · ' + plan.industry;
    meta.textContent = plan.topic + ' / ' + plan.platform;
    brand.textContent = plan.shop_name + ' · ' + plan.industry;
    coverTitle.textContent = plan.cover_text;
    meta.textContent = plan.topic;
    ctaMain.textContent = '建议面诊咨询';
    platformTag.textContent = plan.platform;

    function pickScene(t) {{
      let current = scenes[scenes.length - 1];
      for (const scene of scenes) {{
        if (t >= scene.start && t < scene.start + scene.duration) current = scene;
      }}
      return current;
    }}

    function render() {{
      const elapsed = (performance.now() - started) / 1000;
      const t = Math.min(elapsed, total - 0.01);
      const scene = pickScene(t);
      if (scene.order !== active) {{
        active = scene.order;
        photo.src = 'assets/' + scene.asset_file;
        caption.textContent = scene.caption;
        sceneNo.textContent = String(scene.order).padStart(2, '0');
        timecode.textContent = `${{scene.start}}-${{scene.start + scene.duration}}s`;
        photo.style.transform = scene.effect.includes('out') ? 'scale(1.02) translateY(-4px)' : 'scale(1.13) translateY(5px)';
      }}
      progress.style.width = ((elapsed / total) * 100).toFixed(2) + '%';
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


def render_legacy_gif_preview(plan: dict, assets: list[dict]) -> None:
    frames = []
    frame_duration_ms = 1100
    width, height = 360, 640
    for idx, scene in enumerate(plan["scenes"]):
        asset = assets[idx % len(assets)]["file"] if assets else ""
        img_path = ASSETS_DIR / asset
        base = Image.open(img_path).convert("RGB")
        base = crop_cover(base, width, height)
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        odraw.rectangle((0, 0, width, 150), fill=(7, 12, 20, 154))
        odraw.rectangle((0, 350, width, height), fill=(7, 12, 20, 186))
        odraw.ellipse((-50, -70, 170, 150), fill=(77, 132, 255, 48))
        odraw.ellipse((230, 410, 470, 690), fill=(52, 211, 153, 36))
        base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(base)
        font_brand, font_caption, font_meta = load_fonts()
        font_title = font_for_size(28)
        font_caption = font_for_size(25)
        font_meta = font_for_size(13)
        draw.rounded_rectangle((20, 22, 265, 52), radius=15, fill=(16, 24, 36), outline=(220, 232, 240), width=1)
        draw.rounded_rectangle((292, 22, 340, 52), radius=15, fill=(248, 250, 252))
        draw.text((306, 31), f"{idx + 1:02d}", fill=(15, 23, 42), font=font_meta)
        draw.rounded_rectangle((20, 22, 265, 52), radius=15, fill=(16, 24, 36), outline=(220, 232, 240), width=1)
        draw.text((31, 31), f"{plan['shop_name']} · {plan['industry']}", fill=(255, 255, 255), font=font_brand)
        draw.multiline_text(
            (22, 86),
            wrap_by_pixel(plan["cover_text"], font_title, 315),
            fill=(255, 255, 255),
            font=font_title,
            spacing=6,
            stroke_width=3,
            stroke_fill=(8, 13, 20),
        )
        draw.rounded_rectangle((18, 408, 342, 562), radius=18, fill=(9, 14, 22), outline=(96, 112, 132), width=1)
        draw.text((22, 28), f"{plan['shop_name']} · {plan['industry']}", fill=(255, 255, 255), font=font_brand)
        draw.rounded_rectangle((20, 22, 265, 52), radius=15, fill=(16, 24, 36), outline=(220, 232, 240), width=1)
        draw.text((31, 31), f"{plan['shop_name']} · {plan['industry']}", fill=(255, 255, 255), font=font_brand)
        draw.multiline_text(
            (36, 428),
            wrap_by_pixel(scene["caption"], font_caption, 288),
            fill=(255, 255, 255),
            font=font_caption,
            spacing=7,
            stroke_width=2,
            stroke_fill=(8, 13, 20),
        )
        draw.text((22, 580), f"{scene['start']}-{scene['start'] + scene['duration']}s", fill=(220, 232, 240), font=font_meta)
        draw.text((278, 580), plan["platform"], fill=(220, 232, 240), font=font_meta)
        draw.rounded_rectangle((22, 610, 338, 615), radius=3, fill=(82, 91, 105))
        progress_w = int(316 * ((idx + 1) / len(plan["scenes"])))
        draw.rounded_rectangle((22, 610, 22 + progress_w, 615), radius=3, fill=(248, 214, 109))
        frames.append(base)
    if frames:
        frames[0].save(
            OUTPUT_DIR / "preview.gif",
            save_all=True,
            append_images=frames[1:],
            duration=frame_duration_ms,
            loop=0,
            optimize=True,
        )


def crop_cover(img: Image.Image, width: int, height: int) -> Image.Image:
    src_w, src_h = img.size
    scale = max(width / src_w, height / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    return resized.crop((left, top, left + width, top + height))


def load_fonts():
    try:
        return (
            ImageFont.truetype("msyh.ttc", 16),
            ImageFont.truetype("msyh.ttc", 30),
            ImageFont.truetype("msyh.ttc", 14),
        )
    except OSError:
        font = ImageFont.load_default()
        return font, font, font


def font_for_size(size: int):
    try:
        return ImageFont.truetype("msyh.ttc", size)
    except OSError:
        return ImageFont.load_default()


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.strip().lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def make_placeholder_images(config: dict, count: int = 3) -> list[Path]:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    cards = [
        ("SHOP FRONT", config.get("shop_name", "Local Shop"), "First impression and location"),
        ("SERVICE SPACE", config.get("industry", "Local Service"), "Clean environment and clear process"),
        ("WHY VISIT", config.get("main_offer", "Core offer"), "Key message for first-time visitors"),
    ]
    palettes = [
        ((17, 24, 39), (56, 189, 248), (248, 250, 252)),
        ((20, 83, 45), (250, 204, 21), (240, 253, 244)),
        ((88, 28, 135), (45, 212, 191), (250, 245, 255)),
    ]
    out = []
    for idx in range(count):
        path = IMAGE_DIR / f"demo_{idx + 1}.png"
        bg, accent, panel = palettes[idx % len(palettes)]
        label, title, subtitle = cards[idx % len(cards)]
        img = Image.new("RGB", (1080, 1920), color=bg)
        draw = ImageDraw.Draw(img)
        font_label = font_for_size(42)
        font_title = font_for_size(88)
        font_subtitle = font_for_size(48)
        font_small = font_for_size(34)

        draw.rectangle((0, 0, 1080, 1920), fill=bg)
        draw.ellipse((-220, -160, 520, 560), fill=tuple(min(255, c + 38) for c in bg))
        draw.ellipse((680, 1180, 1320, 2020), fill=tuple(max(0, c - 18) for c in bg))
        draw.rounded_rectangle((86, 190, 994, 1600), radius=58, fill=panel)
        draw.rounded_rectangle((136, 250, 944, 1020), radius=42, fill=(232, 238, 245))
        draw.rounded_rectangle((178, 300, 902, 970), radius=34, outline=accent, width=8)
        for line in range(5):
            y = 1110 + line * 70
            draw.rounded_rectangle((154, y, 926 - line * 38, y + 26), radius=13, fill=(205, 213, 224))
        draw.rounded_rectangle((136, 1350, 944, 1460), radius=32, fill=accent)
        draw.text((158, 1390), label, fill=(15, 23, 42), font=font_label)
        draw.text((150, 1060), wrap_text(title, 10), fill=(15, 23, 42), font=font_title, spacing=20)
        draw.text((150, 1500), wrap_text(subtitle, 18), fill=(71, 85, 105), font=font_small, spacing=10)
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


def render_gif_preview(plan: dict, assets: list[dict]) -> None:
    frames = []
    frame_duration_ms = 1200
    width, height = get_canvas_size(plan)
    layout = get_layout(width, height)
    style = get_visual_style(plan)
    accent = hex_to_rgb(style["accent"])
    for idx, scene in enumerate(plan["scenes"]):
        asset = assets[idx % len(assets)]["file"] if assets else ""
        img_path = ASSETS_DIR / asset
        base = crop_cover(Image.open(img_path).convert("RGB"), width, height)

        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        odraw.rectangle((0, 0, width, int(height * 0.24)), fill=(7, 12, 20, 118))
        odraw.rectangle((0, int(height * 0.58), width, height), fill=(7, 12, 20, 178))
        odraw.ellipse((-60, -80, int(width * 0.55), int(height * 0.28)), fill=(*accent, 34))
        odraw.ellipse((int(width * 0.70), int(height * 0.66), width + 110, height + 110), fill=(52, 211, 153, 24))
        base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(base)

        font_brand = font_for_size(15)
        font_title = font_for_size(layout["title_font"])
        font_caption = font_for_size(layout["caption_font"])

        brand_x = layout["brand_left"]
        brand_y = layout["brand_top"]
        draw.rectangle((brand_x, brand_y, brand_x + 4, brand_y + 28), fill=accent)
        draw.text((brand_x + 14, brand_y + 2), f"{plan['shop_name']} / {plan['industry']}", fill=(255, 255, 255), font=font_brand)
        draw.multiline_text(
            (layout["brand_left"], layout["title_top"]),
            wrap_by_pixel(plan["cover_text"], font_title, layout["caption_width"]),
            fill=(255, 255, 255),
            font=font_title,
            spacing=6,
            stroke_width=3,
            stroke_fill=(8, 13, 20),
        )
        caption_x = layout["brand_left"]
        caption_y = height - layout["caption_bottom"] - 128
        draw.rectangle((caption_x, caption_y - 18, width - layout["brand_left"], caption_y - 14), fill=accent)
        draw.multiline_text(
            (caption_x, caption_y),
            wrap_by_pixel(scene["caption"], font_caption, layout["caption_width"]),
            fill=(255, 255, 255),
            font=font_caption,
            spacing=8,
            stroke_width=2,
            stroke_fill=(8, 13, 20),
        )
        frames.append(base)
    if frames:
        frames[0].save(
            OUTPUT_DIR / "preview.gif",
            save_all=True,
            append_images=frames[1:],
            duration=frame_duration_ms,
            loop=0,
            optimize=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a local-business short-video workflow draft.")
    parser.add_argument("--config", default=str(ROOT / "config.json"))
    parser.add_argument("--demo-assets", action="store_true", help="Create placeholder images if no images exist.")
    parser.add_argument("--refresh-demo-assets", action="store_true", help="Regenerate demo_*.png without touching real images.")
    parser.add_argument("--clean", action="store_true", help="Clear generated output before running.")
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

    plan = generate_plan(config, images)
    compliance = check_compliance(config, plan)
    assets = copy_assets(images)
    write_srt(plan)
    write_voiceover_files(plan)
    write_html(plan, assets)
    write_markdown(plan, compliance)
    render_gif_preview(plan, assets)
    (OUTPUT_DIR / "plan.json").write_text(
        json.dumps({"plan": plan, "compliance": compliance}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Generated: {OUTPUT_DIR}")
    print("Key outputs:")
    print(f"- {OUTPUT_DIR / 'video_plan.md'}")
    print(f"- {OUTPUT_DIR / 'preview.gif'}")
    print(f"- {OUTPUT_DIR / 'preview.html'}")
    print(f"- {OUTPUT_DIR / 'plan.json'}")
    print(f"- {OUTPUT_DIR / 'voiceover.txt'}")


if __name__ == "__main__":
    main()
