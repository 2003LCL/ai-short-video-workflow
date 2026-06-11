# T-007 任务规格：离线文案接入 — file provider + 可配置中转地址

> 这是 Codex 的施工图。开工前按 PROTOCOL 顺序读：PROTOCOL → STATE → HANDOFF 最近 1-2 段 → DECISIONS(ADR-013/014) → schema → 本文件。
> 验收标准在文末。**不改 CONTRACTS/ 数据契约**（本任务只动 llm_generate.py 的 provider 层 + run_workflow 接入）。

## 背景

用户的真实环境：没有官方 Anthropic key，只有「中转站」的 key；`--provider claude` 直接发往官方 `api.anthropic.com` 被 403 拒绝。
用户提了一个很好的方向：让程序生成一个「提示词文件」，人工喂给任意 AI（Claude.ai / 网页版 / 任何模型），拿回 JSON 再读回流水线——零 key、零成本、不挑模型，且完全契合 ADR-002「半自动 + 人工品控」定位。

本任务做两件事，互为备份：
1. **主方案：新增 `--provider file` 离线人工投喂模式**（用户首选，重点做扎实）。
2. **顺手：让 `--provider claude` 的接入地址可配置**，使中转站 key 能用。

## 子目标 1：`--provider file` 离线人工投喂模式（重点）

### 交互流程（两段式，靠文件落盘衔接）
```
第一次跑（生成提示词）:
  python run_workflow.py --demo-assets --clean --provider file
  → 程序把 build_claude_instruction 产出的完整提示词写到 output/llm_prompt.txt
  → 程序提示用户：把这个文件内容贴给任意 AI，要求它【只返回 JSON】，
     把 AI 返回的 JSON 存成 output/llm_response.json，然后重跑同样命令
  → 此时因为还没有 response 文件，干净地停下（不报错崩溃，给清晰指引）

第二次跑（读回结果）:
  （用户已把 AI 给的 JSON 存进 output/llm_response.json）
  python run_workflow.py --demo-assets --provider file   # 注意不带 --clean，否则会清掉 response
  → 程序检测到 output/llm_response.json 存在，读取它、走完整 validate_generation 校验
  → 校验通过则继续 TTS/字幕/MP4 全流程；不通过则打印具体校验错误，让用户拿着错误重新让 AI 改
```

### 实现要点
- 新增 `FileProvider(LLMProvider)`，实现 `generate_json(prompt, last_error)`：
  - 读 `output/llm_response.json`（路径相对 OUTPUT_DIR）。
  - 文件不存在 → 把 `build_claude_instruction(prompt, last_error)` 的完整提示词写到 `output/llm_prompt.txt`，然后抛一个**专门的、可识别的异常**（不要用普通 LLMGenerationError 让它去重试 3 次——file 模式重试没意义）。建议新增 `LLMPromptPendingError(LLMGenerationError)` 或在异常上带个标志，让 `generate_video_content` 不重试、`run_workflow.py` 捕获后打印「提示词已生成，请喂给 AI」的友好指引并干净退出（exit code 非崩溃）。
  - 文件存在 → `json.loads` 它，返回 dict（解析失败给清晰错误：JSON 格式不对，让用户检查 AI 输出）。
- `FileProvider` 不联网、不需要 key。
- `make_provider` 增加 `file` 分支。
- `run_workflow.py` 的 `--provider` choices 加 `file`；主流程捕获「提示词待投喂」这个信号，打印指引并 `raise SystemExit(0)` 式干净退出（区别于真正的失败）。
- `generate_video_content` 的重试循环要识别「提示词待投喂」不去重试。
- **提示词文件要含明确的人工操作说明头部**：在 llm_prompt.txt 顶部加几行中文说明，告诉用户「把以下内容发给 AI，要求只返回 JSON（不要解释、不要 markdown 代码块包裹），把返回的 JSON 存成 output/llm_response.json 后重跑」。让不懂技术的人也能照做。

