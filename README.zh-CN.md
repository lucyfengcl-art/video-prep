[English](README.md) | **简体中文**

# video-prep

把剪辑前那些没人想做的"体力活"自动化：剪掉静音停顿、自动生成字幕（任意语言，默认普通话）、
统一倍速、按文件名顺序拼接。每个素材输出一段干净的 `.mp4` + 对应的 `.srt`，
直接拖进你常用的剪辑软件（剪映 / Premiere / DaVinci…）做真正的排版、转场和润色。

这是**前期清理，不是创作性剪辑**——排列、转场、配乐、风格仍然交给你自己的流程。
正因为这套清理几乎每种视频都要做，所以把它单独拆出来做成一个工具。

> 想看完整文档（进阶参数、可组合的building blocks 等），见 [English README](README.md)。

## 环境要求（装一次即可）

工具用 `uv` 来管理 Python 和依赖，**不用手动装 Python 包**。机器上需要：

- 任意系统（macOS / Windows / Linux，Intel 或 ARM）——转写用 `faster-whisper`，
  纯 CPU 即可运行；有 NVIDIA(CUDA) 显卡会自动加速
- `uv` —— `curl -LsSf https://astral.sh/uv/install.sh | sh`
- `ffmpeg`（剪静音 / 变速 / 拼接）—— `brew install ffmpeg`
- `ffmpeg-full`（把字幕烧进画面，可选）—— `brew install ffmpeg-full`，
  再装一个中文字体：`brew install --cask font-noto-sans-cjk-sc && fc-cache -f`

字幕默认是普通话（`--language zh`）；加 `--language` 换成任意 Whisper 支持的语言即可。
第一次运行会下载 Whisper 模型（`large-v3` 约 3GB），之后会用缓存。

## 安装

### 在 Claude Code 里用（插件 + 技能）

```
/plugin marketplace add lucyfengcl-art/video-prep
/plugin install video-prep
```

装好后，直接对它说**"清理我的素材"**（或调用 `/video-prep:prep-clips`），
它就会跑整套清理流程。插件自带 Python 工具并通过 `uv` 运行，在任意文件夹都能用，
除了 `uv` + `ffmpeg` 不需要额外安装步骤。

### 在 Codex 或其他命令行 Agent 里用

Codex 没有插件系统，先把命令行工具装一次：

```sh
uv tool install git+https://github.com/lucyfengcl-art/video-prep
```

仓库里的 [`AGENTS.md`](AGENTS.md) 会告诉 Codex 什么时候、怎么调用 `video-prep-edit`。

## 一条命令搞定

素材按**文件名顺序**拼接，所以用 `1.MOV`、`2.MOV`（或 `01-...`、`02-...`）来定顺序。
把素材放进 `./raw/`，然后：

```sh
video-prep-edit ./raw
```

结果都写进 `out/<当天日期>/`：

- `NN.processed.mp4` + `NN.srt` —— 每段素材清理后的版本（**主要交付物**，拖进剪辑软件用这些）
- `final.mp4` + `final.srt` —— 按顺序拼好的整段（如果你只想要一个文件）
- `final.subbed.mp4` —— 烧好字幕的合并版，**可选预览**，用来看节奏或直接分享

重复运行会复用同一个日期文件夹，只重新处理改动过的素材。
如果没装 `ffmpeg-full`，依然会生成清理后的素材和 `.srt`，只是跳过烧字幕的预览。

## 常用后续操作

- **删掉口头禅**（然后、就是、于是…），多字词也支持，还能只删某一处：
  ```sh
  video-prep-cut-filler out/<日期>/final.mp4 --word 于是 --dry-run   # 先列出所有出现的位置
  video-prep-cut-filler out/<日期>/final.mp4 --word 于是 --indices 3 # 只删第 3 处
  ```
- **重新烧 / 调整字幕样式**：
  ```sh
  video-prep-burn out/<日期>/final.mp4 --srt out/<日期>/final.srt \
      --font-size 18 --outline 2 --margin-v 100
  ```

## 想改成自己的流程？

这个技能刻意只做"清理"这一步。想在上面搭更完整的流程，参考 [English README](README.md)
里的 **Customize and extend** 一节——传不同参数、写你自己的技能、或者 fork 仓库，
都不用改动已安装的插件本体。

## 许可

[MIT](LICENSE)
