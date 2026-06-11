# 交接说明 (HANDOFF.md)

> 最新的交接写在最上面。任何 AI 接手前先读最近 1-2 段，就能跟上思路。
> 固定格式见 PROTOCOL.md。

## [2026-06-11 #16] Claude(PM) → Codex
**改动**: M3 代码已提交 GitHub；完成 T-005 cleanup；启动文案质量专项 T-006，产出规格 + 升级契约 + 记 ADR-013。
**涉及文件**:
- 提交并推送 M3 代码（commit d971896：render_mp4.py 等）与 T-005 cleanup（commit 7c529e1）
- 新增 `CONTRACTS/T-006_copy_quality_spec.md`（文案专项施工图，Codex 必读，验收标准在文末）
- 升级 `CONTRACTS/video_project.schema.json`（config 加可选 `copy_style` 枚举，向后兼容）
- 更新 `DECISIONS.md`（+ADR-013：文案专项=prompt 工程 + 两套风格 + copy_style 契约升级 + mock 一并升级 + 真实生成验收）
- 更新 `TASKS.md`（T-005→DONE、文案专项具体化为 T-006 就绪）、`STATE.md`、本段
**T-005 cleanup 我直接修了（机械小修，经用户确认走快路径）**: ① 恢复 run_workflow.py GIF 函数三行损坏的中文注释；② renders[] 构造统一走 `render_mp4.make_render_entry`，删除重复的 `make_render_record` 实现体与不再使用的 datetime import。已验证：三套单测过、解析过、--skip-tts --skip-mp4 跑通、renders[] 字段仍贴合契约。
**为什么这么设计 T-006**:
- **抓真正的瓶颈**：读了 llm_generate.py，当前 `build_claude_instruction` 的 prompt 极单薄（只讲 JSON 结构约束，零文案创作指导）——这才是文案平庸的根因，不是模型不行。专项核心 = 重写这个 prompt，不是改架构。
- **两套风格按 industry 自动判定**：用户选了「两套可切换」。医疗/教育→professional_trust，餐饮/零售/维修等下沉生活服务→punchy_local；config 显式 copy_style 覆盖。降低客户门槛，也咬合 ADR-002 半自动定位与 M5 编辑器可改文案。
- **mock 一并升级**：用户决策，让离线 demo 也展示像样文案，不只在花 key 时才看得到效果。
- **契约只加可选字段**：copy_style 是可选枚举，旧 config 无此字段走自动判定，向后兼容，PM 主动升级并记 ADR-013，Codex 不要再动契约。
- **验收靠真实生成 + 人判**：文案好坏无法自动化测试。自动化只测结构合法/风格注入/两套确实不同；真实 Claude 生成对比留到复审环节由用户主观判断（用户决策）。
**接口变化**: 升级 schema（config.copy_style 可选字段，ADR-013）。Codex 按新字段消费即可，不要再改契约。
**验证情况**: 仅文档/契约/规格 + T-005 机械修复（已验证如上）。M1/M2/M3 主流程未动仍可运行。
**下一步建议**: Codex 读 PROTOCOL→STATE→本段→ADR-011/013→schema(copy_style)→T-006 spec，重写 `build_claude_instruction` + 实现 copy_style 解析 + 升级 mock 两套风格 + 补测试，完成后改 T-006 为 REVIEW 并在此写交接段。
**给 Codex 的话**: 这个任务的价值全在 prompt 写得好不好，别只满足于「结构跑通」。真实 Claude 别用真 key 跑（避免 key 进仓库/日志），把真实生成验证留给复审。copy_style 自动判定的 industry 关键词列表写成常量、测试覆盖边界。

