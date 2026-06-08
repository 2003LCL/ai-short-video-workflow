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


def load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
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
      width: 360px;
      height: 640px;
      position: relative;
      overflow: hidden;
      background: #0f172a;
    }}
    .photo {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: cover;
      transform: scale(1.06);
      transition: transform 1000ms ease;
      filter: saturate(1.04) contrast(1.02);
    }}
    .shade {{
      position: absolute;
      inset: 0;
      background: linear-gradient(180deg, rgba(0,0,0,.22), rgba(0,0,0,.08) 42%, rgba(0,0,0,.72));
    }}
    .brand {{
      position: absolute;
      top: 28px;
      left: 24px;
      right: 24px;
      font-size: 16px;
      font-weight: 700;
      text-shadow: 0 2px 8px rgba(0,0,0,.35);
    }}
    .caption {{
      position: absolute;
      left: 24px;
      right: 24px;
      bottom: 92px;
      font-size: 31px;
      line-height: 1.22;
      font-weight: 800;
      text-shadow: 0 3px 14px rgba(0,0,0,.8);
    }}
    .meta {{
      position: absolute;
      left: 24px;
      right: 24px;
      bottom: 34px;
      font-size: 14px;
      line-height: 1.35;
      color: rgba(255,255,255,.82);
      text-shadow: 0 2px 8px rgba(0,0,0,.7);
    }}
    .progress {{
      position: absolute;
      left: 0;
      bottom: 0;
      height: 5px;
      background: #38bdf8;
      width: 0;
    }}
  </style>
</head>
<body>
  <div class="stage" id="stage">
    <img class="photo" id="photo" alt="">
    <div class="shade"></div>
    <div class="brand" id="brand"></div>
    <div class="caption" id="caption"></div>
    <div class="meta" id="meta"></div>
    <div class="progress" id="progress"></div>
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
    const caption = document.getElementById('caption');
    const meta = document.getElementById('meta');
    const progress = document.getElementById('progress');
    let started = performance.now();
    let active = -1;
    brand.textContent = plan.shop_name + ' · ' + plan.industry;
    meta.textContent = plan.topic + ' / ' + plan.platform;

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
        photo.style.transform = scene.effect.includes('out') ? 'scale(1.02)' : 'scale(1.14)';
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


def render_gif_preview(plan: dict, assets: list[dict]) -> None:
    frames = []
    frame_duration_ms = 900
    width, height = 360, 640
    for idx, scene in enumerate(plan["scenes"]):
        asset = assets[idx % len(assets)]["file"] if assets else ""
        img_path = ASSETS_DIR / asset
        base = Image.open(img_path).convert("RGB")
        base = crop_cover(base, width, height)
        draw = ImageDraw.Draw(base)
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        odraw.rectangle((0, 0, width, 120), fill=(0, 0, 0, 72))
        odraw.rectangle((0, 390, width, height), fill=(0, 0, 0, 150))
        base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(base)
        font_brand, font_caption, font_meta = load_fonts()
        draw.text((22, 28), f"{plan['shop_name']} · {plan['industry']}", fill=(255, 255, 255), font=font_brand)
        draw.multiline_text(
            (22, 430),
            wrap_by_pixel(scene["caption"], font_caption, 315),
            fill=(255, 255, 255),
            font=font_caption,
            spacing=8,
        )
        draw.text((22, 585), f"{scene['start']}-{scene['start'] + scene['duration']}s / {plan['platform']}", fill=(220, 232, 240), font=font_meta)
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a local-business short-video workflow draft.")
    parser.add_argument("--config", default=str(ROOT / "config.json"))
    parser.add_argument("--demo-assets", action="store_true", help="Create placeholder images if no images exist.")
    parser.add_argument("--clean", action="store_true", help="Clear generated output before running.")
    args = parser.parse_args()

    if args.clean and OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    ensure_dirs()
    config_path = Path(args.config)
    config = load_config(config_path)
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
