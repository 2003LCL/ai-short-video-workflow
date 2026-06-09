# 交接说明 (HANDOFF.md)

> 最新的交接写在最上面。任何 AI 接手前先读最近 1-2 条，就能跟上思路。
> 固定格式见 PROTOCOL.md。

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
