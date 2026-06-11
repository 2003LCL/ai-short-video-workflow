# T-008 任务规格：M5 网页编辑器 第一期 — 文案审改 (本地)

> 这是 Codex 的施工图。开工前按 PROTOCOL 顺序读：PROTOCOL → STATE → HANDOFF 最近 1-2 段 → DECISIONS(ADR-002/011/015) → schema → 本文件。
> 验收标准在文末。**不改 CONTRACTS/ 数据契约**（只读写已有 plan.json 字段）。

## 目标（一句话）

做一个**本地网页**，让非技术用户（比如店主）打开浏览器就能把已生成的 plan.json 里的文案（标题/封面/发布文案/各场景字幕和口播）**看明白、改掉、存回去**。这是 M5 的第一期，也是用户多次强调的「人工微调文案」必备需求的正式落地。

## 为什么是这个范围（背景）

- AI 生成的文案是 80 分底稿（T-006/T-006b），LLM 有随机性、偶尔失手，最后 20 分微调靠人——这就是本功能（ADR-002 半自动 + 人工品控）。
- 第一期**只做文案审改**，不做重渲染、不做投喂分页（那些是后续期）。先把「人能顺畅地改文案并存回」这条跑通。
- 技术栈已定（ADR-015）：Python + Flask 后端，原生 HTML/JS 前端，本地运行。

## 范围边界

**做：**
- 新增 `web_app.py`（或 `webapp/` 目录）：Flask 应用，提供 JSON API + 托管一个前端页面。
- 一组 JSON API：读取当前项目、保存修改后的文案。
- 一个原生 HTML/JS 单页前端：表单化展示 plan.json 的文案字段，可编辑，保存。
- 保存时写回 `output/plan.json`，并同步更新受影响的衍生产物（见下「保存的副作用」）。
- `requirements.txt` 加 `flask`。
- 新增 `tests/test_web_app.py`：测 API 逻辑（用 Flask test client，不真起服务）。
- README 或 docs 里加一段「怎么启动网页编辑器」。

**不做：**
- 不做增量重渲染（改完一键重出配音/视频）——那是第二期。
- 不做投喂分页（提示词复制 + 大模型链接）——那是后续期。
- 不做多用户、登录、远程部署、数据库——第一期本地单项目。
- 不改数据契约、不改 llm/tts/render 的核心逻辑。
- 不引入 React/Vue/Node 构建链路。

## API 设计（JSON，前端只通过这些和后端交互）

后端读写的是 `output/plan.json`（现有产物）。建议至少这几个端点：

- `GET /api/project` → 返回当前 plan.json 的全文（或精简出前端需要的文案部分：script.topic/cover_text/titles/post_copy/bgm_suggestion + 各 scene 的 order/caption/voiceover/asset_type/effect）。前端据此渲染表单。
- `POST /api/project/copy` → 接收前端提交的修改后文案（JSON body），校验后写回 plan.json。**只允许改文案字段**，不允许前端篡改 start/duration/timeline 这些由程序算的字段（后端要忽略或拒绝对这些字段的修改）。
- 保存成功返回更新后的项目状态；校验失败返回清晰错误（哪个字段为空/非法）。

**契约纪律**：API 读写的字段必须是 `video_project.schema.json` 已定义的（script.*、scenes[].caption/voiceover 等）。不新增契约字段。被用户改过的 scene 建议把 `edited` 置为 true（schema 已有该字段，本就是为「人工改过」设计的，增量重渲染第二期会用到）。

## 保存的副作用（重要，别只改 plan.json 留下不一致现场）

改了文案后，下列由文案派生的产物会和 plan.json 不一致。第一期至少要处理字幕和口播文本的同步（这些是纯文本、好同步，且 T-002/T-003 已有写出函数可复用）：
- `output/captions.srt`（字幕，来自 scene.caption）
- `output/voiceover_segments/*.txt` 和 `voiceover.txt`（口播文本，来自 scene.voiceover）
- `output/video_plan.md`（人类可读版）