### 边界
- `--clean` 会清空 output/，导致 llm_response.json 被删——在指引里**明确提醒第二次跑不要带 --clean**，或更稳妥：把 llm_response.json 放在 output/ 之外（如项目根的 `llm_response.json`）避免被 --clean 误删。**Codex 自行判断哪种更稳，在 HANDOFF 说明选择**。（PM 倾向：放 output/ 外，彻底避开 --clean 这个坑，参考 T-006 验证时踩过的 --clean 删文件教训。）
- response JSON 的结构由现有 `validate_generation` 把关，FileProvider 不需要自己校验业务字段，只负责读取和 JSON 解析。

## 子目标 2：`--provider claude` 接入地址可配置（顺手，修中转站 403）

### 改动（`llm_generate.py` 的 `ClaudeProvider`）
- 当前 `generate_json` 把 URL 写死成 `https://api.anthropic.com/v1/messages`（约 127 行）。
- 改为可配置：读环境变量 `ANTHROPIC_BASE_URL`（为空时默认官方 `https://api.anthropic.com`），实际请求地址 = `base_url.rstrip("/") + "/v1/messages"`。
- `ClaudeProvider.__init__` 里把 base_url 存为实例属性，注释说明：中转站/代理需设 `ANTHROPIC_BASE_URL`。
- 其余请求格式（headers 的 x-api-key / anthropic-version、body、tool_use 解析）**不动**——绝大多数中转站兼容官方 Messages API 格式，只是域名不同。
- 不要把 base_url / key 打印进日志或写进任何文件。

### 说明
- 中转站的真实接入地址由用户提供，本任务只把「地址可配置」这个能力做好，地址填什么是用户运行时的环境变量。Codex 无法用真实中转站 key 验证（也不该拿到用户的 key），这条只做代码 + 单测（mock 掉网络），真实验证留给用户/复审。

## 测试要求（`tests/test_llm_generate.py` 增补）
- FileProvider：response 文件不存在 → 写出 llm_prompt.txt + 抛「待投喂」信号（不触发重试）；response 文件存在且合法 → 正确读取返回 dict；response JSON 非法 → 清晰报错。
- `generate_video_content` 在 file 模式下遇到「待投喂」信号不重试 3 次（用 fake 验证调用次数）。
- ClaudeProvider：`ANTHROPIC_BASE_URL` 设置时请求地址拼接正确、为空时回落官方地址（可 monkeypatch urlopen 或抽出一个纯函数算最终 URL 来断言，不真实联网）。
- 现有测试全部回归通过。

## 验收标准（Codex 自检通过后改 T-007 → REVIEW）
1. 三套单测全过（含上述新增）。
2. `python run_workflow.py --demo-assets --clean --provider file`：生成 `output/llm_prompt.txt`（含人工操作说明 + 完整提示词），干净退出并打印清晰指引，不崩溃、不误判为失败。
3. 手动把一份合法 JSON 放到约定的 response 路径后重跑 `--provider file`：读回成功，走完 TTS/字幕/MP4（或 skip）全流程，plan.json 文案来自该 JSON。
4. response JSON 缺字段/格式错时，打印具体校验错误（复用 validate_generation），不静默吞掉。
5. `--provider mock` 和 `--provider claude` 回归正常（claude 无 key 仍给清晰报错；设了 ANTHROPIC_BASE_URL 时地址拼接正确）。
6. `.\scripts\check_project.ps1` 通过。
7. llm_prompt.txt / llm_response.json 加进 .gitignore（属本地运行产物，不进仓库）。

## 已知坑提示
- file 模式两次运行之间靠文件落盘传状态，--clean 会破坏它——这是最容易踩的坑，务必在指引文案和 .gitignore 里处理好，response 文件建议放 output/ 外。
- AI 返回的 JSON 常被 markdown ```json 代码块包裹，或带前后解释文字。FileProvider 读取时**可以宽容一点**：若直接 json.loads 失败，尝试剥掉 ```json ... ``` 包裹再解析；仍失败才报错。但别过度工程，剥代码块 + 裸 JSON 两种够用。
- 不要为 file 模式改 build_claude_instruction 的内容（T-006 刚定稿），只是把它的产出写到文件而非发给 API。
- 提示词里目前是英文指令 + 中文产出要求，这套对真实 AI 有效，保持不动。
