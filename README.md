# AI Short Video Workflow POC

一个面向本地商家的 AI 短视频生产工作流原型。输入 1-5 张门店图片和一份店铺信息，自动生成短视频方案、字幕、GIF 动态预览、HTML 预览。

核心思路：AI 不手动操作剪辑软件，而是生成结构化剪辑方案，再交给渲染工具执行。

![demo preview](output/preview.gif)

## 目录

```text
ai_video_workflow_poc/
  config.example.json
  config.json
  input/
    images/
  output/
    preview.html
    video_plan.md
    plan.json
    captions.srt
    preview.gif
    voiceover.txt
    voiceover_segments/
    recording/
  run_workflow.py
  record_preview.js
```

## 使用方法

1. 复制 `config.example.json` 为 `config.json`，填写店铺信息。
2. 把 1-5 张图片放到 `input/images/`。
3. 运行：

```powershell
& "C:\Users\LCL\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\run_workflow.py --demo-assets
```

4. 查看输出：

- `output/video_plan.md`：选题、标题、分镜、发布文案、合规检查。
- `output/preview.gif`：无需额外软件的动态预览。
- `output/preview.html`：更接近真实短视频播放效果的竖屏预览。
- `output/captions.srt`：字幕文件。
- `output/voiceover.txt`：可直接送进 CozyVoice 的口播文本。
- `output/plan.json`：给后续 FFmpeg/Remotion 使用的结构化剪辑方案。

5. 如需录制 WebM，需要本机已安装 Playwright 浏览器二进制：

```powershell
$env:NODE_PATH="C:\Users\LCL\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules"
& "C:\Users\LCL\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe" .\record_preview.js
```

## 当前能力

- 支持低素材门槛：1 张图片也能生成，3 张以上更自然。
- 自动生成选题文案、标题、发布文案、分镜、字幕。
- 内置医疗内容风险词检查。
- 生成 `preview.html`，可作为视频预览/录制源。
- 生成 `preview.gif`，不用 FFmpeg/浏览器也能查看动态效果。
- 可选通过 Playwright 录制 WebM。

## 项目文档

- `docs/ARCHITECTURE.md`：工作流架构。
- `docs/ROADMAP.md`：迭代路线。
- `docs/COSYVOICE.md`：CozyVoice 接入说明。
- `docs/GITHUB_START.md`：GitHub 创建和上传说明。
- `SECURITY.md`：密钥和客户素材安全说明。

## 下一步

- 接入真实 LLM API 替换模板生成。
- 接入 TTS 生成配音。
- 安装 FFmpeg 后导出 MP4，并加入 BGM。
- 增加素材识别、封面图生成、多模板选择。

## 配音建议

CozyVoice 可以作为正式配音主线，但建议独立部署，不要直接塞进这个 POC。当前项目已经导出 `output/voiceover_segments/*.txt`，后续可以批量送入 CozyVoice 生成每段 wav。

不要把 API key 写进 `config.json` 或代码里。需要接 LLM/API 时，用 `.env` 或系统环境变量。
