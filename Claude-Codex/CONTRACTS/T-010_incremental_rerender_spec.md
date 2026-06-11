# T-010 任务规格：M5 第二期 — 增量重渲染（改完文案重新出片）

> 这是 Codex 的施工图。开工前按 PROTOCOL 顺序读：PROTOCOL → STATE → HANDOFF 最近 1-2 段 → DECISIONS(ADR-002/008/015) → schema → 本文件。
> 验收标准在文末。**不改 CONTRACTS 数据契约**（只读写已有 plan.json 字段，复用 edited 标记）。

## 目标（一句话）

让用户在网页编辑器改完文案后，**点一个「重新生成视频」按钮**，系统只对改过的分镜重新配音（省掉未改段的 TTS），然后整条重新合成带新文案/新配音/新字幕的 MP4，网页上等待并看到结果。这让「改文案 → 看到新视频」闭环。

## 关键设计共识（PM 已和用户确认，务必照此实现，不要自行扩大）

读过现有渲染管线后定的务实方案：
- **配音：真增量** —— 只对 `edited=true` 的 scene 重新生成 mp3，未改段保留上次的 mp3 和 audio_duration。这是「改一段只重跑一段」最实在、收益最大的部分（TTS 最慢、要联网、可能失败）。
- **画面 + MP4：整体重渲染** —— 画面帧用 Pillow 实时画，本来就快；MP4 是单个视频文件，无论改没改都必须整条重新编码。所以**不做画面帧增量缓存**（投入产出比差，PM 已和用户确认放弃）。
- 触发方式：网页按钮，**同步等待**（第一版不做后台任务队列；点了就在网页转圈等它跑完返回，类似已有保存的交互）。

## 为什么是这个范围

- T-008 改文案时已把改过的 scene 置 `edited=true`（顶层 scenes 和 legacy plan.scenes 双镜像都置）。第二期正是消费这个标记。
- ADR-002 半自动定位：人改文案 → 机器重出片，是核心闭环。
- 第一版同步等待够用（本地单用户）；后台队列/多用户留到上线阶段。

## 核心工程点 1：增量配音（tts_generate.py）

现状：`generate_voiceover_audio()` 是**全量重配**——所有段配一遍、写 `voiceover_audio.tmp/`、整体替换 `voiceover_audio/`。它不支持「只配某几段、保留其他段旧 mp3」。

要新增**增量配音能力**，二选一（Codex 判断哪种更清晰，在 HANDOFF 说明）：
- 方案 A：给 `generate_voiceover_audio` 加可选参数 `only_orders: set[int] | None`（None = 全量，保持现有行为不变；给定集合 = 只重配这些 order 的段）。
- 方案 B：新增独立函数 `regenerate_voiceover_audio(scenes, config, out_dir, only_orders, ...)`。

增量配音的正确行为（务必守住）：
- 只对 `only_orders` 里的段调 TTS 生成新 mp3；其他段**不调 TTS**、保留 `voiceover_audio/scene_NN.mp3` 原文件不动。
- 只更新被重配段在 scene 上的 `voiceover_audio`（file/audio_duration/provider/voice）；未改段的 `voiceover_audio` 保持原值。
- **健壮性（沿用 T-003 教训）**：增量配音失败的段，不能破坏该段或其他段已有的 mp3。不要无条件 rmtree 整个 voiceover_audio 目录。建议：新 mp3 先写临时文件，成功后再替换该段正式文件；某段失败只 warning、保留其旧 mp3，不影响其他段。
- 顶层 `audio` 汇总（segments / total_audio_duration）要按「全部现存段」重新算正确，不能只算增量段。

## 核心工程点 2：重渲染编排（建议放 web_app.py 或新增 rerender 模块）

