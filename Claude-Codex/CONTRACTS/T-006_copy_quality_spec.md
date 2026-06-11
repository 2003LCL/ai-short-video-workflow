# T-006 任务规格：文案质量专项 — prompt 工程 + 两套可切换风格 (闭环后回炉)

> 这是 Codex 的施工图。开工前按 PROTOCOL 顺序读：PROTOCOL → STATE → HANDOFF 最近 1-2 段 → DECISIONS(ADR-011/013) → schema(config.copy_style 新字段) → 本文件。
> 验收标准在文末。**不要改 CONTRACTS/ 数据契约**（copy_style 字段 PM 已加好，你只消费）。

## 目标（一句话）

把 M1 的文案从「正确但平庸的占位」升级为「真正会写带货的文案」。核心是**重写 prompt**，不是改架构。
用户多次强调：真正决定视频好坏的是文案质量，不是配音/渲染花哨度。这是产品核心竞争力。

## 这个任务的本质

当前瓶颈在 `llm_generate.py` 的 `build_claude_instruction()`（约 271-292 行）：它只讲了 JSON 结构约束（生成中文、3-5 scene、避免医疗承诺），**没有任何文案创作指导**。Claude 拿到这种 prompt 只能产出和 mock 同档次的内容。这个任务就是把这个 prompt 写好，并让 mock 占位文案同步升级。

## 范围边界

**做：**
- 重写 `build_claude_instruction()`：注入真正的文案创作准则（见下「两套风格」）。
- 实现两套文案风格 `punchy_local` / `professional_trust`，按 `copy_style` 选择，prompt 注入对应准则。
- `copy_style` 解析逻辑：config 显式指定优先；为空时按 `industry` 自动判定。
- mock provider 的占位文案按 copy_style 产出两套风格（让离线 demo 也展示像样效果）。
- `build_project_input()` 把 `copy_style` 透传进 project_input 的 config（schema 已加该字段）。
- 补/改测试：copy_style 解析（显式 / 自动判定 / 兜底）、mock 两套风格产出、prompt 含对应准则关键词。

**不做：**
- 不改 `CONTRACTS/video_project.schema.json`（copy_style 字段 PM 已加）。
- 不动 M2(TTS) / M3(MP4) / 时间轴分配 / 校验主流程结构。
- 不改 `validate_generation` 的字段要求（文案变的是内容质量不是结构）。
- 不引入新依赖。

## copy_style 解析（明确规则，照做）

```
def resolve_copy_style(config) -> "punchy_local" | "professional_trust":
    explicit = (config.get("copy_style") or "").strip()
    if explicit in ("punchy_local", "professional_trust"):
        return explicit
    industry = config.get("industry", "")
    # 自动判定：专业信任赛道
    if 命中(医疗/口腔/医美/教育/培训/法律/金融/健康)：return "professional_trust"
    # 其余下沉生活服务（餐饮/零售/维修/美业/家政/生活服务）默认强钩子
    return "punchy_local"
```
- 关键词匹配用包含判断即可（中文 industry 字段），列表定义为模块常量便于维护。
- 兜底：识别不出的 industry 默认 `punchy_local`（项目主赛道是下沉生活服务）。

## 两套风格的创作准则（注入 prompt 的核心内容）

### punchy_local（下沉口语强钩子）
- **前3秒强钩子**：第一个 scene 的 caption/voiceover 必须是能让人停下划动的钩子（戳痛点、抛疑问、给反差、点利益），不要平铺直叙「我们是XX店」。
- **痛点直给**：用目标客户真实会说的大白话，不用书面语/营销腔。
- **卖点具体化**：把 main_offer 翻译成客户能感知的具体好处，不空喊「专业/优质」。
- **结尾强转化引导**：明确的下一步动作（到店/咨询/私信/领券），结合 cta。
- **节奏**：短句、口语、有网感，适配抖音/快手竖屏快节奏。

