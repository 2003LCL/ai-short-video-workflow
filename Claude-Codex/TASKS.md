# 任务看板 (TASKS.md)

> 状态：TODO（待认领） / DOING（进行中） / REVIEW（待审查） / DONE（已完成） / BLOCKED（受阻）
> 规则：Codex 认领后改 DOING，完成改 REVIEW；Claude 审过改 DONE，不过退回 DOING。

## 进行中 / 待办

### T-009 网页编辑器一键启动（Windows 本地）
- **状态**: TODO（规格就绪，待 Codex 认领改 DOING）
- **负责**: Claude 出规格 → Codex 实现 → Claude 审查
- **目标**: 双击 `start_editor.bat` 就能用：自动找 Python → 缺依赖自动装 → 起服务 → 自动开浏览器。消除「敲长命令、记 127.0.0.1」门槛。
- **关键现实**: 依赖目前只在 Codex bundled Python（缓存目录，不稳定，禁止写死路径）；启动脚本要用系统 py/python + 首次自动 pip install，保证可移植。
- **不改业务**: 只加启动便利层 + web_app 自动开浏览器（带 AI_VIDEO_NO_BROWSER 开关）。
- **施工图**: `CONTRACTS/T-009_one_click_launch_spec.md`（验收标准在文末）。

### T-007 离线文案接入 — file provider（次目标已由 PM 完成）
- **状态**: TODO（file provider 部分待 Codex；次目标"中转地址可配置"已由 PM 完成并验证）
- **负责**: Claude 出规格 → Codex 实现 file provider → Claude 审查
- **次目标已完成（PM 直接改）**: `ClaudeProvider` 接入地址改为读 `ANTHROPIC_BASE_URL`（默认官方），中转站 key 已实测打通（用户中转站 nexus 可用）。
- **主目标待 Codex**: `--provider file` 离线人工投喂——生成 output/llm_prompt.txt，喂任意 AI，JSON 存回 response 文件，重跑读回继续流水线。零 key。
- **不改契约**: 只动 llm_generate.py provider 层 + run_workflow 接入。
- **施工图**: `CONTRACTS/T-007_offline_copy_spec.md`（验收标准在文末；注意次目标已完成，Codex 只做 file provider 部分）。

## 已完成

### T-006b 文案 prompt 二次升级（PM 直接改，已真实验证 + 定稿）
- **状态**: DONE（PM 改 + 真实中转 key 双风格验证 + 用户定稿 2026-06-11）
- **负责**: Claude（PM 直接改 prompt 内容，属文案创作能力非工程实现，走快路径）
- **改了什么**: 大改 `build_claude_instruction` 主指令 + 两套风格规则。三轮迭代后定稿的核心规则：①「个体户只给一句话，吸引人的文案是 AI 的活，复述输入=失败」②「创意在于怎么说、不在编造事实」③「先卖体验、优惠最多提一两次垫最后」④**「每个场景必须推进到新信息，禁止换皮重复同一角度，给视频层次」**（治本规则，同时解决餐饮"三句不离钱"和口腔"三句不离未知"）。
- **真实验证（中转 key 双风格）**: 餐饮 punchy（勾馋勾场景、优惠垫后）+ 口腔 trust（钩子→知识点→做法→破除误区→引导，有层次有信息增量），用户认可。
- **定位共识（重要）**: prompt 只把文案稳定顶到「80 分底稿」，LLM 生成有随机性、不可能每条完美。最后 20 分的微调 + 偶尔失手的兜底，靠 M5 人工编辑。再盲调 prompt 边际收益递减——用户已决策接受波动、定稿、把精力转 M5。

### T-008 M5 网页编辑器 第一期 — 文案审改（本地）
- **状态**: DONE（Claude 复审通过 2026-06-11）
- **负责**: Claude 出规格 → Codex 实现 → Claude 审查
- **目标**: 本地网页，让非技术用户打开浏览器就能改 plan.json 的文案（标题/封面/发布文案/各场景字幕和口播）并存回。用户必备需求「人工微调文案」的落地。
- **技术栈**（ADR-015）: Python+Flask 后端（复用现有逻辑、JSON API）+ 原生 HTML/JS 前端，本地运行，API 设计成可替换。
- **复审怎么做的（亲自跑真实服务，无虚报）**: 四套单测全过；真起 `web_app.py` 服务，curl 实测 GET /api/project（返回店名/3场景/字幕正确）、首页 HTML 200、POST /api/project/copy 真实保存。
- **核心红线全部验证通过**: ① POST 故意塞 start/duration=999，落盘仍是原值 0/8（篡改 timeline 无效，从 payload 白名单源头杜绝）② 顶层 scenes 与 legacy plan.scenes 双镜像同步更新 ③ 改过的 scene 置 edited=true、未变的不置 ④ analysis/audio/renders/compliance 等字段原样保留（读现有→只改文案→写回）⑤ captions.srt/voiceover_segments/video_plan.md 文本同步更新 ⑥ 空字段被拒并给字段级中文错误 ⑦ 服务绑 127.0.0.1、debug=False、原子写 plan.json。
- **第一期只做文案审改**：不做重渲染、不做投喂分页（后续期）。
- **不改契约**: 只读写已有 plan.json 字段，schema 未动。
- **施工图**: `CONTRACTS/T-008_web_editor_phase1_spec.md`

### M5 后续期（待 T-008 跑通后规划）
- **状态**: TODO（占位，未出规格）
- **第二期**: 增量重渲染——改一段只重跑该段配音/画面，不整条重跑。
- **第三期**: 离线投喂分页——提示词一键复制 + 主流大模型网页链接，用户自选 AI 复制生成再回来（与 T-007 file provider 复用）。
- **更后期**: 可视化时间轴/所见即所得预览（届时再评估引 React/Remotion，后端 API 不动）。

## 已完成

### T-006 文案质量专项 — prompt 工程 + 两套可切换风格 (M1 回炉)
- **状态**: DONE（Claude 复审通过 2026-06-11；真实 Claude 生成对比因环境无 key 另行验收）
- **负责**: Codex 实现 → Claude 审查
- **复审怎么做的（亲自跑，无虚报；bundled python 3.12）**: 三套单测全过；默认口腔 demo 自动走 professional_trust（结构"信任建立-流程说明-具体卖点-风险克制-温和引导"，文案稳重克制）；临时餐饮 config 自动走 punchy_local（结构"强钩子-痛点直击-卖点具体化-少走弯路-明确行动"，口语强钩子强转化）；两套 mock 文案明显不同且都通过 validate_generation。
- **prompt 是真升级**: `build_claude_instruction` 从纯结构约束扩成 角色设定 + 风格创作准则 + 通用文案准则(钩子/痛点/卖点具体化/caption≠voiceover/转化引导) + 合规禁区 + few-shot，保留 tool_use 强制结构化。
- **复审顺手修复（机械小修）**: `PUNCHY_LOCAL_INDUSTRY_KEYWORDS` 原是死代码（定义未用）→ 接进 `resolve_copy_style` 判定逻辑（显式命中 punchy 赛道再兜底），行为不变、语义更清晰。
- **遗留**: 真实 Claude 生成质量对比未跑（复审环境无 ANTHROPIC_API_KEY，按安全原则不硬塞 key）。这是 T-006 验收核心，需在带 key 环境单独跑，由用户主观判断质量提升。
- **施工图**: `CONTRACTS/T-006_copy_quality_spec.md`

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
