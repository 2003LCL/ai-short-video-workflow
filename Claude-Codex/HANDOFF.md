# 交接说明 (HANDOFF.md)

> 最新的交接写在最上面。任何 AI 接手前先读最近 1-2 段，就能跟上思路。
> 固定格式见 PROTOCOL.md。

## [2026-06-11 #24] Claude(PM) → Codex
**改动**: T-008 复审通过后，出 T-009 一键启动规格（用户反馈「打开方式太复杂」）。
**涉及文件**:
- 新增 `CONTRACTS/T-009_one_click_launch_spec.md`（一键启动施工图）
- 更新 `TASKS.md`（T-009 → TODO 就绪）、本段
- 未写业务代码，未改契约
**为什么做 T-009（用户原话「这个打开方式也太复杂了」）**:
- T-008 启动要手敲长命令 + 手动开浏览器，店主级用户门槛太高。目标：双击 `start_editor.bat` 自动找 Python→装依赖→起服务→开浏览器。
- **关键现实（已 PM 查证，写进规格）**: 依赖目前只装在 Codex bundled Python（`.cache\codex-runtimes\...`，是工具缓存目录，不稳定，**禁止写死该路径**）；系统有 `py.exe` 但大概率没装项目依赖。所以一键启动必须用系统 py/python + 首次自动 `pip install -r requirements.txt`，保证可移植、换机器能跑。
- web_app.py 加自动开浏览器（threading.Timer 延迟触发，带 `AI_VIDEO_NO_BROWSER=1` 开关避免测试弹窗）。
**关于上线（已向用户解释，留痕给后续）**: 用户问「怎么上线推广 / 127.0.0.1 会不会变」。已说明：现在是本地自测版（127.0.0.1 只有本机能开、不会变但不是给客户的）；上线要经 ①功能补全(网页端上传→生成→改→出片) ②多用户+账号+数据库 ③部署到云服务器+域名+ICP备案 ④商业化。**最大工程难点**：视频渲染(MoviePy/ffmpeg)极吃服务器资源，多人同时生成需任务队列+按需扩容，是上线阶段主要成本。用户当前选择「先做一键启动」自用顺手，上线是后话。
**接口变化**: 无。
**验证情况**: 仅文档/规格。
**下一步建议**: Codex 读 PROTOCOL→STATE→本段→ADR-015→T-009 spec，实现 `start_editor.bat` + web_app.py 自动开浏览器增强 + README 说明，完成后改 T-009 为 REVIEW 并在此写交接段。**务必本机实跑 .bat 验证**（脚本难做单测），把实测情况写进 HANDOFF。
**给 Codex 的话**: 别写死 bundled Python 路径（会变）。.bat 开头 `chcp 65001` 防中文乱码、结尾 pause 防窗口一闪而过。自动开浏览器要 Timer 延迟、且 run 之前注册，否则浏览器先开连不上。

## [2026-06-11 #23] Claude(Reviewer) → 你(人类)
**改动**: 复审 T-008 / M5 网页编辑器第一期，**通过，T-008 → DONE**。M5 第一期「人工微调文案」落地，是用户必备需求。
**涉及文件**: 仅更新协作文档（TASKS.md T-008→DONE、STATE.md、本段）。代码未改。
**复审怎么做的（亲起真实服务 curl 实测，不只跑 test_client，无虚报；bundled python 3.12 + flask 3.1.3）**:
- 四套单测全过：test_web_app / test_llm_generate / test_tts_generate / test_render_mp4。
- 真起 `web_app.py`（端口 5051），curl 实测：GET /api/project 返回店名/3场景/字幕正确；GET / 首页 HTML 200。
- POST /api/project/copy 真实保存，故意在 payload 里塞 `start:999/duration:999` → 落盘 plan.json 仍是原值 0/8（**篡改 timeline 无效**，从 payload 字段白名单源头杜绝）。
- 双 scenes 镜像：顶层 `scenes` 与 legacy `plan.scenes` 都同步更新为新文案；改过的 scene `edited=true`、文案未变的不置位。
- 字段保护：analysis/audio/renders/compliance 原样保留（后端「读现有 plan.json→只改文案→写回」，前端无法整体覆盖）。
- 文本同步：captions.srt / voiceover_segments/scene_01.txt / video_plan.md 都同步更新为新文案（复用 run_workflow.write_srt/write_voiceover_files/write_markdown，临时切 OUTPUT_DIR 后 finally 还原）。
- 空字段提交被拒，返回字段级中文错误；服务绑 127.0.0.1、debug=False、plan.json 用 tempfile+replace 原子写。
**为什么通过**: Codex 自己点名要审的四条红线（字段白名单、双镜像同步、edited、start/duration 不被改）全部经得起真实服务验证；契约未动（schema 未改，只读写已有字段）；安全（仅本机、无 debug）；自报验证与我亲跑结果吻合，无虚报。代码质量高，校验/错误处理/原子写都到位。
**接口变化**: 无（CONTRACTS 未动）。新增本地服务端点 GET /api/project、POST /api/project/copy，属应用层非数据契约。
**下一步建议（等你拍板）**:
1. 是否把 T-008 代码（web_app.py、tests/test_web_app.py、README/requirements/check_project 改动）提交 GitHub。
2. 选下一步：**M5 第二期**（增量重渲染——改完一段只重跑该段配音/画面）/ **M5 第三期**（投喂分页，与 T-007 file provider 复用）/ **T-007 file provider**（离线零 key 投喂）/ **M4**（素材打标签+自动匹配）。
3. 你现在就可以本地起 `web_app.py` 打开 http://127.0.0.1:5000 试用文案审改——这是你反复强调的「人工微调文案」必备需求的第一个可用版本。
**给你的提醒**: 第一期改完文案后，配音/视频不会自动更新（页面已明确提示）。「改一段只重跑一段」是第二期增量重渲染的事。

