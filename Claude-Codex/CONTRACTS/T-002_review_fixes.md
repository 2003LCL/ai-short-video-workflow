# T-002 复审修改单 (Claude Review → Codex)

> Claude 已审查 Codex 提交的 M1 实现，并亲自跑通了单测、mock 全流程、claude 无 key 报错三条路径，结果与你的报告一致，没有虚报。整体方向对（Provider 抽象干净、时间轴交给代码算、向后兼容到位）。但有 4 处问题不修会在「真接 Claude API」时翻车。本单按严重程度列出必改项，逐条修完后把 T-002 重新置为 REVIEW。

## 验证基线（复审时 Claude 会重新跑这三条）
- `python tests/test_llm_generate.py` → 应通过
- `python run_workflow.py --demo-assets --clean --provider mock` → 产物结构合法、渲染不坏
- 无 key 时 `--provider claude` → 清晰报错不崩溃

---

## 🔴 必改 1：ClaudeProvider 默认模型 ID 过时/不存在
- **位置**: `llm_generate.py:78`
- **问题**: 默认 `claude-3-5-sonnet-latest`。本项目环境下当前应使用 Claude 4.x。该 ID 会导致真实 API 调用失败。
- **改法**: 默认模型改为 **`claude-sonnet-4-6`**（生成类任务用 Sonnet 性价比合适）。保留 `CLAUDE_MODEL` 环境变量覆盖能力。
- **正确模型 ID 参考**: Opus 4.8 = `claude-opus-4-8`，Sonnet 4.6 = `claude-sonnet-4-6`，Haiku 4.5 = `claude-haiku-4-5-20251001`。

## 🔴 必改 2：Claude API 缺少结构化输出约束（违反规格第 3 点）
- **位置**: `ClaudeProvider.generate_json` (`llm_generate.py:83-111`)
- **问题**: 现在只用 prompt 文字请求「返回 JSON」，再用 `parse_json_object` 从文本里抠 `{...}`。这是最脆弱的做法——模型多说一句话或 JSON 被截断就解析失败。规格明确要求「结构化输出 / 工具调用强约束 JSON」。
- **改法**: 改用 Anthropic Messages API 的 **tool use 强制工具调用**：
  - 在请求 body 里定义一个工具，例如 `emit_video_content`，其 `input_schema` 用 JSON Schema 描述 `analysis` / `script` / `scenes` 三块结构（可从 `CONTRACTS/video_project.schema.json` 抽取对应子结构）。
  - 设 `tool_choice: {"type": "tool", "name": "emit_video_content"}` 强制模型必须调用该工具。
  - 从响应的 `content` 里取 `type == "tool_use"` 的块，直接读它的 `input` 字段拿到结构化对象——**不再走文本解析**。
- **注意**: 这样 `parse_json_object` 在 Claude 路径下不再需要（见必改 4 的死代码清理）。

## 🔴 必改 3：重试没覆盖网络/限流瞬时失败
- **位置**: `generate_video_content` (`llm_generate.py:114-128`)
- **问题**: 重试只在「校验失败」时触发。真正该重试的网络抖动 / API 限流（HTTPError 429/5xx、URLError）现在直接抛出退出，不重试。规格说的「失败重试」主要就该覆盖这类瞬时失败。
- **改法**: 把 provider 调用纳入 try/except 重试循环，区分两类：
  - **可重试**：URLError（网络）、HTTP 429 / 5xx（限流/服务端）→ 计入重试次数，重试。
  - **不可重试**：无 key、HTTP 4xx（401/400 等参数/认证错）→ 立即抛出，不浪费重试。
  - 建议给 `LLMGenerationError` 或新增异常加一个 `retryable: bool` 标志，或在 ClaudeProvider 内按 HTTP code 分类抛不同异常。

## 🟡 必改 4：删死代码 + 校验与契约的「两套真相」问题
- **问题 4a 死代码**: `load_schema` (`llm_generate.py:331-333`) 写了但从未被调用。
- **问题 4b 死代码**: 改用工具调用后，`parse_json_object` (`llm_generate.py:281-291`) 在 Claude 路径下冗余。
- **裁决（已记入 DECISIONS.md ADR-007）**: **M1 阶段不引入 jsonschema 依赖**，保留手写 `validate_generation`。schema 文件作为「契约文档」而非运行时校验器。
- **改法**:
  - 删除 `load_schema`（未使用）。
  - `parse_json_object` 如果工具调用路径完全不用了就删；若想留作兜底（模型偶尔不调工具直接出文本），可保留但要写注释说明它是 fallback，并在工具调用失败时才走它。二选一，写清楚理由。

## 🟢 顺手优化（不阻塞，但建议一起做）
- **timeline 校验二次报错**: `validate_timeline` (`llm_generate.py:207-221`) 中 duration 非法时置 0 继续累加，会连带报后续 start 全错，错误信息刷屏。建议遇到非法 duration 时聚焦报第一个错误即可，避免噪声。

---

## 收工动作（Codex 改完后）
1. 三条验证基线全部重跑通过（无 key 路径仍要清晰报错）。
2. `TASKS.md` 中 T-002 改回 REVIEW。
3. `STATE.md` 更新。
4. `HANDOFF.md` 顶部追加交接段，逐条说明「每个必改项怎么改的、为什么这么改」，方便 Claude 复审快速核对。
5. 必改 2 如果对 Anthropic tool use 的请求格式没把握，可在 HANDOFF 里写下你采用的请求 body 结构，复审时 Claude 会一并核对格式正确性。