### professional_trust（专业克制信任感）
- **建立信任**：突出流程透明、资质、规范，语气稳重专业。
- **克制不夸张**：不用绝对化表达，不做疗效/结果承诺（尤其医疗，配合现有风险词约束）。
- **信息清晰**：帮第一次接触的客户把「该了解什么」讲清楚。
- **温和引导**：结尾引导到正规咨询/面诊，不强推。

两套都必须遵守的硬约束（保留现有规则）：
- 中文文案；不输出 start/duration（程序算时间轴）；scenes 3-5 个；每个 scene 含 order/asset_type/caption/voiceover/effect/edited；edited=false；effect 取现有枚举。
- 避免医疗疗效承诺、治愈率、绝对化表达、患者证言（现有规则，prompt 里继续强调，professional_trust 尤其）。
- caption 与 voiceover 可有差异：caption 是屏幕字幕（精炼），voiceover 是口播稿（可稍口语完整），但语义一致。建议在 prompt 里说明这个区别，让文案更自然（当前两者经常完全相同，是平庸感来源之一）。

## prompt 写法建议（给 Codex 的方向，不强制照抄）

- 给 Claude 一个明确的「角色设定」：你是给本地小商户写爆款短视频脚本的资深操盘手。
- 把选中的风格准则作为「创作要求」段落注入，而不是只列 JSON 字段。
- 可给 1 个简短的好文案示例（few-shot），但注意别让它套用到所有行业（示例要中性或标注「仅示意结构」）。
- 保留 tool_use 强制结构化输出（emit_video_content）和 retry_note 机制，不要退回文本解析。
- max_tokens 可适当上调（当前 3000）若文案变长，但别过度。

## 验收标准（Codex 自检通过后改 T-006 → REVIEW）

1. `python tests/test_llm_generate.py` 通过（含新增的 copy_style 解析、mock 两套风格、prompt 含风格关键词的测试）；`test_tts_generate` / `test_render_mp4` 回归通过。
2. `resolve_copy_style` 三类输入正确：显式 punchy_local/professional_trust 直接返回；空 + 医疗类 industry → professional_trust；空 + 餐饮类 → punchy_local；无法识别 → punchy_local。
3. `python run_workflow.py --demo-assets --clean`（mock）跑通：plan.json 文案体现所选风格（默认 demo 是医疗口腔，应走 professional_trust）；改 config industry 为餐饮类后重跑应走 punchy_local，两套占位文案明显不同。
4. mock 两套风格文案都合法通过 validate_generation，时间轴正常，闭环（GIF/MP4/TTS）不受影响。
5. `build_claude_instruction` 在两种风格下分别注入了对应准则（可在测试里断言关键词出现）。
6. `.\scripts\check_project.ps1` 通过。
7. **真实 Claude 验收（Codex 不跑，留给 Claude/用户）**：T-006 改 REVIEW 后，Claude 复审时用真实 key 跑 `--provider claude` 生成 1-2 条真实文案，连同 mock 文案一起交用户主观对比判断质量是否提升。Codex 在 HANDOFF 写明：未用真实 key 跑（避免 key 进仓库/日志），把真实生成验证留给复审环节。

## 已知坑提示

- 真实 Claude 调用要花钱且需 key，**Codex 阶段不要用真实 key 跑**，只保证 mock 路径和 prompt 文本正确（对齐 M1 当初「真实 API 留到上线单独验证」的做法）。
- copy_style 自动判定的 industry 关键词列表会影响判定，列清楚、写成常量、测试覆盖边界。
- 别让 few-shot 示例污染输出（Claude 可能直接套用示例的店名/行业），示例要中性或明确标注仅示意。
- 文案质量是主观的，自动化测试只能测「结构合法 + 风格关键词注入 + 两套确实不同」，测不了「好不好」——好不好由真实生成 + 用户判断决定，别试图用断言证明文案质量高。
