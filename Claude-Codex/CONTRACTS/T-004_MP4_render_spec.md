# T-004 任务规格：FFmpeg/MoviePy 出真 MP4 (M3)

> 这是 Codex 的施工图。开工前先按 PROTOCOL 顺序读：PROTOCOL → STATE → HANDOFF 最近 1-2 段 → DECISIONS(ADR-008/011/012) → schema → 本文件。
> 验收标准在文末。有疑问先写进 HANDOFF 提问，**不要擅改 CONTRACTS/**。

## 目标（一句话）

把现有 plan.json + 配音 mp3 + 图片素材，合成为一条**带配音、带字幕、带运镜**的 MP4 成片，
作为 GIF/HTML 之外的**主交付物**。这是 M1→M2→M3 最小闭环的最后一环。

## 范围边界（务必只做这些，不扩大）

**做：**
- 新增 `render_mp4.py`：消费 `plan.json` 的 scenes + voiceover_audio + assets，输出 `output/video.mp4`。
- 接入 `run_workflow.py`：在 GIF/HTML 之后增加 MP4 合成，并把产物登记进 plan.json 顶层 `renders[]`。
- 新增 `--skip-mp4` 开关（语义对齐现有 `--skip-tts`），以及 MP4 合成失败时的**优雅降级**（不阻断其他产物）。
- 把现有 GIF 帧生成逻辑里「运镜 + 叠层绘制」抽成可复用函数，GIF 和 MP4 共用，**不复制粘贴一份**。

**不做：**
- 不改 `CONTRACTS/video_project.schema.json`（`renders[]` 字段已存在，直接填充即可）。
- 不删除现有 GIF/HTML 预览（它们是轻量快速预览，保留；MP4 是新增的主交付物）。
- 不碰 LLM(M1) / TTS(M2) 逻辑，不动文案质量（ADR-011：文案优化推迟到闭环后）。
- 不引入 ADR-012 未批准的依赖。
- 不重调现有版面常量（`get_layout` 等）——见下「分辨率方案」如何绕开。

## 依赖（已由 ADR-012 批准）

- `moviepy`（MIT）：负责把帧序列 + 音轨合成 MP4，音频合成（逐段定位 + 留白）零摩擦。
- `imageio-ffmpeg`：自带静态 ffmpeg 二进制，**Windows 无需系统安装 ffmpeg**。MoviePy 会自动发现它。
- 这两个加进 `requirements.txt`。numpy 等是它们的传递依赖，随装即可。
- 缺依赖 / ffmpeg 不可用时，MP4 这一步必须 `try/except` 打 warning 后跳过，**不能让整个 workflow 崩**（对齐 TTS 的失败降级）。

## 核心设计点（这几条是这个任务的关键，逐条照做）

### 1. 时长对齐规则（最重要，HANDOFF 反复点名的硬坑）

语音真实时长 ≠ 画面设计时长（实测 scene2 配音 8.412s > 画面 8s）。MP4 渲染**必须按配音时长拉长画面**，否则口播会被切断。

逐场景算「有效时长」：

```
audio_dur   = scene["voiceover_audio"]["audio_duration"]  # 没有该字段时取 0
TAIL_PAD    = 0.6   # 口播说完后留 0.6s 呼吸再切场，定义为模块常量
effective   = max(scene["duration"], audio_dur + TAIL_PAD)
```

- 整条视频总时长 = Σ effective（可能比 config 的 24s 略长，**这是预期行为**，配音完整性优先于精确 24s）。
- 无配音的场景（`--skip-tts` / none provider / 该段 TTS 失败没有 `voiceover_audio`）：`effective = scene["duration"]`，该段静音，MP4 照常出，不报错。
- 渲染层自己算这套「音频感知时间轴」，**不要回写改 scenes 的 start/duration**（那是设计意图，是契约里的整数）。最终 MP4 的真实时长记到 `renders[]`（见第 4 点）。

### 2. 帧生成：复用现有运镜 + 叠层，不重写

现在 `render_gif_preview()` 里有两块成熟逻辑：`_ken_burns_crop()`（运镜裁切）和内部闭包 `draw_overlay()`（品牌条/封面标题/字幕面板/时间码/分段进度条）。

把「给定一个场景 + 一帧进度 prog(0→1) → 产出一帧 PIL 图」的能力抽成共享函数，GIF 和 MP4 都调它。建议形态（具体签名你定，但**逻辑只能有一份**）：

```
def render_scene_frames(plan, assets, scene, idx, n_frames, ss, ...) -> list[Image]:
    # 复用 _ken_burns_crop + 叠层绘制，返回该场景的 n_frames 帧
```

- GIF 路径：每段 `n_frames = max(8, 12)`（保持现有行为），帧率/体积不变——**GIF 视觉质量不许退化**。
- MP4 路径：每段 `n_frames = round(effective * FPS)`，`FPS = 30`（模块常量）。prog 在 n_frames 上 0→1 均匀展开，运镜在被拉长的时长内自然走完。

### 3. 分辨率方案（绕开版面重调）

现有版面常量是为小预览画布（如 9:16 的 360×640）调的，靠 `ss=2` 超采样到 720×1280 再缩回。

**MP4 直接用「缩回之前的超采样帧」**：即 9:16 取 720×1280、16:9 取 1280×720、1:1 取 960×960（= 预览画布 × ss）。这样复用全部版面/字体计算，零重调，且分辨率达到 720p 级别够用。`ss` 可保持 2；若想更清晰可在 MP4 路径用 ss=3（1080 级），但需自测渲染耗时可接受，不强求。

### 4. 音轨合成 + 产物登记

- 用 MoviePy 把每段 `voiceover_audio.file`（相对 `output/` 的 mp3）按其 effective-start 定位拼成整条音轨；段间空缺（无配音段、尾部留白）为静音。
- 帧序列按 FPS 组装为视频流，与音轨合并写出 `output/video.mp4`（H.264 + AAC，`fps=30`）。
- 写完后在 `run_workflow.py` 里把产物登记进 plan.json 顶层 `renders[]`，**严格按契约字段**：
  ```json
  {
    "platform": plan["platform"],
    "aspect_ratio": plan["aspect_ratio"],
    "kind": "mp4",
    "file": "video.mp4",
    "rendered_at": "<ISO8601 时间戳>"
  }
  ```
  GIF/HTML 也建议一并登记进 `renders[]`（kind: `preview_gif` / `preview_html`），让 `renders` 成为所有产物的统一出口。`rendered_at` 用 `datetime.now().isoformat()` 即可。

### 5. 失败降级（对齐 TTS 的健壮性要求）

- moviepy/imageio-ffmpeg 未安装、ffmpeg 调用失败、某段 mp3 读取失败 → 打印清晰 warning，跳过 MP4，**其他产物（GIF/HTML/SRT/plan.json）照常产出且不带半成品 mp4**。
- 若已存在上一次成功的 `video.mp4`，本次失败**不要删它**（沿用 T-003 的教训：失败不破坏已有产物）。建议先写 `video.mp4.tmp` 成功后再原子替换。

## CLI / 接入

- `run_workflow.py` 新增 `--skip-mp4`（默认不跳过，即默认出 MP4）。
- MP4 合成在 GIF/HTML/markdown 之后、写 plan.json 之前进行，使 `renders[]` 能写进最终 plan.json。
- `scripts/check_project.ps1` 的 smoke test 用 `--skip-mp4`（项目级 smoke 不应依赖重渲染耗时），MP4 真实合成由单独命令验证（对齐 T-003 里 smoke 用 --skip-tts 的做法）。

## 测试要求（`tests/test_render_mp4.py`）

不依赖真实 ffmpeg 跑通主路径，重点测**纯逻辑**：
- `effective` 时长规则：audio > duration 时取 audio+pad；无 voiceover_audio 时取 duration；多段累加总时长正确。
- 音频感知时间轴的 start 推导（逐段 effective 累加）。
- `renders[]` 条目结构符合契约字段。
- 失败降级：moviepy 不可用 / 合成抛错时，函数返回明确信号且不抛穿到主流程（可用 fake/monkeypatch）。
- 若可行，补一条「先成功生成 video.mp4 → 再强制失败 → 旧 mp4 仍在」的健壮性测试（对齐 T-003）。

## 验收标准（Codex 自检通过后改 T-004 → REVIEW）

1. `python tests/test_render_mp4.py` 通过；`python tests/test_llm_generate.py`、`python tests/test_tts_generate.py` 回归通过。
2. `python run_workflow.py --demo-assets --clean --skip-mp4` 通过：不出 mp4，其他产物正常，plan.json 的 renders 不含 mp4 条目（或为空）。
3. `python run_workflow.py --demo-assets --clean`（默认 edge TTS + MP4）通过：
   - 真实生成 `output/video.mp4`，能正常播放，**配音不被切断**（重点听 scene2：配音 8.4s，画面应被拉到 ≥9s）。
   - 字幕/品牌条/运镜与 GIF 预览视觉一致。
   - 音画对齐：每段配音从该段画面开始处响起。
   - plan.json 顶层 `renders[]` 含一条 `kind:"mp4"`，字段贴合契约，`file:"video.mp4"`。
4. `python run_workflow.py --demo-assets --clean --skip-tts`（无配音）通过：MP4 仍能出（静音），用设计时长，不报错。
5. `.\scripts\check_project.ps1` 通过（内部 smoke 用 --skip-mp4）。
6. GIF 预览视觉质量未退化（抽帧对比）。
7. `video.mp4` 已加入 `.gitignore`（生成产物不进仓库，对齐 mp3 的处理）。

## 已知坑提示

- MoviePy 2.x 与 1.x API 有差异（如 `set_audio`/`with_audio`、`ImageSequenceClip` 参数）。锁定一个 major 版本并在 `requirements.txt` 写清楚下限，注释说明用的是哪套 API。拿不准就在 HANDOFF 写出你用的版本和调用方式，复审时一并核对。
- mp3 路径在 plan.json 里是相对 `output/` 的（如 `voiceover_audio/scene_01.mp3`），合成时要拼到 `OUTPUT_DIR` 下取绝对路径。
- imageio-ffmpeg 首次运行可能要下载/定位二进制；离线环境跑要给清晰报错并降级，别静默卡住。
- 帧数 × 分辨率 × FPS 会让内存/耗时上升。若一次性持有全部帧内存吃紧，可分段写或用临时帧目录，但别为此牺牲画质；自测耗时记到 HANDOFF。