## [2026-06-11 #22] Codex(Dev) -> Claude(Reviewer)
**Change**: Implemented T-008 / M5 web editor phase 1. The local Flask page reads `output/plan.json`, lets the user edit script copy plus scene captions/voiceovers, saves the allowed copy fields back to plan.json, and syncs text sidecar outputs. T-008 is now REVIEW.

**Files touched**:
- Added `web_app.py`
- Added `tests/test_web_app.py`
- Updated `requirements.txt` with `flask>=3.0.0`
- Updated `scripts/check_project.ps1` to run web editor tests
- Updated `README.md` with local editor startup instructions
- Updated `Claude-Codex/STATE.md`, `Claude-Codex/TASKS.md`, and this handoff entry
- Did not modify `CONTRACTS/`

**Why this design**:
- The backend uses a patch-style save: read the existing `plan.json`, update only allowlisted copy fields, then write it back. This avoids letting the browser overwrite the whole project and accidentally drop or mutate `analysis`, `audio`, `renders`, `compliance`, `config`, or `input`.
- The API surface is intentionally small: `GET /api/project` returns a compact copy-editing view; `POST /api/project/copy` accepts only `script.topic`, `script.cover_text`, `script.titles`, `script.post_copy`, `script.bgm_suggestion`, and `scenes[].order/caption/voiceover`. Extra fields such as `start` and `duration` are ignored by construction.
- Save updates both mirrors: top-level `scenes` and legacy `plan.scenes`. Scenes are matched by `order`. If caption or voiceover actually changes, both mirrors get `edited=true`, preserving the future hook for incremental rerendering.
- Text side effects reuse existing workflow functions instead of duplicating logic: `run_workflow.write_srt`, `write_voiceover_files`, and `write_markdown`. They consume the legacy plan, so `project["plan"]` remains the sync source for `captions.srt`, `voiceover.txt`, `voiceover_segments/*.txt`, and `video_plan.md`.
- Phase 1 deliberately does not rerender mp3/GIF/MP4. The page and API success message both tell the user that audio and video must be regenerated before the final media reflects copy edits.
- The server runs with `app.run(host="127.0.0.1", port=5000, debug=False)`. Port can be changed with `AI_VIDEO_WEB_PORT`; it never binds `0.0.0.0`.

**Interface changes**: No CONTRACTS/schema changes. New local service endpoints:
- `GET /api/project` returns `{ok, project}` where project is the copy-editor view.
- `POST /api/project/copy` accepts `{script, scenes}` and saves copy-only updates; success returns the updated editor view plus the audio/video regeneration notice.

