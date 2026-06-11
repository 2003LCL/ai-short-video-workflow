# 项目状态快照 (STATE.md)

> 单一事实来源。任何 AI 动手前先读这里，收工前必更新这里。

**最后更新**: 2026-06-11 by Claude (PM)
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

**M1/M2/M3 全部 DONE 并提交 GitHub（M1: 7ca5cbf，M2: 41c18c0，M3 文档: e5c6511）。** 渲染引擎(ADR-008)、TTS(ADR-009) 选型已定。

**T-004 / M3 复审通过，DONE（Claude 2026-06-11）。** FFmpeg/MoviePy 出真 MP4：默认全开真实生成 `output/video.mp4`（720×1280 / 30fps / H.264+AAC / 25s），登记进 `plan.json` 顶层 `renders[]`。
**最小可用闭环 M1→M2→M3 已跑通**，可拿自家店素材验证整条管道。

**T-005 cleanup 已 DONE（注释乱码 + renders[] 双份实现已修，7c529e1）。**

**等你拍板下一步**：M3 代码已提交 GitHub（d971896），T-005 cleanup 已 DONE 并提交（7c529e1）。

**当前焦点：T-006 文案质量专项已出规格，等 Codex 认领实现。** 按 ADR-011/013 回炉打磨文案——重写 `build_claude_instruction` 的 prompt（当前太单薄，是文案平庸的根因），加两套可切换风格(punchy_local/professional_trust，按 industry 自动判定)，mock 一并升级。契约已加 config.copy_style（ADR-013，向后兼容）。施工图 `CONTRACTS/T-006_copy_quality_spec.md`。

**M4(素材打标签+自动匹配) / M5(审核Web界面+增量重渲染) 暂放一放**，先把文案质量这个核心竞争力打磨好。

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
- [ ] M5: 审核 Web 界面 + 增量重渲染（改一段只重跑一段）
- [ ] M6: 多平台版本输出（重渲染）
- [ ] M7: 发布 + 数据回流（能手动先手动）

**M1→M2→M3 串起来 = 最小可用闭环，可拿自家店验证。**