**已有配音 mp3 / GIF / MP4 第一期不自动重生成**（那是第二期增量重渲染的活）。但要在前端给用户一个明确提示：「文案已保存，配音和视频需要重新生成才会更新」——避免用户以为改完文案视频就自动变了。可复用 run_workflow 里现成的 write_srt / write_voiceover_files / write_markdown（注意它们吃的是 legacy plan 结构，Codex 看清楚参数）。

## 前端（原生 HTML/JS，简单清晰，给非技术用户用）

- 单页：顶部显示店名/主题；中间分区显示「整体文案」（标题备选、封面文案、发布文案、BGM 建议）和「分镜列表」（每个场景一块：序号 + 素材类型 + 字幕输入框 + 口播文本框 + effect 只读或下拉）。
- 每个文案字段是可编辑输入框/文本域。
- 一个「保存」按钮，调 POST API，保存后给明确反馈（成功/失败/字段错误）。
- 保存后明确提示「配音/视频需重新生成」。
- 不追求好看，追求清楚、好用、中文界面、字段标签让店主看得懂（用「这句话的字幕」「这句话的口播」而不是 caption/voiceover）。
- UI 文案用中文。

## 启动方式
- `python web_app.py` 起服务，控制台打印 `http://127.0.0.1:<port>`，用户浏览器打开即用。
- 默认绑定 `127.0.0.1`（仅本机），**不要绑 0.0.0.0**（第一期不对外，避免无鉴权服务暴露到网络——安全）。
- 端口固定一个（如 5000）或可用环境变量配。

## 测试要求（`tests/test_web_app.py`，用 Flask test client）
- GET /api/project：在有 plan.json 时返回正确文案结构；无 plan.json 时给清晰错误（提示先跑 run_workflow 生成）。
- POST /api/project/copy：合法修改写回成功；空标题/空 caption 等非法输入被拒并给字段级错误；尝试篡改 start/duration 被忽略或拒绝（验证 timeline 字段没被前端改动）。
- 保存后 captions.srt / voiceover 文本确实同步更新。
- 被改的 scene 的 edited 置为 true。

## 验收标准（Codex 自检通过后改 T-008 → REVIEW）
1. 三套既有单测 + 新增 test_web_app 全过。
2. 先 `python run_workflow.py --demo-assets --clean --skip-tts --skip-mp4` 生成一个 plan.json，再 `python web_app.py` 起服务，浏览器打开能看到文案表单。
3. 在网页改一条标题 + 一条场景字幕 + 一条口播，点保存 → plan.json 对应字段更新、captions.srt 和 voiceover 文本同步更新、被改 scene 的 edited=true。
4. 提交空字段被拒、给清晰中文错误；尝试改 timeline 字段无效。
5. 服务绑定 127.0.0.1，控制台打印可点开的本地地址。
6. `.\scripts\check_project.ps1` 通过（如脚本需要可加 web 测试）。
7. flask 加入 requirements.txt。

## 已知坑提示
- run_workflow 里 write_srt/write_voiceover_files/write_markdown 吃的是 `plan`（legacy 结构）而非顶层 scenes。plan.json 里 `plan.scenes` 和顶层 `scenes` 目前是两份内容相同的镜像（看现有写法）。保存文案时**两处都要更新**，否则重渲染/预览会读到旧文案。Codex 看清楚 plan.json 结构再动手，在 HANDOFF 说明怎么保证两处一致。
- 不要把 plan.json 整个交给前端再整个写回（前端可能丢字段）。后端应「读现有 plan.json → 只更新允许的文案字段 → 写回」，保留 analysis/audio/renders/compliance 等其他字段不动。
- Flask 默认 debug 模式不要开（或仅本地开发开），避免无意义的安全面。
- 中文 JSON 响应注意 `ensure_ascii=False` 和 UTF-8，别出乱码。