**Validation**:
- Passed: `python tests/test_web_app.py`
- Passed: `python tests/test_llm_generate.py`
- Passed: `python tests/test_tts_generate.py`
- Passed: `python tests/test_render_mp4.py`
- Passed: `./scripts/check_project.ps1` including key scan, demo smoke, LLM/TTS/MP4/web tests.
- Passed service smoke: started `python web_app.py`, then `http://127.0.0.1:5000/api/project` returned project data.
- Passed browser smoke: opened `http://127.0.0.1:5000`; the page rendered with Chinese title/header and Chinese field labels for topic, cover copy, title options, post copy, BGM suggestion, scene caption, and scene voiceover. 3 scenes rendered, and the status said the project was loaded.
- Note: `./scripts/check_project.ps1` refreshes generated timestamps in `output/plan.json`; timestamps were restored. A remaining final-newline diff in `output/plan.json` is only a smoke-test artifact, not a business change.

**Next step recommendation**:
1. Review `web_app.py` for allowlisted fields, mirror sync, `edited=true`, `start/duration` ignore behavior, and preservation of `analysis/audio/renders/compliance`.
2. During review, send a POST payload containing fake `start/duration` values and verify both scene mirrors keep their original timeline.
3. If accepted, mark T-008 DONE. The next spec should cover phase 2: regenerate only edited scenes' audio/video.

## [2026-06-11 #21] Claude(PM) → Codex
**改动**: 文案 prompt 已定稿提交（07b1d8e）。启动 M5 网页编辑器，定技术栈(ADR-015) + 出第一期 T-008 文案审改规格。
**涉及文件**:
- 新增 `CONTRACTS/T-008_web_editor_phase1_spec.md`（第一期施工图，验收标准在文末）
- 更新 `DECISIONS.md`（+ADR-015：M5 技术栈 Python+Flask 后端 / 原生 HTML+JS 前端 / 分期 / API 可替换；关闭 ADR-005 挂起的前端栈评估）
- 更新 `TASKS.md`（M5 拆成 T-008 第一期 + 后续期占位）、`STATE.md`（焦点转 M5）、本段
- 未写业务代码，未改契约
**M5 决策怎么定的（用户拍板）**:
- 用户定：第一期**只做文案审改** + **本地网页**；技术栈听 PM 分析后选了 **Python 后端 + 原生前端**。
- PM 分析（写进 ADR-015）：核心逻辑(LLM/TTS/渲染/plan.json)全在 Python，第一期文案审改本质是 读 plan.json→表单→写回，后端直接调现有代码；上 React 后端仍得 Python，等于为一个改文字的表单平白加一套 Node 链路。React 价值在复杂交互(时间轴/实时预览)，第一期用不到，留到后期且因 **API 设计成可替换**不影响后端。落实了 ADR-005 当初挂起的「M5 再评估前端栈」。
- 框架选 Flask（轻量、Python web 事实标准、做 JSON API 省事）。
**T-008 范围红线（Codex 务必守住）**:
- 只做文案审改：读写 plan.json 的文案字段（script.* + scenes[].caption/voiceover），不做重渲染、不做投喂分页（后续期）。
- **保存副作用**：改完要同步 captions.srt / voiceover 文本 / video_plan.md（复用 run_workflow 的 write_srt/write_voiceover_files/write_markdown）；配音 mp3/MP4 第一期不自动重生成，但前端要提示「配音视频需重新生成」。
- **契约纪律**：不改 schema；只更新允许的文案字段，保留 analysis/audio/renders/compliance 不动；前端不许改 start/duration/timeline；改过的 scene 置 edited=true。
- **安全**：服务绑 127.0.0.1（不绑 0.0.0.0，第一期不对外、避免无鉴权服务暴露）；Flask debug 不开。
- **已知坑**：plan.json 里 `plan.scenes`(legacy) 和顶层 `scenes` 是两份镜像，保存文案两处都要更新，否则重渲染读到旧文案——Codex 看清结构、在 HANDOFF 说明怎么保证一致。
**接口变化**: 无（不动 CONTRACTS）。新增 flask 依赖。
**验证情况**: 仅文档/规格。现有流水线未动。
**下一步建议**: Codex 读 PROTOCOL→STATE→本段→ADR-002/011/015→schema→T-008 spec，实现 `web_app.py`(Flask API + 原生前端页) + `tests/test_web_app.py`，完成后改 T-008 为 REVIEW 并在此写交接段。
**给 Codex 的话**: 这是给店主这种非技术用户用的，界面用中文、字段标签说人话（「这句话的字幕」而非 caption）。先把「能看明白→能改→能存回→字幕口播同步」这条跑通，别扩到重渲染。保存逻辑要「读现有 plan.json→只改文案字段→写回」，别整个覆盖丢字段。

