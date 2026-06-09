# 项目状态快照 (STATE.md)

> 单一事实来源。任何 AI 动手前先读这里，收工前必更新这里。

**最后更新**: 2026-06-10 by Codex (Dev)
## 一句话定位

一个面向个体商户和下沉市场的**短视频自动生成平台**：客户上传素材（图片/视频/文字/录音），
平台自动产出一条带配音+字幕的完整宣传视频，并支持在网页上**手动微调成品**（改脚本、换语气、调字幕、替换镜头），无需每次都和 AI 重新沟通整条视频。先做网页，后做软件。

## 当前阶段

**Stage 1 / M1 复审中**：已有本地 POC（run_workflow.py），
现在已接入 `llm_generate.py` 的 Provider 抽象。默认 `mock` provider 可离线生成 analysis/script/scenes；
`claude` provider 已按 review 修复改为 Anthropic tool_use 强制结构化输出，等待 Claude 复审与真实 key 验证。

## 已有资产 (POC)

- `run_workflow.py`：核心流水线（模板生成 plan.json + Pillow 渲染 GIF/HTML 预览）
- `llm_generate.py`：M1 生成模块（Provider 抽象、mock/claude、结构校验、代码分配时间轴）
- `output/plan.json`：结构化剪辑计划（系统的核心数据契约雏形）
- `output/voiceover_segments/`：逐场景 TTS 文本（待接 CosyVoice）
- 医疗风险词预警、多画幅 (9:16/16:9/1:1)、多视觉风格

## 当前焦点

**T-002 M1 已 DONE（Claude 复审通过 2026-06-10）。** LLM 生成模块完成：Provider 抽象（mock/claude）、
Anthropic tool_use 强制结构化输出、retryable 重试边界、手写校验、代码分配时间轴、向后兼容旧 plan。
三条验证基线全过、新增重试测试到位。

**等你拍板下一步**：(1) 是否提交 GitHub；(2) 启动 M2（接 CosyVoice TTS）还是 M3（FFmpeg/Remotion 出 MP4）。
注：M3 的渲染引擎选型（D-02）尚未定，需 Claude 先做一次 2026 生态调研再开工。

## 关键约束

- **定位是「半自动 + 人工品控」**，对外可叫「全自动」，但内部架构按半自动设计（素材匹配、发布两步不强求全自动）。
- **医疗仅作自家试验田**，商业化优先非医疗赛道（餐饮/零售/维修/教育/生活服务）。
- 核心架构思想不变：**AI 产出结构化剪辑计划，渲染工具执行**，不让 AI 操作剪辑软件。

## 里程碑路线 (MVP 闭环)

- [x] M1: 接真 LLM —— 输入信息 → 分析卖点/痛点/角度 → 生成脚本/分镜/口播/标题（结构化输出）✅ DONE
- [ ] M2: 接 TTS —— voiceover_segments 真正出声 (CosyVoice)
- [ ] M3: FFmpeg/Remotion 出真 MP4（替代 GIF/HTML 预览）
- [ ] M4: 素材打标签 + 自动匹配（产品护城河，最大瓶颈）
- [ ] M5: 审核 Web 界面 + 增量重渲染（改一段只重跑一段）
- [ ] M6: 多平台版本输出（重渲染）
- [ ] M7: 发布 + 数据回流（能手动先手动）

**M1→M2→M3 串起来 = 最小可用闭环，可拿自家店验证。**
