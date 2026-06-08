# CozyVoice / CosyVoice 接入说明

这个 POC 目前已经把每个分镜的口播文案导出到：

```text
output/voiceover.txt
output/voiceover_segments/scene_01.txt
output/voiceover_segments/scene_02.txt
output/voiceover_segments/scene_03.txt
```

后续接 CozyVoice 时，推荐流程是：

```text
run_workflow.py
  -> 生成 voiceover_segments/*.txt
  -> CozyVoice 为每段生成 wav
  -> FFmpeg/Remotion 按分镜时间轴合成配音、字幕、BGM、画面
```

## 为什么不直接把 CozyVoice 下载进项目

CozyVoice 本地部署通常会涉及模型权重、Python 依赖和显卡/推理性能问题，体积和环境成本都比这个 POC 大很多。第一阶段更建议把它作为独立服务或独立目录部署，然后由本项目调用。

## 建议配置

不要把 API key 或模型路径写死在代码里，使用 `.env` 或系统环境变量：

```text
COSYVOICE_HOME=
COSYVOICE_MODEL=
COSYVOICE_SPEAKER=
```

## 什么时候接入最合适

先用当前 POC 跑通：

```text
店铺信息 + 图片
  -> 分镜
  -> 字幕
  -> 动态预览
```

等你确认视频结构可用，再接入 CozyVoice 生成正式配音。
