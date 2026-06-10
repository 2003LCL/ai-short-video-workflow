# T-003 复审修改单 #2 (Claude Review → Codex)

> 背景：T-003 M2 功能复审已通过（配音能真实生成、字段符合契约、时长真实）。但复审过程中发现一个**健壮性缺陷**，用户决定现在就修（不留到 M3）。本单只修这一个问题，不要扩大范围。

## 🟡 必改：失败的 TTS 运行会清空上一次的成功配音

### 问题
`generate_voiceover_audio` (`tts_generate.py:116-119`) 在生成前**无条件** `shutil.rmtree(audio_dir)` 清空整个 `voiceover_audio/` 目录，然后才逐段合成。

后果：任何一次「整体失败」的运行都会把上次的好产物删光且无新产物补上。实测触发场景：
- 跑 `--tts-provider aliyun`（占位必失败）→ 先清空目录 → 每段都 raise → 最终目录全空，上次 edge 生成的 mp3 没了。
- 断网时跑 edge → 同样先清空 → 全失败 → 配音丢失。

对一个要自动化、可能反复重跑的流水线，这意味着「跑错一次 provider 就毁掉已有配音」，不可接受。

### 修法（按这个来，不要自由发挥）
核心原则：**先成功生成，再替换；失败不破坏已有产物。** 推荐用「临时目录 + 原子替换」：

1. 把音频先生成到一个临时目录（如 `voiceover_audio.tmp/` 或 tempfile 创建的目录）。
2. 逐段合成。
3. **只有在至少有一段成功**时，才用临时目录替换正式的 `voiceover_audio/`（先删旧正式目录、再把临时目录改名/移动过去）。
4. **如果一段都没成功**（segments == 0），保留原有的 `voiceover_audio/` 不动，清理临时目录，照常返回 summary（segments=0）并打印 warning。

可接受的等价实现：先把每段写到临时文件名，全部尝试完后再决定是否覆盖——只要满足「整体失败时不删旧产物」即可。

### 边界要求
- `NoneProvider`（--skip-tts）路径维持现状：直接 return，不碰目录。
- 部分成功（有的段成功、有的失败）：成功的段正常替换进正式目录，这是正常行为，保留。
- 替换过程本身要稳：临时目录清理别漏（成功替换后、或失败放弃后都要清掉临时目录）。
- Windows 下 `Path.rename`/`replace` 跨目录移动注意：同盘符内 `os.replace` 可原子替换目录；若 rmtree+rename 分两步，注意中途异常的处理。用 `shutil.move` 或先 `rmtree` 正式目录再 `os.replace` 临时目录均可，写清楚即可。

## 测试要求（复审会重点看这条）
在 `tests/test_tts_generate.py` 新增一个测试，**证明「整体失败不破坏已有产物」**：
1. 先用 FakeProvider 成功生成一批音频到某目录。
2. 再对同一目录用一个「全部失败的 provider」跑一次。
3. 断言：原有的音频文件**仍然存在**、内容未被清空（segments==0 但旧文件还在）。

现有三个测试（回填、单段失败继续、none 跳过）保持通过。

## 验证基线（复审重跑）
- `python tests/test_tts_generate.py`（含新增的「失败不破坏」测试）
- `python run_workflow.py --demo-assets --clean --tts-provider edge`（真实生成）
- 紧接着再跑 `python run_workflow.py --demo-assets --tts-provider aliyun`（注意**不带 --clean**），断言上一步的 mp3 **仍在**、plan.json 的 audio 退化为 aliyun/segments=0 但不删音频文件。

## 收工动作
1. T-003 状态：DOING → REVIEW（功能上轮已过，本轮只补健壮性，修完回 REVIEW）。
2. HANDOFF.md 顶部写交接段，说明临时目录/替换的具体做法和边界处理。
3. 不要改 CONTRACTS、不要动 M1、不要顺带改其他无关逻辑。
