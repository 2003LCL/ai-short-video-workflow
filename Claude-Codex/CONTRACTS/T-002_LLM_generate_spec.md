# 任务规格 T-002：LLM 生成模块 (M1)

> 这是给 Codex 的施工图。Codex 开工前必须先读：PROTOCOL.md → STATE.md →
> CONTRACTS/video_project.schema.json → 本文件。不清楚的地方按本文件为准；
> 涉及改接口契约的，停下来在 HANDOFF.md 提问，等 Claude 确认，不要擅自改。

## 目标

把现有 `run_workflow.py` 里 **模板驱动** 的生成（`generate_plan`、`make_titles`、
`make_post_copy` 等函数）升级为 **真 LLM 驱动** 的分析 + 生成，产出符合
`CONTRACTS/video_project.schema.json` 的 `analysis` + `script` + `scenes` 三块内容。

**只做 M1 这一段**（输入 → 分析 → 生成脚本/分镜/口播/标题/封面文案）。
不碰 TTS、不碰 MP4 渲染、不碰 Web 界面——那是后续里程碑。

## 范围边界（明确不做什么）

- 不改渲染逻辑（`write_html` / `render_gif_preview` 保持可用，继续吃 scenes）。
- 不引入前端、不引入 Web 框架。
- 不实现素材自动匹配（M4）；本阶段 scene.asset_id 仍可沿用「按顺序取图」的旧逻辑。
- 不接真实付费 API 也能跑：必须提供一个 `--provider mock` 模式（见下）。

## 具体要求

### 1. 新建模块 `llm_generate.py`（不要把这堆逻辑塞进 run_workflow.py）
   职责单一：输入一个 dict（含 input.shop、可选 input.sources 的 extracted_text、config），
   输出一个 dict（analysis + script + scenes），结构严格符合 schema 对应部分。

### 2. Provider 抽象（关键设计）
   定义一个 `LLMProvider` 接口/基类，至少两个实现：
   - `MockProvider`：不调任何 API，用规则/模板产出合法结构（其实可复用现有模板逻辑）。
     **作用：让整条流水线在没有 API key 时也能跑通、能写测试、CI 友好。**
   - `ClaudeProvider`：调用 Anthropic API（读 env 里的 key），用结构化输出 / 工具调用强约束 JSON。
   通过 `--provider mock|claude` 或 config 字段切换。默认 mock。

### 3. 结构化输出 + 校验 + 重试
   - LLM 返回后，用 schema 校验（可用 jsonschema 库；若不引依赖则手写关键字段校验）。
   - 校验失败时重试（带上「上次哪里不合格」的提示），最多 N 次（N=3，可配）。
   - 三次仍失败则报错退出并写明原因，不要静默吞掉。

### 4. 接进 run_workflow.py
   - 加 `--provider` 参数。
   - 用 llm_generate 的产出替换 generate_plan 的对应部分，但 **保留 plan.json 向后兼容**：
     旧的 `plan` 字段继续写出（给现有渲染用），同时新增 analysis 写进产物。
   - 现有 `--demo-assets` / `--clean` / 渲染 / 合规检查流程保持不变。

### 5. 合规检查前移
   生成出来的 scenes/script 仍要过现有 `check_compliance`。医疗模式下命中风险词时，
   理想做法是让 LLM 重生成一版规避（可选增强，不强制本期做，但要在代码里留 TODO 注释）。

## 验收标准（Claude 审查时会逐条核对）

- [ ] `python run_workflow.py --demo-assets --clean --provider mock` 能跑通，产物结构合法。
- [ ] `llm_generate.py` 可独立 import 和单元测试，不依赖 run_workflow 的全局状态。
- [ ] 产出的 analysis / script / scenes 通过 schema 校验。
- [ ] ClaudeProvider 在无 key 时给出清晰报错，不崩在莫名其妙的地方。
- [ ] 有针对 MockProvider 的测试（至少覆盖：必填字段齐全、scenes 时间轴连续不重叠、duration 合法）。
- [ ] 不破坏现有 GIF/HTML 渲染。
- [ ] 代码风格与 run_workflow.py 一致（类型注解、中文注释密度、命名）。

## 交付时（Codex 收工动作）

1. 更新 `STATE.md`（M1 状态、当前焦点）。
2. 更新 `TASKS.md`（T-002 → REVIEW）。
3. 在 `HANDOFF.md` 顶部按固定格式追加交接段，**重点写「为什么这么设计 Provider 抽象/校验逻辑」**，让 Claude 审查时能跟上你的思路。
4. 若过程中做了任何架构选择（比如选了某个库），记进 `DECISIONS.md`。

## 已知坑提示

- Windows 环境，路径用 pathlib，编码统一 utf-8（现有代码已是这样，照做）。
- 现有 config.json 用 utf-8-sig 读，别改坏。
- LLM 输出中文时注意 ensure_ascii=False。
- scene 的 start/duration 必须由代码保证时间轴自洽（参考现有 scene_duration），
  **不要完全信任 LLM 算的时间**——让 LLM 给内容，时间轴由代码分配。