## [2026-06-11 #15] Claude(Reviewer) → 你(人类)
**改动**: 复审 T-004 / M3，**通过，T-004 → DONE**。最小可用闭环 M1→M2→M3 跑通，能出真 MP4 成片。两处非阻塞质量问题转 T-005 cleanup。
**涉及文件**: 仅更新协作文档（TASKS.md T-004→DONE + 新增 T-005 cleanup、STATE.md、本段）。代码未改。
**复审怎么做的（亲自跑，无虚报；用 bundled python 3.12，环境已装 moviepy 1.0.3 / numpy 2.3.5）**:
- 三套单测全过：`test_render_mp4` / `test_llm_generate` / `test_tts_generate`。
- 基线：`--skip-tts --skip-mp4`、`--skip-tts` 均正常，skip 时不出 video.mp4。
- 默认全开真实生成 `output/video.mp4`；用 imageio-ffmpeg 自带 ffmpeg 探针确认：**720×1280 / 30fps / H.264(High) + AAC 44.1k stereo / Duration 25.00s**。
- **命门（配音不被切断）验证通过**：用 `build_render_timeline` 复算——scene2 配音 8.412s → effective 9.012s(=audio+0.6)，scene1/3 配音短于画面保持 8s；`scenes[].start/duration` 仍是原始整数 8/8/8 未被回写；总时长 25.012s 与成片探针一致。
- 契约：plan.json 顶层 `renders[]` 三条（preview_html/preview_gif/mp4）字段贴合 schema；MP4 失败只 warning（已读代码确认 try/except MP4RenderError 不阻断 plan.json/GIF/HTML）；`git check-ignore output/video.mp4` 确认不进仓库。
- GIF 未退化：运镜/叠层已抽成 `make_render_context`/`draw_scene_overlay`/`render_scene_frames_with_context`，GIF 与 MP4 共用同一套 `_ken_burns_crop`+overlay，GIF 仍走原 12fps/每段固定帧数/缩回小预览。
**为什么通过**: 时长命门、契约符合度、失败降级、GIF 复用四个重点全部经得起跑。MoviePy 锁 `>=1.0.3,<2.0` 与实际 1.x API（ImageSequenceClip/set_audio/set_start/write_videofile）一致。Codex 自报的验证与我亲跑结果吻合，无虚报。
**发现两处非阻塞质量问题（转 T-005 cleanup，不卡里程碑——经你确认）**:
1. `run_workflow.py:959,961,965` GIF 函数三行中文注释损坏成 `?????`（抽取共享函数时编码被破坏）。
2. `renders[]` 构造逻辑双份实现：`run_workflow.py:628 make_render_record` 与 `render_mp4.py:47 make_render_entry` 结构相同，应统一一处避免契约字段变动时漏改。
**接口变化**: 无（CONTRACTS 未动，Codex 正确地只填了已存在的 `renders[]`）。
**下一步建议（等你拍板）**:
1. 是否把 M3 代码（render_mp4.py 等）提交 GitHub。当前工作区有：新增 render_mp4.py / tests/test_render_mp4.py，改动 run_workflow.py / requirements.txt / .gitignore / scripts/*.ps1 + 协作文档。
2. 选下一个里程碑：**M4**（素材打标签+自动匹配，产品护城河、最大瓶颈）还是 **M5**（审核 Web 界面+增量重渲染）。
3. 按 ADR-011，闭环已通，可考虑回炉做「文案质量」专项（真接 Claude provider 的 prompt 打磨）——用户此前明确文案才是视频好坏的关键。
4. T-005 cleanup 可让 Codex 在下次开工时顺手清掉。
**给你的提醒**: 你现在可以直接打开 `output/video.mp4` 看成片效果——这是 M3 的核心目的，确认带配音/字幕/运镜的整条视频是否够用。

## [2026-06-11 #14] Codex(Dev) → Claude(Reviewer)
**改动**: 实现 T-004 / M3 MP4 渲染模块。新增 `render_mp4.py`，把 `plan.json + voiceover_audio mp3 + 图片素材` 合成为 `output/video.mp4`，接入 `run_workflow.py`，并把产物登记进顶层 `renders[]`。T-004 已改为 REVIEW。

**涉及文件**:
- 新增 `render_mp4.py`
- 新增 `tests/test_render_mp4.py`
- 修改 `run_workflow.py`
- 修改 `requirements.txt`（新增 `moviepy>=1.0.3,<2.0`、`imageio-ffmpeg>=0.4.9`）
- 修改 `.gitignore`（显式忽略 `output/video.mp4`）
- 修改 `scripts/run_demo.ps1`（smoke test 加 `--skip-mp4`）
- 修改 `scripts/check_project.ps1`（加入 MP4 render tests）
- 更新 `Claude-Codex/STATE.md`、`Claude-Codex/TASKS.md`、本交接段
- 未修改 `CONTRACTS/`

**为什么这么做**:
- **时长规则**：`render_mp4.py` 用 `effective = max(scene.duration, voiceover_audio.audio_duration + 0.6)` 构建 MP4 专用时间轴，逐段累加 start；不回写 `scenes[].start/duration`。实测默认 demo 的 MP4 从设计 24s 拉到约 25s，避免 scene2 8.412s 口播被 8s 画面切断。
- **复用 GIF 视觉逻辑**：把 `render_gif_preview()` 内的运镜/叠层逻辑抽成 `make_render_context()`、`draw_scene_overlay()`、`render_scene_frames_with_context()`、`render_scene_frames()`。GIF 与 MP4 共用 `_ken_burns_crop` 和同一套 overlay 绘制函数；GIF 仍按原来的 12fps/每段固定帧数/缩回小预览输出。
- **MoviePy API**：实际安装并验证的是 `moviepy 1.0.3`，使用 1.x API：`ImageSequenceClip(frames, fps=fps)`、`AudioFileClip(...).set_start(...)`、`CompositeAudioClip(...).set_duration(...)`、`video_clip.set_audio(...)`、`write_videofile(...)`。帧传入 MoviePy 前转为 `numpy.array(PIL.Image.convert("RGB"))`，因为 1.x 需要数组的 `shape`。
- **失败降级**：`run_workflow.py` 捕获 `MP4RenderError`，只打印 `MP4 warning`，不阻断 GIF/HTML/SRT/plan.json。`render_mp4.py` 先写 `video.tmp.mp4`，成功后 `os.replace` 到 `video.mp4`；失败时删除临时文件，不删旧 `video.mp4`。
- **renders[]**：`run_workflow.py` 写 `preview_html`、`preview_gif`，MP4 成功时追加 `kind:"mp4", file:"video.mp4"`，字段按 schema 已有契约。

**接口变化**: 无。只填充 `renders[]`，没有改 `CONTRACTS/video_project.schema.json`。

**验证情况**:
- 通过：`python tests/test_render_mp4.py`
- 通过：`python tests/test_llm_generate.py`
- 通过：`python tests/test_tts_generate.py`
- 通过：`python run_workflow.py --demo-assets --clean --skip-tts --skip-mp4`
- 通过：`python run_workflow.py --demo-assets --clean --skip-tts`，生成静音 `output/video.mp4`，时长 24s，720x1280 H.264。
- 通过：`python run_workflow.py --demo-assets --clean`，默认 edge TTS + MP4 成功，生成 `output/video.mp4`，ffmpeg 检查有 H.264 视频流 + AAC 音频流，时长约 25s，`plan.json` 的 `renders[]` 含 `preview_html` / `preview_gif` / `mp4`。
- 通过：`.\scripts\check_project.ps1`（内部 smoke 使用 `--skip-tts --skip-mp4`，随后跑 LLM/TTS/MP4 逻辑测试）。
- 注意：验证中曾把读取 `output/plan.json` 和 `run_workflow.py --clean` 并行执行，Windows 文件锁导致一次 `PermissionError`；改为顺序执行后通过。这是验证编排问题，不是代码路径问题。

**下一步建议**: Claude 重点复审三件事：1) `effective` 时间轴是否完全满足“不切配音”；2) GIF 是否确实仍走同一 overlay 逻辑且未退化；3) MoviePy 1.x API 与 requirements 锁定是否一致。若要进一步压缩渲染耗时/内存，可后续再优化为流式写帧，本轮为先打通闭环。

## [2026-06-11 #13] Claude(PM) → Codex
**改动**: 确认 M2 已在 GitHub（无需重复提交）；启动 M3，产出 T-004 MP4 渲染任务规格 + 批准渲染依赖。Codex 可据此开工。
**涉及文件**:
- 新增 `CONTRACTS/T-004_MP4_render_spec.md`（M3 施工图，Codex 必读，验收标准在文末）
- 更新 `DECISIONS.md`（+ADR-012：批准 moviepy + imageio-ffmpeg，定复用现有运镜/叠层、不改契约填 renders[]、失败降级）
- 更新 `TASKS.md`（T-004 → TODO 就绪）、`STATE.md`（焦点转 M3）、本交接段
- 未写任何业务代码，未改 CONTRACTS 的数据契约（schema 未动）
**先核对了 GitHub 状态（用户要求先提交）**: `git fetch` 后 `HEAD == origin/main == 41c18c0`（"M2: 接入 TTS 配音模块"），工作树 clean，0 ahead/0 behind。**M2 上一棒已提交远端，本次无需再推**——已向用户说明。
**为什么这么设计 M3**:
- **落实 ADR-008 不另起炉灶**：MoviePy(MIT) + imageio-ffmpeg(自带 ffmpeg 二进制，Windows 免装) 是这阶段最省事的落地。MoviePy 处理「逐段音频按时间定位 + 静音留白 + 合并音视频」零摩擦。
- **复用而非重写**：要求把 `render_gif_preview` 里已验证的 `_ken_burns_crop` + 叠层绘制抽成 GIF/MP4 共享函数，保证 MP4 与预览视觉一致，符合「不重写可用代码」。
- **绕开版面重调**：MP4 直接用现有 ss 超采样帧（9:16→720×1280），复用全部版面/字体计算，零摩擦达 720p。
- **不升级契约**：v1 契约已预埋顶层 `renders[]`(kind:"mp4")，M3 只填充，省一轮契约 ADR——这是 PM 该判的，不让 Codex 纠结。
- **把那个反复点名的时长坑写成硬要求**：`effective = max(scene.duration, audio_duration + 0.6s 留白)`，画面让步给配音，渲染层自算时间轴**不回写 scenes**。总时长可略超 24s，这是预期行为（配音完整性优先）。
- **沿用 T-003 健壮性教训**：缺依赖/合成失败要 warning 降级不阻断其他产物，且失败不删上次成功的 video.mp4（先写 .tmp 再原子替换）。
**接口变化**: 无。CONTRACTS 未动，Codex 只填已存在的 `renders[]`。
**验证情况**: 仅文档/契约/规格，未写代码。M1/M2 代码未动仍可运行。
**下一步建议**: Codex 读 PROTOCOL→STATE→本段→ADR-008/011/012→schema→T-004 spec，实现 `render_mp4.py` 并接入 `run_workflow.py`，完成后改 T-004 为 REVIEW 并在此写交接段，由 Claude 复审。
**给 Codex 的话**: 施工图是 `CONTRACTS/T-004_MP4_render_spec.md`。MoviePy 1.x/2.x API 有差异（set_audio vs with_audio 等），锁定一个版本、在 requirements.txt 写清下限、在 HANDOFF 写明你用的 API，复审时一并核对。时长对齐那条是这个任务的命门，别让配音被切断。

## [2026-06-10 #12] Claude(Reviewer) → 你(人类)
**改动**: 复审 T-003 健壮性返修，**通过，T-003 彻底 DONE**。M2 里程碑完整收尾。
**涉及文件**: 仅更新协作文档（TASKS.md T-003→DONE、STATE.md、本段）。代码未改。
**复审怎么做的（这次精心编排了验证顺序，吸取上次教训）**:
- TTS 单测通过，含新增的「先成功生成→再全失败→旧文件仍在且内容不变」测试，是真测。
- 按返修单要求的关键顺序验证：edge 生成 3 个 mp3 → 紧接着跑 aliyun(全失败，**不带 --clean**) → 确认 3 个 mp3 **仍保留**、plan.json audio 退化为 aliyun/segments=0 但文件未删。修复目标达成。
- **最后用 edge 收尾跑一次**，让现场 plan.json(audio=edge/segments=3) 与磁盘真 mp3 一致——不再留矛盾现场给用户。
**为什么通过**: 临时目录 + 原子替换的实现正确（segments>0 才替换正式目录，全失败删临时目录保留旧产物），范围没有扩大，只修了这一个点。
**接口变化**: 无。
**下一步建议（等你拍板）**:
1. 是否把 M2(含本次健壮性修复) 提交 GitHub。
2. 启动 M3：FFmpeg/MoviePy 出真 MP4。**M3 规格必须把「按 scene.voiceover_audio.audio_duration 微调画面节奏」写成硬要求**（scene2 配音 8.4s > 画面 8s，不处理配音会被切断）。
3. 文案优化按 ADR-011 推迟到闭环跑通后再回炉，M3 阶段不碰。

## [2026-06-10 #11] Codex(Dev) → Claude(Reviewer)
**改动**: 按 `CONTRACTS/T-003_review_fixes.md` 只修 T-003 一个健壮性问题：失败的 TTS 运行不再清空上一次成功生成的 `output/voiceover_audio/`。T-003 已改回 REVIEW。

**涉及文件**:
- 修改 `tts_generate.py`
- 修改 `tests/test_tts_generate.py`
- 更新 `Claude-Codex/STATE.md`
- 更新 `Claude-Codex/TASKS.md`
- 更新本交接段
- 未修改 `CONTRACTS/`、M1、LLM、渲染逻辑

**为什么这么做**:
- 原逻辑在合成前直接 `rmtree(output/voiceover_audio)`，导致 aliyun 占位/断网等整体失败会删掉旧的好音频。
- 新逻辑先生成到 `output/voiceover_audio.tmp/`。逐段尝试完成后，如果 `segments > 0`，才删除正式 `voiceover_audio/` 并把临时目录移动过去；如果 `segments == 0`，删除临时目录并保留正式目录不动。
- `NoneProvider` 路径仍然直接 return，不碰目录。部分成功时仍按 review 单要求用成功片段替换正式目录。

**接口变化**: 无。

**验证情况**:
- 通过：`python tests/test_tts_generate.py`，新增测试覆盖「先成功生成，再全失败，旧音频文件仍存在且内容不变」。
- 通过：`python run_workflow.py --demo-assets --clean --tts-provider edge`，真实生成 mp3。
- 通过：紧接着运行 `python run_workflow.py --demo-assets --tts-provider aliyun`（不带 `--clean`），aliyun 全失败但 `output/voiceover_audio/scene_01.mp3`、`scene_02.mp3`、`scene_03.mp3` 仍保留；`plan.json` 的 `audio.provider=aliyun`、`segments=0`。
- 通过：`.\scripts\check_project.ps1`。

**下一步建议**: Claude 只复审本次临时目录 + 替换逻辑和新增测试即可。功能层面的 TTS 字段、edge 时长、Provider 抽象上轮已过，本轮没有动。

## [2026-06-10 #10] Claude(Reviewer) → Codex
**改动**: 修正上轮复审的一个疏忽，并指派 T-003 健壮性返修。T-003 退回 DOING。
**自我纠错（重要，留痕）**: 上一段(#9)我说复审跑通五条路径——结论属实，但我**验证命令的编排有疏忽**：把会清空目录的失败用例(aliyun)放在成功用例(edge)之后跑，导致真生成的 3 个 mp3 被最后那条 aliyun 命令清掉，留给用户的现场是空目录、plan.json 停在 aliyun/segments=0。用户当场质疑「目录是空的你怎么通过的」，质疑成立。我已重跑 edge 把真产物补回。教训：验证多 provider 时，会破坏产物的用例必须放最后或隔离目录跑。
**这暴露了代码的真实缺陷（本次返修目标）**: `generate_voiceover_audio` 无条件先 `rmtree` 清空 `voiceover_audio/` 再生成 → 任何整体失败的运行(aliyun占位/断网)都会删掉上次的成功配音且无新产物。对要反复重跑的自动化流水线不可接受。
**涉及文件**:
- 新增 `CONTRACTS/T-003_review_fixes.md`（只修这一个健壮性问题，修法已定：临时目录+原子替换，失败不破坏已有产物）
- 更新 TASKS.md（T-003 → DOING）
**接口变化**: 无，不许动 CONTRACTS。
**用户反馈（务必记住，影响后续所有生成）**: 用户确认「AI 配音效果 OK，音色不是重点」，并明确指出 **真正决定视频好坏的是文案内容质量**。→ 这意味着后续重心应放在 LLM 生成的脚本/卖点/钩子文案质量上，而非配音/渲染的花哨度。M1 的 mock 文案只是占位，真接 Claude provider 时的 prompt 质量、文案打磨是产品核心竞争力。建议后续单开一个「文案质量」专项(选题角度、钩子、转化引导)。
**下一步建议**: Codex 读 `CONTRACTS/T-003_review_fixes.md` 修健壮性问题(含新增「失败不破坏已有产物」测试)，重跑验证基线，T-003 回 REVIEW。Claude 复审这一个点即可。

## [2026-06-10 #9] Claude(Reviewer) → 你(人类)
**改动**: 复审 T-003 M2，**通过，T-003 → DONE**。M2 里程碑完成，AI 中文口播能真正出声了。
**涉及文件**: 仅更新协作文档（TASKS.md T-003→DONE、STATE.md、本段）。代码未改。
**复审怎么做的**（亲自跑五条路径，无虚报）:
- TTS 单测通过（含强制单段失败 → 其他段继续的降级验证）。
- LLM 单测回归通过（M1 没被 M2 改动破坏）。
- `--skip-tts` 跑通，segments=0、不打印音频产物、其他产物正常。
- **真实 edge 联网生成 3 个 mp3**（35-50KB 真音频），plan.json 顶层 audio.provider=edge/segments=3/total=20.386s，三段 scene 的 voiceover_audio 字段严格符合契约，时长用 WordBoundary 真实算出（6.087/8.412/5.887s）。
- aliyun 占位被选中时逐段清晰报错且其他产物照常产出；mp3 经 git check-ignore 确认不会进仓库。
**为什么通过**: 失败降级、音频时长、契约符合度三个 Codex 自己点名要审的点全部经得起跑。Provider 抽象沿用 M1 模式、edge-tts 注释里点明了仅试水非商用。质量稳定。
**接口变化**: 无（CONTRACTS 未动，Codex 正确地只消费了 Claude 上轮升级的字段）。
**发现一个不阻塞的设计前提，已记入 STATE/TASKS 留给 M3**: 语音真实时长 ≠ 画面 duration（scene2 配音 8.412s > 画面 8s）。这是 M2 范围外（M2 只管出声），但 M3 渲染合成时必须按 audio_duration 微调画面节奏，否则配音会被切断。
**下一步建议（等你拍板）**:
1. 是否把 M2 提交 GitHub（当前在本地工作区；音频 mp3 已被 .gitignore 忽略，不会进仓库）。
2. 启动 M3：FFmpeg/MoviePy 出真 MP4（引擎已定 ADR-008）。届时 Claude 写 M3 规格，把上面那个时长对齐问题作为硬要求写进去。
**给你的提醒**: 你现在已经可以亲自去 `output/voiceover_audio/` 听三段 mp3，确认 AI 中文口播效果到底够不够用——这是 M2 的核心目的。

## [2026-06-10 #8] Codex(Dev) → Claude(Reviewer)
**改动**: 实现 T-003 / M2 TTS 配音模块。新增 `tts_generate.py`，把 edge-tts / aliyun / none 做成 Provider 抽象，并接入 `run_workflow.py`。T-003 已从 DOING 改为 REVIEW。

**涉及文件**:
- 新增 `tts_generate.py`
- 新增 `tests/test_tts_generate.py`
- 修改 `run_workflow.py`
- 修改 `requirements.txt`（新增 `edge-tts>=7.0.0`）
- 修改 `.gitignore`（忽略 `output/voiceover_audio/`）
- 修改 `scripts/run_demo.ps1`（demo smoke test 用 `--skip-tts`，避免检查脚本依赖网络）
- 修改 `scripts/check_project.ps1`（加入 TTS 单测）
- 更新 `Claude-Codex/STATE.md`、`Claude-Codex/TASKS.md`、本交接段
- 未修改 `CONTRACTS/`，仅消费 Claude 已升级的 `scene.voiceover_audio` 和顶层 `audio` 字段

**为什么这么做**:
- **Provider 抽象**：`TTSProvider.synthesize(text, out_path) -> float` 返回音频时长，`EdgeTTSProvider` 负责真实试水，`AliyunProvider` 留清晰未实现占位，`NoneProvider` 用于跳过配音。这样 M2 能先跑通免费口播，将来切阿里云 CosyVoice 时只新增真实 provider，不改主流程。
- **失败降级**：`generate_voiceover_audio()` 对单段失败只打印 warning 并继续其他段；edge 包缺失/联网失败/aliyun 未实现都不会阻断 GIF、HTML、SRT、plan.json 等其他产物。`--skip-tts` 等价 `--tts-provider none`，scene 不写 `voiceover_audio`，顶层 `audio` 返回 provider=none、segments=0。
- **音频时长方案**：edge 路径用 `Communicate.stream()` 收集 `WordBoundary` / `SentenceBoundary` metadata，按 `offset + duration` 取最后边界时间，单位按 edge-tts 的 100ns tick 转秒(`/ 10_000_000`)；如果 metadata 缺失，再降级用 `文本非空字符数 / 4.5` 估算。当前真实 edge 验证能拿到边界时长，未走估算。这个点建议 Claude 重点复审。
- **检查脚本稳定性**：`scripts/run_demo.ps1` 改为 `--skip-tts`，因为项目级 smoke test 不应依赖外网；真实 edge 生成通过单独命令验证。

**接口变化**: 没有改 `CONTRACTS/`。运行产物现在会在 plan.json 顶层写 `audio`；edge 成功时每个 scene 写 `voiceover_audio`：`file/audio_duration/provider/voice`，字段名按 `video_project.schema.json`。

**验证情况**:
- 通过：`python tests/test_tts_generate.py`（FakeProvider 验证回填结构、命名、汇总统计、单段失败继续、none provider 跳过）
- 通过：`python tests/test_llm_generate.py`
- 通过：`python run_workflow.py --demo-assets --clean --skip-tts`
- 通过：`python run_workflow.py --demo-assets --clean --tts-provider edge`，真实生成 3 个 mp3：`output/voiceover_audio/scene_01.mp3`、`scene_02.mp3`、`scene_03.mp3`
- 通过：检查 `output/plan.json`，`audio.provider=edge`、`segments=3`、`total_audio_duration=20.386`；三段 scene 均有 `voiceover_audio`，duration 分别约 6.087 / 8.412 / 5.887 秒
- 通过：`.\scripts\check_project.ps1`（脚本内 demo 使用 skip-tts，随后跑 LLM/TTS 单测）
- 已安装到当前 bundled Python 环境：`edge-tts 7.2.8`

**下一步建议**: Claude 复审 `tts_generate.py` 的失败边界、音频时长计算是否可接受、以及 `plan.json` 字段是否严格贴合契约。若对音频时长有更严格要求，建议在 T-003 review 中明确是否允许引入专门读 mp3 时长的依赖；否则 M3 先沿用 edge metadata 时长即可。

## [2026-06-10 #7] Claude(PM) → Codex
**改动**: M1 已提交 GitHub。完成渲染/TTS 选型调研并定案。产出 M2(TTS) 任务规格，升级契约，批准 edge-tts 依赖。Codex 可据此开工。
**涉及文件**:
- 升级 `CONTRACTS/video_project.schema.json`（scene 加 voiceover_audio，顶层加 audio 块）
- 新增 `CONTRACTS/T-003_TTS_spec.md`（M2 施工图，Codex 必读）
- 更新 DECISIONS.md（+ADR-008 渲染引擎、+ADR-009 TTS 选型、+ADR-010 契约升级与依赖批准；关闭 D-02/D-03）
- 更新 TASKS.md（T-003 就绪）、STATE.md（当前焦点 M2）
**为什么这么做**:
- **M2 先用 edge-tts 免费试水**：用户要先零成本听 AI 中文口播效果，再决定是否接付费 TTS。edge-tts 调微软 Neural 语音(剪映同源技术体系)、免费、能被程序调用，是验证效果最快的方式。Provider 抽象为将来切阿里云 CosyVoice 预留(ADR-009)。
- **契约先行(ADR-010)**：配音音频必须在数据结构里有明确落点(scene.voiceover_audio + 顶层 audio)，才能被 M3 渲染消费、M5 编辑器引用。这是 PM 该定的，不让 Codex 擅改契约。
- **强调失败降级**：edge-tts 要联网，规格里要求无网络时能 --skip-tts 降级，不让主流程崩——保证离线也能跑通其他产物。
- **预判最大的坑**：mp3 时长不好读，规格里给了三个方案(优先 edge-tts 的 WordBoundary)，让 Codex 拿不准时在 HANDOFF 提问而不是硬猜。
**接口变化**: 升级了 video_project.schema.json(M2 字段)。这是 PM 主动升级并记入 ADR-010，Codex 按新字段产出即可，不要再改契约。
**验证情况**: 仅文档/契约，未写代码。M1 代码未动，仍可运行。
**下一步建议**: 把 T-003 规格交给 Codex。让它先读 PROTOCOL→STATE→本段→ADR-009/010→schema→T-003 spec，实现 `tts_generate.py`，完成后改 T-003 为 REVIEW 并在此写交接段，由 Claude 复审。
**给 Codex 的话**: 你的施工图是 `CONTRACTS/T-003_TTS_spec.md`。音频时长那个坑(已知坑提示第一条)如果拿不准用哪个方案，先在 HANDOFF 提问，别硬猜。edge-tts 只是试水不是商用，代码注释要点明。

## [2026-06-10 #6] Claude(Reviewer) → 你(人类)
**改动**: 复审 T-002 返修，**通过，T-002 → DONE**。M1 里程碑完成。
**涉及文件**: 仅更新协作文档（TASKS.md T-002→DONE、STATE.md 当前焦点、本段交接）。代码未改动。
**复审怎么做的**:
- 逐条核对 4 个必改项：模型 ID(`claude-sonnet-4-6`)、tool_use 强制结构化输出、retryable 重试边界、死代码清理——全部修对。
- 重点核对了上轮最易错的 Anthropic tool_use 请求格式：endpoint / x-api-key / anthropic-version / tools / tool_choice / 响应取 tool_use.input 均正确，input_schema 贴合 M1 契约。
- 亲自重跑三条基线（单测 / mock 全流程 / 无 key 报错）全过；检视新增的重试测试（FlakyProvider calls==2、BrokenProvider calls==1），是真测不是空壳。
**为什么通过**: 上轮拦的全是「真接 Claude 必炸」的隐患，这轮逐一消除，且没有过度扩大改动范围。代码质量稳定。
**接口变化**: 无（CONTRACTS 未动）。
**未验证项**: 真实 Claude API 调用仍未用真 key 跑过——这是有意保留的，等真要上线时单独做一次非提交式本地验证（避免 key 进仓库/日志）。
**下一步建议（等你拍板）**:
1. 是否提交 GitHub（目前所有改动仅在本地工作区，含 collab→Claude-Codex 重命名、M1 代码）。
2. 下一个里程碑选 M2（CosyVoice TTS）还是 M3（FFmpeg/Remotion 出 MP4）。
3. 若选 M3：渲染引擎选型 D-02 未定，需 Claude 先做一次 2026 生态调研（FFmpeg vs Remotion）再写规格交 Codex。

## [2026-06-10 #5] Codex(Dev) → Claude(Reviewer)
**改动**: 按 `CONTRACTS/T-002_review_fixes.md` 完成 T-002 返修：4 个必改项已逐条处理，顺手优化也已做，T-002 已从 DOING 改回 REVIEW。

**涉及文件**:
- 修改 `llm_generate.py`
- 修改 `tests/test_llm_generate.py`
- 更新 `Claude-Codex/STATE.md`
- 更新 `Claude-Codex/TASKS.md`
- 未修改 `CONTRACTS/` 下任何契约文件

**逐条修复说明**:
- 必改 1：`ClaudeProvider` 默认模型从 `claude-3-5-sonnet-latest` 改为 `claude-sonnet-4-6`，仍保留 `CLAUDE_MODEL` 环境变量覆盖。这样默认路径不再使用过时模型，同时本地/线上可按环境切换模型。
- 必改 2：Claude API 改为 Anthropic Messages tool_use 强制结构化输出，不再从 text block 里抓 JSON。请求 body 当前结构如下：
  ```python
  {
      "model": self.model,
      "max_tokens": 3000,
      "temperature": 0.4,
      "messages": [{"role": "user", "content": instruction}],
      "tools": [video_content_tool_schema()],
      "tool_choice": {"type": "tool", "name": "emit_video_content"},
  }
  ```
  `video_content_tool_schema()` 定义的工具名是 `emit_video_content`，`input_schema` 只覆盖 M1 需要的 `analysis` / `script` / `scenes` 三块；响应解析只接受 `content[]` 中 `type == "tool_use"` 且 `name == "emit_video_content"` 的 block，并直接读取 `input`。这样做的原因是：结构约束交给 Claude tool use，运行时代码继续用现有手写 `validate_generation` 做二次校验，不引入新依赖，也不擅自改变总契约。
- 必改 3：`LLMGenerationError` 增加 `retryable: bool`。Claude HTTP 429、HTTP 5xx、`URLError` 标记为可重试；无 key、HTTP 400/401/其他 4xx 默认不可重试。`generate_video_content()` 现在会把 provider 调用纳入重试循环，只对 `retryable=True` 且未达到最大次数的错误继续重试，避免无 key/认证错误空耗重试。
- 必改 4：删除 `load_schema` 和 `parse_json_object`，同步移除 `Path` import。M1 继续遵循 ADR-007：不新增 `jsonschema` 依赖，`CONTRACTS/video_project.schema.json` 仍作为文档契约，运行时保留手写关键字段校验。
- 顺手优化：`validate_timeline()` 遇到非法 duration 时直接返回当前错误，不再把 duration 置 0 后继续累加，避免后续 start/sum 产生连带噪声。

**额外测试补强**:
- 在 `tests/test_llm_generate.py` 增加默认 Claude 模型断言。
- 增加可重试 provider 错误会重试、不可重试 provider 错误不重试的测试。

**验证情况**:
- 通过：`python tests/test_llm_generate.py`
- 通过：`python run_workflow.py --demo-assets --clean --provider mock`
- 通过预期失败路径：无 `ANTHROPIC_API_KEY` / `CLAUDE_API_KEY` 时运行 `python run_workflow.py --demo-assets --provider claude`，输出 `LLM generation failed: Claude provider requires ANTHROPIC_API_KEY or CLAUDE_API_KEY in the environment.`，进程以失败码退出但不崩溃。

**为什么这么设计**: 本轮没有扩大架构范围，只修真接 Claude 时会炸的边界。tool schema 是从 M1 子契约抽出的最小运行时约束，不把完整项目 schema 变成运行时依赖；provider 异常只暴露 retryable 标志，主流程不需要知道 HTTP 细节；删除文本 JSON fallback 是为了避免“结构化输出”和“文本解析”两套真相并存。

**下一步建议**: Claude 复审时重点核对 Anthropic tool_use body 格式、`input_schema` 是否足够贴合 M1 契约、以及真实 key 下是否需要调整 `anthropic-version` 或模型 ID。若工具调用格式需要修正，建议只改 `video_content_tool_schema()` 和 `ClaudeProvider.generate_json()`，不要改 `CONTRACTS/`。

## [2026-06-10 #4] Claude(Reviewer) → Codex
**改动**: 审查 T-002 M1 实现。亲自跑通单测、mock 全流程、claude 无 key 报错三条路径，结果与 Codex 报告一致（无虚报）。整体方向通过，但发现 4 处「mock 跑得通、真接 Claude 必炸」的问题，**T-002 退回 DOING**。
**涉及文件**:
- 新增 `CONTRACTS/T-002_review_fixes.md`（逐条必改清单，Codex 照此修改）
- 更新 `DECISIONS.md`（+ADR-007：M1 用手写校验、不引入 jsonschema，回应 Codex 的依赖提问）
- 更新 `TASKS.md`（T-002 → DOING）
**审查结论摘要**（详见 review_fixes.md）:
- 🔴 必改1：`ClaudeProvider` 默认模型 `claude-3-5-sonnet-latest` 过时 → 改 `claude-sonnet-4-6`。
- 🔴 必改2：Claude 调用只靠文本抠 JSON，违反规格「工具调用强约束」→ 改用 Anthropic tool use 强制结构化输出。
- 🔴 必改3：重试只覆盖校验失败，未覆盖网络/限流瞬时失败 → 把 provider 调用纳入重试并区分可重试/不可重试。
- 🟡 必改4：`load_schema` 是死代码、`parse_json_object` 改后冗余 → 清理；裁决 M1 保留手写校验（ADR-007）。
- 🟢 顺手：`validate_timeline` 非法 duration 会二次报错刷屏。
**为什么这么判**: mock 模式永远产出合法结构，掩盖了真实 API 路径的脆弱性（错误的模型 ID、文本解析、无网络重试）。审查的价值正是在真钱真 key 烧下去之前拦住这些。代码质量本身不差，问题集中在「还没被真实跑过的 Claude 分支」。
**接口变化**: 未改 CONTRACTS 里的数据契约。新增的是 review 修改单文档。
**验证情况**: 用 bundled python 3.12 跑通三条基线，plan.json 顶层键/analysis/script/scenes/时间轴(0-8/8-16/16-24)/向后兼容 plan 均合法。
**下一步建议**: Codex 读 `CONTRACTS/T-002_review_fixes.md`，逐条修完，重跑三条基线，T-002 改回 REVIEW 并在此写交接段（逐条说明怎么改的）。Claude 复审。
**给 Codex 的话**: 必改2 若对 tool use 请求格式没把握，把你采用的 body 结构写进 HANDOFF，我复审时一并核对。

## [2026-06-10 #3] Codex(Dev) → Claude(PM/Reviewer)
**改动**: 实现 T-002 M1：新增 LLM 生成模块，把 run_workflow 从纯模板生成接到 Provider 抽象，默认 mock 可离线跑通，claude provider 支持 Anthropic API 路径。
**涉及文件**:
- 新增 `llm_generate.py`
- 新增 `tests/test_llm_generate.py`
- 修改 `run_workflow.py`
- 修改 `scripts/check_project.ps1`
- 更新本目录 `STATE.md`、`TASKS.md`、`HANDOFF.md`
- 运行 demo 后更新 `output/plan.json`、`output/preview.*`、`output/voiceover*` 等生成产物
**为什么这么做**:
- **Provider 抽象**：M1 需要同时满足“以后接真 LLM”和“没有 API key 也能稳定测试”。所以把 `LLMProvider` 定为最小接口，只暴露 `generate_json()`，`MockProvider` 保证离线可跑，`ClaudeProvider` 只处理 API 请求和 JSON 解析。这样后续加 DeepSeek/通义/Kimi 时是新增 Provider，不改主流程。
- **校验在模块内部做**：`generate_video_content()` 内部负责调用 provider、校验 analysis/script/scenes、最多 3 次重试。主流程只消费合法结构，避免 `run_workflow.py` 混入 LLM 细节。
- **时间轴由代码分配**：严格按 T-002 要求，LLM/Provider 只产内容，`apply_timeline()` 根据 `duration_seconds` 重新写入 `start/duration`，再用 `validate_timeline()` 检查连续、不重叠、总时长一致。这样避免 LLM 算错秒数污染渲染层。
- **保留旧 plan 兼容**：`legacy_plan_from_generation()` 把新契约的 `script/scenes` 转成旧渲染仍能吃的 `plan` 字段；同时 `output/plan.json` 现在额外写入 `schema_version/input/config/analysis/script/scenes`，便于后续模块逐步迁移。
- **不引入新依赖**：没有使用 `jsonschema`，只手写 M1 需要的关键字段校验。理由是协议要求不引入未批准依赖；如果 Claude 认为需要完整 JSON Schema 校验，应在 DECISIONS.md 记依赖决策后再加。
**接口变化**: 未修改 `CONTRACTS/` 中任何契约。新增代码按 `video_project.schema.json` 的 analysis/script/scenes 子结构产出，并保留旧 `plan` 字段向后兼容。
**验证情况**:
- 通过：`python tests/test_llm_generate.py`
- 通过：`python run_workflow.py --demo-assets --clean --provider mock`
- 通过：`scripts/check_project.ps1`（包含 key 扫描、workflow smoke test、LLM generation tests）
- 通过：`python run_workflow.py --demo-assets --provider claude` 在无 key 时输出清晰错误：`LLM generation failed: Claude provider requires ANTHROPIC_API_KEY or CLAUDE_API_KEY in the environment.`
- 未验证：真实 Claude API 调用（本阶段未使用真实 key）。
**下一步建议**:
1. Claude 审查 `llm_generate.py` 的契约符合度和边界处理。
2. 若要求完整 schema 校验，先在 DECISIONS.md 记录是否允许新增 `jsonschema` 依赖。
3. 如果 ClaudeProvider 真实 API 调用要上线，建议补一条非提交式本地验证流程，避免 key 进入仓库或日志。
4. 当前 `CONTRACTS/` 目录是新文件，尚未提交 GitHub；用户要求本阶段先不提交远程。

## [2026-06-10 #2] Claude(PM) → Codex
**改动**: 定下 3 个待定决策；产出数据契约 v1 和 M1 的完整任务规格。Codex 可据此直接开工。
**涉及文件**:
- 新增 `CONTRACTS/video_project.schema.json`（VideoProject v1 核心契约）
- 新增 `CONTRACTS/T-002_LLM_generate_spec.md`（M1 施工图，Codex 必读）
- 更新 DECISIONS.md（+ADR-005 技术栈、ADR-006 首闭环；关闭 D-04）
- 更新 TASKS.md（T-001 DONE，T-002 规格就绪）、STATE.md（当前焦点）
**为什么这么做**:
- **契约先行**：先把所有模块共用的 JSON 结构定死，Codex 写的 M1 才能和未来的 TTS/渲染/Web 编辑严丝合缝对接。契约里特意预埋了 analysis（卖点/痛点/角度）、scene.edited（增量重渲染）、renders（多平台版本）、metrics（数据回流）这些字段，对应用户的完整愿景，但 M1 只需填 analysis+script+scenes。
- **Provider 抽象 + mock 模式**：强制要求无 API key 也能跑通，是为了让流水线可测试、可演示、不被 key 卡住。这是 M1 最关键的设计点。
- **时间轴由代码算不信 LLM**：避免 LLM 算错 start/duration 导致渲染错位。
**接口变化**: 首次定义 CONTRACTS（video_project.schema.json）。这是基线 v1，Codex 不得擅改；需改要先在 HANDOFF 提问。
**验证情况**: 均为文档/契约，未写代码，现有 POC 未动仍可运行。
**下一步建议**: 把 T-002 规格交给 Codex。让 Codex 先读 PROTOCOL→STATE→schema→T-002 spec，实现 `llm_generate.py`，完成后改 T-002 为 REVIEW 并在此写交接段，由 Claude 审查。
**给 Codex 的话**: 你的施工图是 `CONTRACTS/T-002_LLM_generate_spec.md`，逐条照做，验收标准在文末。有疑问先写进 HANDOFF 不要乱改契约。

## [2026-06-10] Claude(PM) → 你(人类) + 待 Codex
**改动**: 搭好双 AI 协作底座，确立角色分工与交接机制；尚未写任何业务代码。
**涉及文件**:
- 新增 `Claude-Codex/PROTOCOL.md`（协作规则、角色、工作循环）
- 新增 `Claude-Codex/STATE.md`（项目状态快照 + 里程碑路线）
- 新增 `Claude-Codex/TASKS.md`（任务看板）
- 新增 `Claude-Codex/DECISIONS.md`（4 条已定 ADR + 4 条待定项）
- 新增本文件 `Claude-Codex/HANDOFF.md`
**为什么这么做**: 两个 AI 无共享记忆，必须把协作状态全部落盘成固定文件，才能让任意一方接手时「无缝跟上思路」。先立规矩再写代码，避免后面各写各的。
**接口变化**: 暂未定义业务契约（CONTRACTS/ 待 T-001 产出）。
**验证情况**: 仅文档，无需运行验证。现有 POC 未改动，仍可正常运行。
**下一步建议**:
1. 等你确认协作方式 OK（尤其分工和交接格式）。
2. Claude 接着做 T-001：设计核心数据契约 v1，写入 CONTRACTS/。
3. T-001 完成后，Claude 写 T-002 的详细任务规格交给 Codex 实现 LLM 生成模块。
**给 Codex 的话**: 你接手时，先读 PROTOCOL.md → STATE.md → TASKS.md → 本文件 → CONTRACTS/ 下相关契约，再动手。实现完更新 STATE/TASKS 并在此追加交接段。
