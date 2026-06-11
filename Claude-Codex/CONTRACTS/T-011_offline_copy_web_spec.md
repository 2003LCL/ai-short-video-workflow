# T-011 任务规格：M5 第三期 — 网页离线投喂页（零 key 生成文案）

> 这是 Codex 的施工图。开工前按 PROTOCOL 顺序读：PROTOCOL → STATE → HANDOFF 最近 1-2 段 → DECISIONS(ADR-002/014/015) → schema → 本文件。
> 验收标准在文末。**不改 CONTRACTS 数据契约**（复用现有 build_claude_instruction + validate_generation + plan.json 字段）。

## 目标（一句话）

在网页编辑器加一个「离线生成文案」页/区：用户**没有 API key 也能用真实大模型生成文案**——网页给出提示词（一键复制）+ 主流大模型网页链接，用户去任意 AI 网页版粘贴生成，把 AI 返回的 JSON 贴回网页，系统解析校验后写进 plan.json，再走文案审改/重渲染流程。

## 背景

- 用户环境没有官方 key（中转 key 可用但不稳定，且不是所有用户都有）。ADR-014 已定「file provider 人工投喂」为零 key 主方案。
- M5 第一/二期已让用户能「改文案→重出片」，但**文案的首次生成仍依赖 mock 或 key**。第三期补上「用真实大模型生成首版文案、零 key」这一环，闭环就完整了。
- 这是 ADR-014 file provider 的**网页版**（命令行版 T-007 仍可留作备选，但本期直接做网页版，更贴合非技术用户）。

## 范围边界

**做：**
- 网页加「离线生成文案」入口（新页或现有页的一个区/标签）。
- 后端 API：
  - `GET /api/offline/prompt`：根据当前店铺输入（config/shop）生成完整提示词文本（复用 `llm_generate.build_claude_instruction` + `build_project_input`），返回给前端展示。
  - `POST /api/offline/apply`：接收用户贴回的 AI 输出（文本），解析出 JSON、走 `validate_generation` 校验，合法则写进 plan.json（analysis/script/scenes）并重算时间轴，返回成功/字段错误。
- 前端「离线生成文案」区：
  - 显示生成好的提示词（只读文本框）+ **一键复制**按钮。
  - 一排**主流大模型网页链接**（新标签打开）：豆包、Kimi、通义千问、DeepSeek、文心一言等（纯 `<a target="_blank">`，不调它们的 API）。
  - 一个**粘贴框** + 「应用文案」按钮：把 AI 返回的内容贴进来，提交给 apply API。
  - 成功后提示「文案已生成，可去文案审改页修改或直接重新生成视频」。
- 复用现有 JSON 宽容解析：AI 返回常被 ```json 代码块包裹或带前后说明文字，apply 时要能剥壳提取 JSON（先直接 json.loads，失败再尝试剥 ```json...``` 或截取第一个 `{` 到最后一个 `}`）。

**不做：**
- 不调用任何大模型 API（本期就是「零 key、人工搬运」，链接只是 `<a>` 跳转）。
- 不改数据契约 / schema。
- 不做账号/多用户/部署。
- 不重写 T-006 的 prompt 内容（只复用 build_claude_instruction 的产出）。
- 不动 M5 第一/二期已完成的文案审改、重渲染逻辑（共存）。

## 与现有代码的复用点（看清楚再动手）

- 生成提示词：`llm_generate.build_claude_instruction(prompt_json_str, last_error=None)`，其中 `prompt_json_str = json.dumps(build_project_input(config, assets, sources))`。这是 T-006 定稿的高质量带货文案 prompt，**直接复用，不要另写**。
- 校验 AI 返回：`llm_generate.validate_generation(candidate, project_input)` + `apply_timeline(candidate, duration)` + `validate_timeline(...)`，和 `generate_video_content` 内部用的是同一套。建议直接复用这套流程（可考虑把 generate_video_content 里「校验+时间轴」那段抽成一个可复用函数，避免在 web_app 里重写一遍校验逻辑——Codex 判断，但不要让校验逻辑出现两份真相）。
- 写 plan.json：参考现有 run_workflow 写 plan.json 的结构（schema_version/input/config/analysis/script/scenes/...），以及 web_app 已有的「读现有 plan.json→只改部分字段→写回」的安全模式。
- 注意：apply 成功后，scenes 是全新生成的，配音/视频都过时了——比照第一期的提示，告诉用户「需要重新生成视频」；新 scenes 的 edited 可不置（因为是全新生成不是人工微调），但要确保第二期重渲染能正常对这批新 scenes 工作（首次生成后配音可能还没有，重渲染时 edited 为空则全段配音——Codex 注意这个衔接，在 HANDOFF 说明）。

## 数据来源问题（需处理）

生成提示词需要店铺输入（shop_name/industry/topic/main_offer 等）。来源两种，Codex 选其一并说明：
- A：从当前 `output/plan.json` 的 `input.shop` + `config` 读（如果已有项目）。
- B：网页上让用户填一个简单表单（店名/行业/想宣传什么/主打），再生成提示词（适合「全新项目、还没有 plan.json」）。
- 建议：本期先做 A（基于已有项目重新生成文案，最简单、和现有编辑器衔接）；B（网页新建项目）留作后续。**若选 A，无 plan.json 时给清晰提示**「请先用 run_workflow 生成一次基础项目」。

## 测试要求（tests/test_web_app.py 增补）
- `GET /api/offline/prompt`：返回的提示词包含 T-006 prompt 的关键锚点（如 copy_style、店铺信息）。
- `POST /api/offline/apply`：
  - 贴入合法 JSON（裸 JSON / ```json 包裹 / 带前后文字三种）都能正确解析并写进 plan.json。
  - 贴入非法/缺字段 JSON 被拒，返回字段级中文错误（复用 validate_generation）。
  - apply 成功后 plan.json 的 analysis/script/scenes 更新、时间轴合法。
- 四套既有单测回归通过。

## 验收标准（Codex 自检通过后改 T-011 → REVIEW）
1. 四套单测 + 新增 offline 测试全过。
2. 起 web_app，「离线生成文案」区能显示提示词、一键复制可用、大模型链接能新标签打开。
3. 手动把一份合法 JSON（可由 PM 用真实 AI 或手写）贴进粘贴框 → 应用成功 → plan.json 文案更新 → 能在文案审改页看到新文案 → 能重新生成视频。
4. 非法 JSON / 缺字段被拒并给清晰中文错误，不写坏 plan.json。
5. JSON 宽容解析：```json 包裹、带前后说明文字都能正确提取。
6. 无 plan.json（选方案 A 时）给清晰指引。
7. 仍绑 127.0.0.1、debug off；`.\scripts\check_project.ps1` 通过。

## 已知坑提示
- AI 网页版返回的内容几乎一定带 markdown 代码块或解释文字，apply 的解析必须宽容（剥 ```json、截取 {…}），否则用户体验很差。
- 校验逻辑别在 web_app 里重写一份——复用 llm_generate 的 validate_generation/apply_timeline，保持单一真相。
- 写 plan.json 用现有的原子写（tempfile+replace）和「保留其他字段」模式，别整个覆盖。
- apply 写入新 scenes 后，旧配音/视频过时；和第二期重渲染衔接时，新 scenes 通常还没 voiceover_audio，重渲染要能处理「全段都要配音」的情况（edited 为空时的行为，Codex 确认并在 HANDOFF 说明）。
- 大模型网页链接用稳定的官网地址，注释标明仅跳转、不调 API。
