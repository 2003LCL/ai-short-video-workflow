# 项目状态快照 (STATE.md)

> 单一事实来源。任何 AI 动手前先读这里，收工前必更新这里。

**最后更新**: 2026-06-11 by Claude (Reviewer)

> M5 网页编辑器第一期（T-008 文案审改）复审通过，DONE。
## 一句话定位

一个面向个体商户和下沉市场的**短视频自动生成平台**：客户上传素材（图片/视频/文字/录音），
平台自动产出一条带配音+字幕的完整宣传视频，并支持在网页上**手动微调成品**（改脚本、换语气、调字幕、替换镜头），无需每次都和 AI 重新沟通整条视频。先做网页，后做软件。

## 当前阶段

**Stage 1 / M3 已 DONE，最小闭环跑通**：已有本地 POC（run_workflow.py），
现在已接入 `llm_generate.py` 的 Provider 抽象和 `tts_generate.py` 的 TTS Provider 抽象。
默认 `mock` LLM 可离线生成 analysis/script/scenes；TTS 默认 edge，可用 `--skip-tts` 降级跳过配音；
M3 已接入 MoviePy MP4 渲染，可用 `--skip-mp4` 跳过成片合成。

## 已有资产 (POC)

- `run_workflow.py`：核心流水线（模板生成 plan.json + Pillow 渲染 GIF/HTML 预览）
- `llm_generate.py`：M1 生成模块（Provider 抽象、mock/claude、结构校验、代码分配时间轴）
- `output/plan.json`：结构化剪辑计划（系统的核心数据契约雏形）
- `output/voiceover_segments/`：逐场景 TTS 文本（待接 CosyVoice）
- 医疗风险词预警、多画幅 (9:16/16:9/1:1)、多视觉风格

## 当前焦点

**M1/M2/M3 全部 DONE 并提交 GitHub。最小可用闭环 M1→M2→M3 已跑通**（店铺信息→真实文案→配音→带字幕/运镜的 720p MP4）。

**T-006 + T-006b 文案专项 DONE 并提交（07b1d8e）**：`build_claude_instruction` 经三轮真实迭代定稿为带货文案 prompt（个体户场景化、创意在角度不在编造、先卖体验优惠垫后、每场景必须推进新信息禁止换皮重复）；两套风格 punchy/trust 用中转 key 真实验证均有层次。中转地址已可配置（`ANTHROPIC_BASE_URL`，修了 403）。**共识：prompt 只到 80 分底稿，剩余微调靠 M5 人工兜底。**

**当前焦点：M5 网页编辑器第一期（T-008）复审通过，DONE（Claude 2026-06-11）。** `web_app.py`：Flask 本地后端（绑 127.0.0.1、debug off）+ 原生 HTML/JS 页面，读 `output/plan.json`、编辑整体文案和分镜字幕/口播、只存允许的文案字段。复审亲起真实服务 curl 实测通过：篡改 start/duration 无效、顶层+legacy 双 scenes 镜像同步、改过的 scene 置 edited=true、analysis/audio/renders 原样保留、captions.srt/voiceover/video_plan.md 文本同步、空字段被拒。
M5 后续期（占位）：第二期增量重渲染、第三期投喂分页、更后期可视化时间轴。

**等你拍板下一步**：T-008 代码（web_app.py 等）待提交 GitHub。之后可选：M5 第二期（增量重渲染）/ 第三期（投喂分页，与 T-007 file provider 复用）/ T-007 file provider / M4。

**T-007 离线 file provider**：次目标(中转地址可配置)已由 PM 完成；主目标(`--provider file` 人工投喂)仍待 Codex，与 M5 第三期投喂分页可复用。施工图 `CONTRACTS/T-007_offline_copy_spec.md`，ADR-014。

**M4(素材打标签+自动匹配) 仍暂放。**

**⚠️ 安全**：用户在对话里贴过中转站 key（已用完即弃、未落盘未提交），建议用户去后台吊销换新。

**已落实的硬前提**：语音真实时长 ≠ 画面 duration。M3 已按 `effective = max(scene.duration, audio_duration + 0.6s 留白)` 拉长画面，渲染层自算时间轴不回写 scenes，配音不被切断（实测 scene2 8.412s→9.012s）。

## 关键约束

- **定位是「半自动 + 人工品控」**，对外可叫「全自动」，但内部架构按半自动设计（素材匹配、发布两步不强求全自动）。
- **医疗仅作自家试验田**，商业化优先非医疗赛道（餐饮/零售/维修/教育/生活服务）。
- 核心架构思想不变：**AI 产出结构化剪辑计划，渲染工具执行**，不让 AI 操作剪辑软件。

## 里程碑路线 (MVP 闭环)

- [x] M1: 接真 LLM —— 输入信息 → 分析卖点/痛点/角度 → 生成脚本/分镜/口播/标题（结构化输出）✅ DONE
- [x] M2: 接 TTS —— voiceover_segments 真正出声（edge-tts 试水）✅ DONE（已提交 GitHub 41c18c0）
- [x] M3: FFmpeg/Remotion 出真 MP4（替代 GIF/HTML 预览）✅ DONE（复审通过，720p H.264+AAC，配音不切断）
- [ ] M4: 素材打标签 + 自动匹配（产品护城河，最大瓶颈）
- [ ] M5: 审核 Web 界面 + 增量重渲染（改一段只重跑一段）← **进行中：第一期 T-008 文案审改已 DONE（复审通过），后续期做增量重渲染**
- [ ] M6: 多平台版本输出（重渲染）
- [ ] M7: 发布 + 数据回流（能手动先手动）

**M1→M2→M3 串起来 = 最小可用闭环，可拿自家店验证。**
