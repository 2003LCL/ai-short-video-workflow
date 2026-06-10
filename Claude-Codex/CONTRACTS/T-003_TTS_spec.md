# 任务规格 T-003：TTS 配音模块 (M2)

> 这是给 Codex 的施工图。开工前必须先读：PROTOCOL.md → STATE.md →
> HANDOFF.md(最近一条) → DECISIONS.md(ADR-009、ADR-010) →
> CONTRACTS/video_project.schema.json(看新增的 scene.voiceover_audio 和顶层 audio 字段) → 本文件。
> 涉及改接口契约的，停下来在 HANDOFF.md 提问，不要擅自改。

## 目标

把每个 scene 的 `voiceover` 口播文本，通过 TTS 合成为音频文件，并把音频信息回填进数据结构。
本阶段用 **免费的 edge-tts** 先把"出声闭环"跑通，听 AI 中文口播效果。
同时按 M1 的设计经验做 **Provider 抽象**，为将来切商用 TTS(阿里云 CosyVoice 等)预留接口。

## 范围边界（明确不做什么）

- **只做"文本 → 音频文件"**。不做"把配音合进视频/MP4"——那是 M3。
- 不改 LLM 生成逻辑(llm_generate.py)、不改渲染逻辑(GIF/HTML)。
- 不实现商用 provider 的真实调用，但要把 `AliyunProvider` 的类骨架和清晰的 NotImplemented 占位留好(注释写明将来怎么接)。
- 不引入除 edge-tts 外的新依赖。

## 依赖（已批准，见 ADR-010）

- 新增 `edge-tts`（免费、无需 key、调微软 Neural 在线语音）。加入 requirements.txt。
- edge-tts 是 **异步** 库(基于 asyncio)，注意用 `asyncio.run()` 包装，不要把 async 泄漏到主流程。
- **离线/无网络兜底**：edge-tts 需要联网。若网络不可用或合成失败，要清晰报错并允许主流程跳过配音继续(用 `--skip-tts` 或 provider=none)，不能让整个 run_workflow 崩掉。

## 具体要求

### 1. 新建模块 `tts_generate.py`（独立模块，不要塞进 run_workflow.py）
   职责：输入 scenes(含 voiceover 文本) + 配置 → 为每段生成音频文件 → 返回回填信息。

### 2. Provider 抽象（沿用 M1 思路）
   - 定义 `TTSProvider` 抽象基类，核心方法如 `synthesize(text: str, out_path: Path) -> float`(返回音频时长秒)。
   - `EdgeTTSProvider`：用 edge-tts 实现，默认中文女声音色 `zh-CN-XiaoxiaoNeural`(可配)。支持语速/音量微调参数(edge-tts 的 rate/volume)。
   - `AliyunProvider`：**只留骨架**，方法体 raise NotImplementedError 并注释说明将来接百炼 CosyVoice 的方式。
   - `NoneProvider` 或等效机制：跳过配音(用于无网络/不想配音时)。
   - 通过 `--tts-provider edge|aliyun|none` 切换，默认 edge。

### 3. 主函数 `generate_voiceover_audio(scenes, config, out_dir, provider_name)`
   - 为每个 scene 生成音频，存到 `output/voiceover_audio/scene_01.mp3` 这样的命名(与现有 voiceover_segments 的 scene_NN 命名对齐)。
   - 回填：每个 scene 加 `voiceover_audio` 对象(file/audio_duration/provider/voice，**严格按 schema 字段名**)。
   - 返回顶层 `audio` 汇总对象(provider/voice/segments/total_audio_duration，可选 full_track)。
   - 单段失败要记录但不中断其他段(收集失败列表，最后报告)。

### 4. 接进 run_workflow.py
   - 加 `--tts-provider edge|aliyun|none`(默认 edge) 和 `--skip-tts`(等价 none)。
   - 在生成 plan、写完 voiceover 文本之后调用 TTS 模块。
   - 把回填后的 scenes 和 audio 汇总写进 plan.json(plan.json 顶层加 `audio` 字段；scene 内已带 voiceover_audio)。
   - **保持向后兼容**：不配音时(none/失败)，现有所有产物(GIF/HTML/srt/plan.json)仍要正常产出，只是没有音频字段或音频字段为空。

### 5. 产物落盘位置
   - 音频存 `output/voiceover_audio/`(注意：.gitignore 已忽略 *.mp3/*.wav，音频不会进 git，符合预期)。
   - 若需要，可在 .gitignore 显式加一行 `output/voiceover_audio/` 注释说明(可选)。

## 验收标准（Claude 复审会逐条核对）

- [ ] `python run_workflow.py --demo-assets --clean --tts-provider edge` 能联网生成每段 mp3，plan.json 里 scene 带 voiceover_audio、顶层有 audio 汇总。
- [ ] `python run_workflow.py --demo-assets --clean --skip-tts`(或 --tts-provider none) 不配音也能跑通全部其他产物，不崩。
- [ ] 无网络/edge-tts 失败时报错清晰，且能降级继续(不让整个流程崩)。
- [ ] `tts_generate.py` 可独立 import 测试。
- [ ] 回填字段严格符合 CONTRACTS/video_project.schema.json 的 voiceover_audio / audio 定义。
- [ ] AliyunProvider 骨架在被选中时给出清晰的"未实现，请用 edge"提示，不是莫名 traceback。
- [ ] 有针对 TTS 模块的测试：用一个 `FakeProvider`(不真联网，写个假音频文件/返回固定时长)验证回填结构、命名、汇总统计、单段失败处理。**测试不要依赖真实网络**。
- [ ] audio_duration 是真实读取的音频时长(edge-tts 输出 mp3，可用 mutagen 读时长——但 mutagen 是新依赖，未批准；改用 edge-tts 自带的 WordBoundary/SubMaker 时间信息，或估算并注明)。**这条有坑，见下方提示，拿不准就在 HANDOFF 提问。**
- [ ] 代码风格与现有模块(llm_generate.py / run_workflow.py)一致。

## 交付时（Codex 收工动作）

1. 更新 STATE.md(M2 状态)、TASKS.md(T-003 → REVIEW)。
2. HANDOFF.md 顶部追加交接段，**重点说明：音频时长是怎么拿到的(见下方坑)、Provider 抽象怎么设计的、失败降级怎么处理的**。
3. 若过程中做了依赖/架构选择，记进 DECISIONS.md。

## 已知坑提示

- **音频时长怎么拿(最大的坑)**：edge-tts 生成 mp3，但标准库没法直接读 mp3 时长。三个选项，按优先级：
  1. 用 edge-tts 的 `Communicate` + `SubMaker`，它会回传每个词的时间边界(WordBoundary)，最后一个边界的结束时间≈音频时长。**优先用这个，零新依赖**。
  2. 若方案1拿不到，可生成 wav 格式(标准库 `wave` 模块能读 wav 时长)。但 edge-tts 默认输出 mp3，要确认它能否直出 wav。
  3. 实在不行，先按"文本字数 / 每秒中文字数(约 4-5 字/秒)"估算，字段里注明是估算值，并在 HANDOFF 写明留待 M3 优化。
  **拿不准用哪个方案，先在 HANDOFF 提问，不要硬猜。**
- edge-tts 异步：用 asyncio.run 包好，别把 async 扩散到主流程。
- Windows + 中文：路径用 pathlib，文本编码 utf-8，音色名是 ASCII 不用担心。
- edge-tts 走的是微软非公开接口，**仅用于试效果，不是商用方案**(ADR-009)。代码注释里点明这一点，别让将来的人误以为它能正经商用。
