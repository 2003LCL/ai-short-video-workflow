# 任务看板 (TASKS.md)

> 状态：TODO（待认领） / DOING（进行中） / REVIEW（待审查） / DONE（已完成） / BLOCKED（受阻）
> 规则：Codex 认领后改 DOING，完成改 REVIEW；Claude 审过改 DONE，不过退回 DOING。

## 进行中 / 待办

### 文案质量专项 (ADR-011 闭环后回炉)
- **状态**: TODO（PM 出规格中）
- **说明**: 闭环 M1→M3 已通，按 ADR-011 回炉打磨文案质量。用户明确「文案才是视频好坏的关键」。重点是真接 Claude provider 的 prompt 工程（选题角度/钩子/转化引导），把 M1 的 mock 占位文案换成高质量生成。

## 已完成

### T-005 M3 复审收尾 cleanup
- **状态**: DONE（Claude 直接修复并验证 2026-06-11）
- **负责**: Claude（机械小修，Reviewer 直接改）
- **修了什么**:
  1. `run_workflow.py` GIF 函数三行中文注释乱码 `?????` → 恢复正常中文注释（grep `????` 已归零）。
  2. `renders[]` 双份实现 → run_workflow 的 `make_render_record` 改为复用 `render_mp4.make_render_entry` 的薄包装，逻辑收敛一处；顺手删掉因此不再使用的 `datetime` import。
- **验证**: run_workflow.py 解析通过；三套单测全过；`--skip-tts --skip-mp4` 跑通；plan.json 的 renders[] 字段经 make_render_entry 后仍贴合契约。

### T-004 MP4 渲染模块 (M3)
- **状态**: DONE（Claude 复审通过 2026-06-11）
- **负责**: Codex 实现 → Claude 审查
- **复审怎么做的（亲自跑，无虚报）**: 三套单测全过；`--skip-tts --skip-mp4` 与 `--skip-tts` 基线正常；默认全开真实生成 `output/video.mp4`，ffmpeg 探针确认 720×1280 / 30fps / H.264+AAC / 25.00s。
- **命门验证通过**: scene2 配音 8.412s → 画面被拉到 9.012s(=audio+0.6)，配音不被切断；scene1/3 配音短于画面保持设计 8s；`scenes[].start/duration` 仍是原始整数未被回写；总时长 25.012s 与成片一致。
- **契约符合**: plan.json 顶层 `renders[]` 三条（preview_html/preview_gif/mp4）字段贴合 schema；MP4 失败只 warning 不阻断；video.mp4 已被 .gitignore 忽略（git check-ignore 确认）。
- **GIF 未退化**: 运镜/叠层抽成 `make_render_context`/`draw_scene_overlay`/`render_scene_frames_with_context` 共享函数，GIF 与 MP4 共用同一套 `_ken_burns_crop` + overlay，GIF 仍按原 12fps/每段固定帧数/缩回小预览输出。
- **MoviePy 锁定**: requirements `moviepy>=1.0.3,<2.0`，代码用 1.x API（ImageSequenceClip/set_audio/set_start/write_videofile），一致。
- **遗留**: 两处非阻塞质量问题转 T-005 cleanup（注释乱码 + renders[] 双份实现）。
- **施工图**: `CONTRACTS/T-004_MP4_render_spec.md`

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