## [2026-06-11 #20] Claude(PM) → 你(人类)
**改动**: 中转地址打通真实生成 + 文案 prompt 二次大改并真实验证 + 把「人工微调文案」归入 M5。代码改动待用户确认定稿后提交。
**涉及文件（已改未提交）**:
- `llm_generate.py`：① `ClaudeProvider` 接入地址可配置（`ANTHROPIC_BASE_URL`，默认官方）② 大改 `build_claude_instruction` 主指令 + 两套风格规则
- `tests/test_llm_generate.py`：更新 prompt 注入断言锚点（随 prompt 改写）
- 协作文档 TASKS/STATE/本段；T-007 spec 状态备注更新
**做了什么、为什么**:
- **修 403（次目标，PM 直接改）**：根因是 `llm_generate.py` 把请求 URL 写死官方端点，中转站 key 打过去被拒。改成读 `ANTHROPIC_BASE_URL`，其余请求格式不动（中转站兼容官方 Messages API）。用户中转站(nexus)实测打通，`--provider claude` 真实生成成功。
- **文案 prompt 二次大改（T-006b，PM 直接改，走快路径）**：首版真实文案用户评「草率、三句不离钱、廉价」。诊断根因=我首版 prompt 太强调「把 offer 翻译成好处」，offer 是"五折"时 AI 一头扎进钱里。大改加了三类规则：①个体户只给一句话、复述输入=失败、吸引人靠 AI ②创意在角度不在编造事实 ③**关键平衡规则：先卖体验(味道/烟火气/场景/情绪)、折扣最多提一两次垫最后当行动理由**。用中转 key 重跑极简餐饮(店名/烧烤/周年庆/五折)：改后 4 场景仅 1 场讲折扣、其余勾馋勾场景，用户认可「思路对了」。
- **为什么 PM 直接改而非走 Codex**：prompt 内容质量本质是文案创作能力非工程实现，且中转 key 已通、"改→真实跑→看效果→再调"由我闭环最快。类似 T-005 Reviewer 直接改的快路径。
- **人工微调归 M5（用户决策）**：用户明确「人工微调文案」是必备需求，prompt 只做 80 分底稿、剩 20 分人工调。归入 M5 网页编辑器，与投喂分页、增量重渲染合为一个"非技术用户能审/改/重生成的网页工作台"。
**接口变化**: 无（未动 CONTRACTS；copy_style 字段上轮已加）。
**验证情况**: 三套单测过；中转 key 真实生成餐饮文案两版（改前/改后）已人工对比。仅餐饮(punchy)验过，trust(口腔/教育)未重验。
**遗留 / 下一步（等你拍板）**:
1. **文案定稿确认**：这版 prompt 你认可即定稿。建议定稿前我用中转 key 补跑一次 trust 风格(口腔)，确认平衡规则没把专业克制风格带歪。
2. **提交 GitHub**：你说过「改完文案一起提交」——确认定稿后，把中转地址 + 文案 prompt + 测试一起提交。
3. **T-007 file provider** 主目标仍可让 Codex 做（离线零 key 备份方案），次目标已完成。
4. **M5 规划**：人工微调 + 投喂分页 + 增量重渲染，优先级已提升。
**⚠️ 安全**: 用户在对话里贴过中转站 key，我已用完即弃、未写入任何文件/未提交。建议用户去中转站后台吊销该 key 换新。

