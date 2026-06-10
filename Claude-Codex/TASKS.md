# 任务看板 (TASKS.md)

> 状态：TODO（待认领） / DOING（进行中） / REVIEW（待审查） / DONE（已完成） / BLOCKED（受阻）
> 规则：Codex 认领后改 DOING，完成改 REVIEW；Claude 审过改 DONE，不过退回 DOING。

## 进行中 / 待办

### T-004 MP4 渲染模块 (M3)
- **状态**: TODO（规格就绪，待 Codex 认领改 DOING）
- **负责**: Claude 出规格 → Codex 实现 → Claude 审查
- **目标**: plan.json + 配音 mp3 + 图片 → 带配音/字幕/运镜的 `output/video.mp4`，作为主交付物（GIF/HTML 保留为轻量预览）。
- **硬要求**: 按 `scene.voiceover_audio.audio_duration` 拉长画面时长（`effective = max(duration, audio_dur + 0.6s 留白)`），配音绝不被切断。复用现有运镜/叠层逻辑，不重写、不改契约（填 v1 已预埋的 `renders[]`）。
- **依赖**: moviepy + imageio-ffmpeg（ADR-012 已批准）。失败必须降级，不阻断其他产物。
- **施工图**: `CONTRACTS/T-004_MP4_render_spec.md`（验收标准在文末）。

## 已完成

### T-003 TTS 配音模块 (M2)
- **状态**: DONE（功能 + 健壮性两轮复审均通过，Claude 2026-06-10）
- **负责**: Codex 实现 → Claude 审查
- **健壮性返修复审**: edge 生成 3 个 mp3 后跑 aliyun(全失败，不带 --clean) → mp3 仍保留、plan.json audio 退化为 aliyun/segments=0 但不删文件；新增「失败不破坏已有产物」测试通过。修复目标达成。
- **遗留给 M3 的已知前提**: 语音真实时长 ≠ 画面 duration（scene2 配音 8.4s > 画面 8s）。M3 渲染需按 audio_duration 微调画面节奏。
- **产物**: `tts_generate.py`（含临时目录原子替换）、`tests/test_tts_generate.py`、接入 `run_workflow.py`、edge-tts 依赖。
- **施工图**: `CONTRACTS/T-003_TTS_spec.md`；返修单 `CONTRACTS/T-003_review_fixes.md`

### T-002 LLM 生成模块 (M1)
- **状态**: DONE（Claude 复审通过 2026-06-10）
- **负责**: Codex 实现 → Claude 审查
- **产物**: `llm_generate.py`（Provider 抽象 mock/claude + tool_use 结构化输出 + retryable 重试 + 手写校验）、`tests/test_llm_generate.py`、接入 `run_workflow.py`。
- **复审结论**: 4 个必改项 + 顺手优化全部修对；亲自重跑三条基线 + 检视新增测试，无虚报。Anthropic tool_use 请求格式核对正确。
- **施工图**: `CONTRACTS/T-002_LLM_generate_spec.md`；**复审修改单**: `CONTRACTS/T-002_review_fixes.md`

### T-001 设计核心数据契约 v1
- **状态**: DONE
- **负责**: Claude
- **产物**: `CONTRACTS/video_project.schema.json`（VideoProject v1，向后兼容旧 plan.json，覆盖分析/生成/渲染/审核/数据回流全链路字段）。

### T-000 搭建双 AI 协作底座
- **状态**: DONE
- **负责**: Claude
- **说明**: 建立 Claude-Codex/ 目录，含 PROTOCOL / STATE / TASKS / HANDOFF / DECISIONS / CONTRACTS。
