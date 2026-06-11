# T-009 任务规格：网页编辑器一键启动（Windows 本地）

> 这是 Codex 的施工图。开工前按 PROTOCOL 顺序读：PROTOCOL → STATE → HANDOFF 最近 1-2 段 → DECISIONS(ADR-015) → 本文件。
> 验收标准在文末。**不改业务逻辑、不改 CONTRACTS**，只加启动便利层。

## 目标（一句话）

让非技术用户**双击一个文件**就能打开网页编辑器：自动找 Python、自动装依赖、自动起服务、自动打开浏览器。消除「敲长命令、记 127.0.0.1:5000」的门槛。

## 背景与现状

- T-008 已交付 `web_app.py`，但启动要手敲 `& "C:\...\python.exe" web_app.py` 再手动开浏览器，对店主级用户门槛太高。
- **关键现实（已查证，务必处理）**：
  - flask/moviepy/edge-tts 等依赖目前只装在 Codex 的 bundled Python（`C:\Users\LCL\.cache\codex-runtimes\...\python.exe`）里。
  - 那个 bundled 路径是**工具缓存目录**，不稳定（工具更新/清缓存就没了），**不能作为长期依赖写死进启动脚本**。
  - 系统装了 `py.exe`（Windows Python launcher），但它指向的 Python **大概率没装项目依赖**。
- 所以一键启动必须自己解决「用哪个 Python + 依赖在不在 + 缺了自动装」。

## 范围边界

**做：**
- 新增 `start_editor.bat`（Windows 双击启动脚本，放项目根目录）。
- 脚本职责：定位可用 Python → 确保依赖已装（缺则自动 pip install）→ 确保有 plan.json（没有则给清晰提示）→ 启动 web_app.py → 自动打开默认浏览器到本地地址。
- `web_app.py` 做小增强：启动后可选自动打开浏览器（用 Python `webbrowser` 模块，比 .bat 里 sleep+start 更可靠）。加一个开关避免测试环境误开浏览器。
- README 增补「双击启动」说明，作为推荐方式，原命令行方式保留作为备选。

**不做：**
- 不改 web_app 的 API / 业务逻辑 / 文案逻辑。
- 不做打包成 exe（PyInstaller 之类）——那是更后期的事，本任务只做脚本级一键启动。
- 不做 Mac/Linux 启动脚本（用户是 Windows；可留 TODO）。
- 不碰部署/上线（那是独立的大阶段）。

## Python 定位策略（核心，按优先级）

启动脚本按以下顺序找一个「能用且装了依赖」的 Python：
1. 优先尝试系统 `py -3`（Windows launcher，最可移植、最稳）。
2. 其次 `python`（PATH 里的）。
3. 都没有时，给清晰中文提示：「未检测到 Python，请先安装 Python 3.10+（https://www.python.org/downloads/，安装时勾选 Add to PATH）」，然后暂停（pause）让用户看到信息，不要一闪而过。

**依赖保障**：选定 Python 后，先检测关键依赖是否可导入（如 `python -c "import flask"`）。缺失则自动 `python -m pip install -r requirements.txt`（提示用户「首次启动正在安装依赖，请稍候」）。装完再起服务。
- 不要写死 bundled Python 路径（不稳定）。让一键启动用系统 Python + 自动装依赖，这样可移植、换机器也能跑。

## 启动流程（start_editor.bat 期望行为）

```
1. 切到脚本所在目录（cd /d "%~dp0"）
2. 定位 Python（上面的策略），找不到 → 提示安装 + pause + 退出
3. 检测依赖，缺则 pip install -r requirements.txt
4. 检测 output\plan.json：
   - 不存在 → 提示「还没有可编辑的项目，请先生成一条视频（运行 run_workflow）」，
     给出生成命令，pause。（第一期不强求 .bat 里替用户生成，给清晰指引即可；可选做成问用户要不要跑一次 demo 生成）
5. 启动 web_app.py（浏览器自动打开交给 web_app 的 webbrowser 逻辑）
6. 控制台保留打印 http://127.0.0.1:5000，并提示「关闭此窗口即可停止」
```

## web_app.py 增强（自动开浏览器）

- 在 `main()` 起服务前，用 `webbrowser.open(f"http://{HOST}:{PORT}")` 自动打开默认浏览器。
- 注意时序：Flask `app.run` 会阻塞，所以要在 run 之前用一个**延迟/后台方式**触发 open（如 `threading.Timer(1.0, lambda: webbrowser.open(url)).start()`），等服务起来再开，避免浏览器先打开却连不上。
- 加开关：环境变量 `AI_VIDEO_NO_BROWSER=1` 时不自动开浏览器（测试 / check_project 用，避免 CI/自测时弹浏览器）。debug 仍关闭、仍绑 127.0.0.1。

## 测试要求
- 现有 `tests/test_web_app.py` 全部回归通过（自动开浏览器逻辑不能破坏 API 测试——测试里设 `AI_VIDEO_NO_BROWSER=1` 或不调 main()）。
- 不要求给 .bat 写自动化测试（脚本难测），但 Codex 要在本机手动验证双击/运行 .bat 能起服务并开浏览器，结果写进 HANDOFF。
- 四套既有单测回归通过。

## 验收标准（Codex 自检通过后改 T-009 → REVIEW）
1. 四套单测全过；test_web_app 在自动开浏览器逻辑加入后仍全过（测试环境不弹浏览器）。
2. 手动跑 `start_editor.bat`：能定位 Python、（首次）自动装依赖、起服务、自动打开浏览器到编辑页面。Codex 在 HANDOFF 记录实测情况。
3. 没装依赖的干净 Python 下，脚本能自动 pip install 跑通（或在 HANDOFF 说明如何验证的）。
4. 无 plan.json 时给清晰中文指引，不报错崩溃、不一闪而过（有 pause）。
5. `AI_VIDEO_NO_BROWSER=1` 时不弹浏览器，服务正常。
6. README 有「双击 start_editor.bat 即可」的说明。
7. `.\scripts\check_project.ps1` 通过（确保自动开浏览器没污染自测）。

## 已知坑提示
- **不要写死 bundled Python 路径**（`C:\Users\LCL\.cache\codex-runtimes\...`）——那是工具缓存，会变。用系统 py/python + 自动装依赖。
- .bat 中文输出可能乱码：脚本开头加 `chcp 65001 >nul` 切 UTF-8，中文提示才正常。
- Flask app.run 阻塞，自动开浏览器必须用 Timer/线程延迟触发，且要在 run 之前注册，否则浏览器先开会连不上。
- pip install 首次可能较慢，要给用户「正在安装依赖请稍候」提示，别让用户以为卡死。
- 脚本结尾遇错要 pause，否则双击运行时窗口一闪而过，用户看不到错误。