## [2026-06-11 #19] Claude(PM) → Codex
**改动**: 用户真实跑 `--provider claude` 被中转站 403 阻断；用户提出「生成提示词文件喂给任意 AI」的离线方案。据此产出 T-007 规格 + ADR-014。
**涉及文件**:
- 新增 `CONTRACTS/T-007_offline_copy_spec.md`（施工图，验收标准在文末）
- 更新 `DECISIONS.md`（+ADR-014：file provider 人工投喂为主 + 中转地址可配置为辅）
- 更新 `TASKS.md`（T-007 → TODO 就绪）、`STATE.md`、本段
- 未写业务代码，未改契约
**问题根因（已查证）**: `llm_generate.py:127` 把请求 URL 写死成官方 `https://api.anthropic.com/v1/messages`。用户用的是中转站 key，打到官方端点被 403 forbidden。不是代码 bug、不是 key 失效，是接入地址不匹配。
**为什么这么设计 T-007**:
- **主方案 file provider**：用户首选，也最稳——彻底不依赖 key，生成提示词文件人工喂给任意 AI，拿回 JSON 读回流水线。完美咬合 ADR-002 半自动定位，且让 T-006 升级的 prompt 不靠 key 就能见效。
- **顺手修中转**：只把 ClaudeProvider 的接入地址改成可配置（ANTHROPIC_BASE_URL），其余请求格式不动（中转站基本都兼容官方 Messages API 格式）。地址由用户运行时填，Codex 不碰用户 key。
- **两条路互为备份**：能配通中转就自动化，配不通就人工投喂，都不卡产品验证。
- **最容易踩的坑写进规格**：file 模式靠文件落盘衔接两次运行，--clean 会删掉 response——建议 response 文件放 output/ 外规避（参考 T-006 验证时踩过的 --clean 删文件教训）；AI 返回 JSON 常被 markdown 包裹，读取要宽容剥壳。
**PM 已当场验证 prompt 价值**: 我（Claude）在对话里直接用 T-006 升级后的 prompt 手写了一版星河口腔的真实文案给用户看——钩子戳中"怕疼/怕出血/怕被推销"、痛点大白话、全程无疗效承诺、结尾温和引导面诊，明显优于 mock 占位的平铺直叙。证明 T-006 的 prompt 升级方向对，只差一个能跑真实模型的通道，这正是 T-007 要补的。
**接口变化**: 无（不动 CONTRACTS，不动 T-006 prompt 内容）。
**验证情况**: 仅文档/规格。现有 mock/claude/M2/M3 主流程未动仍可运行。
**下一步建议**: Codex 读 PROTOCOL→STATE→本段→ADR-013/014→schema→T-007 spec，实现 FileProvider + ClaudeProvider 地址可配置 + 补测试，完成后改 T-007 为 REVIEW 并在此写交接段。
**给 Codex 的话**: file 模式是重点，把"两次运行靠文件衔接 + --clean 坑 + 友好的人工操作指引"做扎实，让不懂技术的人照着提示也能完成投喂。中转地址那条只做代码+单测，别拿用户真实 key 跑。

## [2026-06-11 #18] Claude(Reviewer) → 你(人类)
**改动**: 复审 T-006 文案专项，**代码层通过，T-006 → DONE**。复审顺手清掉一处死代码。真实 Claude 文案对比因环境无 key 未跑，交回给你。
**涉及文件**: `llm_generate.py`（顺手把死代码常量接进判定逻辑）；协作文档 TASKS/STATE/本段。
**复审怎么做的（亲自跑，无虚报；bundled python 3.12）**:
- 三套单测全过（test_llm_generate 含 copy_style 显式/自动/兜底、透传、mock 两套风格差异、prompt 注入关键词，是真测）。
- 默认口腔 demo 跑通：自动走 `professional_trust`，结构"信任建立-流程说明-具体卖点-风险克制-温和引导"，文案稳重克制。
- 临时餐饮 config 跑通：自动走 `punchy_local`，结构"强钩子-痛点直击-卖点具体化-少走弯路-明确行动"，口语强钩子强转化。两套文案明显不同。
- 重点核对了 prompt 质量本身：`build_claude_instruction` 从原来 12 行纯结构约束，扩成 角色设定(本地商户短视频文案操盘手) + 风格创作准则 + 通用文案准则(首屏钩子/痛点/卖点具体化/caption≠voiceover/转化引导) + 合规禁区 + few-shot，保留 tool_use 强制结构化。**这是真升级，不是只把结构跑通**。
**为什么通过（代码层）**: prompt 工程方向对、质量实打实；copy_style 解析的显式/自动/兜底逻辑正确；两套 mock 风格确实不同且都合法；契约只消费 PM 加的 copy_style 字段未擅改；闭环(TTS/MP4)未受影响。
**复审顺手修复（机械小修，Reviewer 直接改）**: `llm_generate.py:29 PUNCHY_LOCAL_INDUSTRY_KEYWORDS` 原是死代码（定义了从未引用，resolve_copy_style 只查 trust 否则一律 punchy）→ 接进判定逻辑（显式命中 punchy 赛道再兜底），行为不变、语义更清晰。已验证测试仍全过、三类输入 + 显式覆盖行为不变。
**接口变化**: 无（CONTRACTS 未动）。
**唯一遗留，必须交回给你（重要）**: **真实 Claude 文案生成对比没跑成**——复审环境里没有 ANTHROPIC_API_KEY / CLAUDE_API_KEY，按项目安全原则我不会去找或硬塞 key。这恰恰是 T-006 的**验收核心**：mock 文案再像样也只是模板拼接，证明不了升级后的 prompt 对真实 Claude 的效果。Codex 没跑真实 key 是对的（规格要求它别跑，避免 key 进仓库）。
**下一步建议（等你拍板）**:
1. **真实文案验收**：在你有 key 的环境跑 `python run_workflow.py --demo-assets --clean --provider claude`（口腔→trust）和一个餐饮 config（→punchy），各看 1-2 条真实文案，主观判断比 mock 占位是否真的更会"带货"。这是文案专项价值的最终检验。key 用环境变量注入，别写进 config/仓库。
2. 是否把 T-006 代码提交 GitHub。
3. 真实文案满意后，选下一个里程碑：M4(素材打标签+自动匹配，护城河/最大瓶颈) 还是 M5(审核 Web 界面+增量重渲染)。
**给你的提醒**: 你之前明确"文案才是视频好坏的关键"。这一棒把生成文案的 prompt 引擎做厚了，但它到底好不好，得你用真实 key 跑出来亲眼看——这是唯一能下结论的方式。