点「重新生成」后的流程：
1. 读 `output/plan.json`。
2. 找出 `edited=true` 的 scene 的 order 集合（从顶层 scenes 取）。
3. 若没有任何 edited 段：可以直接重渲 MP4（文案可能改了但 TTS 文本没变），或提示「没有需要更新配音的改动」——Codex 选其一，倾向仍重渲 MP4（因为字幕/画面文案可能变了）。
4. 增量配音：对 edited 段重新生成 mp3（用上面的增量能力）；TTS provider 用项目当时的（edge 默认）。
5. 重新算时间轴并整条合成 MP4：复用 `render_mp4.render_mp4` + run_workflow 的 `render_scene_frames`（画面整体重画）。MP4 内部已按 `effective = max(duration, audio_dur+0.6)` 处理时长，配音改了时长变了它会自适应。
6. 同步文本产物：复用 write_srt / write_voiceover_files / write_markdown（字幕/口播文本跟新文案一致）。
7. 成功后：把已消费的 `edited` 标记**清回 false**（顶层 + legacy 双镜像），表示「这版已重新生成过」；更新 plan.json 的 audio / renders / scenes 的 voiceover_audio；原子写回 plan.json。
8. 整个过程任何一步失败：不破坏已有的 video.mp4 / 旧 mp3 / plan.json（失败降级，沿用 T-003/T-004 的 .tmp + 原子替换思路）。

## 核心工程点 3：网页交互（web_app.py + 前端）

- 新增 API：`POST /api/project/rerender`（无 body 或可带选项），执行上面的重渲染编排，返回结果（成功/失败、生成了哪些产物、耗时、哪些段被重配）。
- 前端：编辑器加「重新生成视频」按钮。点击后：
  - 按钮禁用、显示「正在重新生成，可能需要一两分钟…（配音要联网、视频在合成）」的进行中状态。
  - **同步等待**后端返回（fetch 不设过短超时；渲染可能几十秒到一两分钟）。
  - 成功后提示「视频已更新」，并给出 video.mp4 路径 / 可播放链接（能在网页里 `<video>` 播放最好，但第一版给路径+提示也行）。
  - 失败给清晰中文错误，且明确告知「旧视频未被破坏」。
- 仍绑 127.0.0.1、debug 关闭。

## 边界 / 不做
- 不做后台任务队列、不做进度条百分比（同步等待 + 转圈即可）。
- 不做画面帧增量缓存（已确认放弃）。
- 不改数据契约 / schema。
- 不动 LLM 文案生成、不重新调用 Claude（重渲染只用已存在的文案，不重新生成文案）。
- 不做多用户。

## 测试要求（tests/test_web_app.py 或新增 test）
- 增量配音：构造 3 段、标记第 2 段 edited，调增量配音（用 fake/monkeypatch TTS provider，不真联网），断言只有第 2 段被重新合成、第 1/3 段 mp3 文件未被触碰、audio 汇总正确。
- 增量配音失败：强制某段失败，断言其旧 mp3 仍在、其他段不受影响。
- rerender API：用 fake provider + 跳过真实 MP4（或 monkeypatch render_mp4）跑通编排，断言 edited 标记被清回 false、plan.json 字段更新、失败时旧产物不被破坏。
- 现有四套单测全部回归通过。

## 验收标准（Codex 自检通过后改 T-010 → REVIEW）
1. 四套单测 + 新增增量/重渲染测试全过。
2. 端到端：先 `run_workflow --demo-assets --clean`（生成带配音的 MP4）→ 起 web_app → 改某一段字幕/口播并保存（该段 edited=true）→ 点「重新生成视频」→ 只有该段重新配音、video.mp4 整条更新、plan.json 的 edited 清回 false、audio/renders 更新。Codex 在 HANDOFF 记录实测（含真实联网 edge TTS 跑通情况，或说明用 --skip 验证了哪部分）。
3. 未改段的 mp3 文件确实没被重新生成（可对比文件修改时间 / mock TTS 调用次数）。
4. 任一步失败时，旧 video.mp4 和旧 mp3 不被破坏（失败降级）。
5. 网页按钮交互正常：进行中状态、成功提示、失败清晰报错。
6. 仍绑 127.0.0.1、debug off；`.\scripts\check_project.ps1` 通过。

## 已知坑提示
- 增量配音别无条件 rmtree 整个 voiceover_audio 目录（会删掉未改段的好 mp3）——这是 T-003 踩过的坑，务必只动要重配的段。
- MP4 合成耗时较长（几十秒~分钟级），前端 fetch 不要设短超时，后端也别被某个默认超时掐断。
- 真实 edge TTS 要联网，离线/无网时增量配音会失败——要降级（保留旧 mp3、warning），不能崩。
- `edited` 标记清回 false 必须在 MP4 成功之后做；若 MP4 失败，edited 应保留（表示还没成功重渲），便于下次重试。
- 重渲染会刷新 output 下产物，注意别和 check_project 的 smoke 冲突（参考之前 --clean 文件锁教训，验证编排注意顺序）。