## [2026-06-11 #17] Codex(Dev) → Claude(Reviewer)
**改动**: 实现 T-006 文案质量专项。升级 `llm_generate.py` 的文案 prompt、copy_style 解析、mock 两套文案风格，并补测试。T-006 已改为 REVIEW。

**涉及文件**:
- 修改 `llm_generate.py`
- 修改 `tests/test_llm_generate.py`
- 更新 `Claude-Codex/STATE.md`
- 更新 `Claude-Codex/TASKS.md`
- 更新本交接段
- 未修改 `CONTRACTS/`，只消费已存在的 `config.copy_style`

**为什么这么做**:
- **prompt 核心升级**：`build_claude_instruction()` 不再只讲 JSON 结构，而是给 Claude 明确角色：本地小商户短视频文案操盘手；加入首屏钩子、痛点、卖点具体化、转化引导、caption/voiceover 区分、合规禁区、few-shot 结构示例，并继续保持 tool_use 强制结构化输出。
- **两套风格**：新增 `punchy_local` 和 `professional_trust`。`punchy_local` 强调前 3 秒钩子、下沉口语、痛点直给、直接 CTA；`professional_trust` 强调专业克制、流程透明、正规咨询、避免夸张承诺。
- **copy_style 解析**：新增模块常量 `PROFESSIONAL_TRUST_INDUSTRY_KEYWORDS` 和 `PUNCHY_LOCAL_INDUSTRY_KEYWORDS`。`resolve_copy_style(config, shop)` 规则是显式 `copy_style` 优先；为空时医疗/口腔/医美/教育/培训/法律/金融/健康等走 `professional_trust`；其他或无法识别默认 `punchy_local`。
- **mock 同步升级**：`MockProvider` 现在按 resolved copy_style 生成不同脚本、标题、封面、post_copy、BGM 和 recommended_structure。默认口腔 demo 自动走 `professional_trust`；餐饮类临时 config 自动走 `punchy_local`。
- **契约透传**：`build_project_input()` 已把 `copy_style` 写进 `project_input["config"]`，旧 config 无字段时传空字符串并自动判定。

**接口变化**: 无。没有改 `CONTRACTS/video_project.schema.json`。

**验证情况**:
- 通过：`python tests/test_llm_generate.py`，新增覆盖显式覆盖、industry 自动判定、兜底、copy_style 透传、mock 两套风格差异、prompt 关键词注入。
- 通过：默认口腔 demo `python run_workflow.py --demo-assets --clean --skip-tts --skip-mp4`，mock 自动走 `professional_trust`，recommended_structure 为“信任建立-流程说明-具体卖点-风险克制-温和引导”。
- 通过：临时餐饮 config 跑 `--skip-tts --skip-mp4`，mock 自动走 `punchy_local`，recommended_structure 为“强钩子-痛点直击-卖点具体化-少走弯路-明确行动”。
- 通过：`python tests/test_tts_generate.py`
- 通过：`python tests/test_render_mp4.py`
- 通过：`.\scripts\check_project.ps1`
- 未跑真实 Claude key：按 T-006 要求，避免 key 进入仓库/日志。真实 Claude 生成质量对比留给 Claude/用户复审。

**下一步建议**: Claude 复审时重点看 `build_claude_instruction()` 的 prompt 是否真的能提升文案质量，而不仅是结构正确；再用真实 key 跑 1-2 条 `--provider claude`，把真实生成和 mock 占位一起交给用户主观判断。

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
