[English](README.md) | **简体中文**

# video-prep

把剪辑前那些没人想做的"体力活"自动化：剪掉静音停顿、自动生成字幕（任意语言，默认普通话）、
统一倍速、按文件名自然顺序拼接。每个素材输出一段干净的 `.mp4` + 对应的 `.srt`，
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
第一次运行会下载 Whisper 模型（默认 `large-v3-turbo` 约 1.6GB，比 `large-v3` 快约 2 倍，质量损失可忽略；要最高精度可用 `--model large-v3`），之后会用缓存。

## 安装

> **最省事：让你的编程 Agent 帮你装。** 如果你已经在用 Claude Code 或 Codex，
> 直接对它说：*"帮我从 github.com/lucyfengcl-art/video-prep 安装 video-prep 技能"*，
> 它会按各自平台跑对应步骤（Claude Code 装插件，Codex 装技能或 `uv tool install`）。
> 想自己手动装，见下面的命令。

### 在 Claude Code 里用（插件 + 技能）

```
/plugin marketplace add lucyfengcl-art/video-prep
/plugin install video-prep
```

装好后，直接对它说**"清理我的素材"**（或调用 `/video-prep:prep-clips`），
它就会跑整套清理流程。插件自带 Python 工具并通过 `uv` 运行，在任意文件夹都能用，
除了 `uv` + `ffmpeg` 不需要额外安装步骤。

### 在 Codex 或其他支持技能的 Agent 里用

两种方式：

- **安装技能** —— Codex 也能读同一个 `prep-clips` 技能。让它的 skill 安装器指向本仓库，
  就会装上 `skills/prep-clips/SKILL.md`（调用方式与平台无关，不依赖 Claude Code）。
- **安装命令行工具** —— `uv tool install git+https://github.com/lucyfengcl-art/video-prep`
  把 `video-prep-edit` 装到 `PATH`。仓库里的 [`AGENTS.md`](AGENTS.md) 是一个指向技能的简短入口，
  把它放进你存素材的项目里，支持 `AGENTS.md` 的 Agent 就知道有这个工具、并去读技能了解细节。

之后直接对它说**"清理我的素材"**即可。

## 一条命令搞定

素材按**文件名自然顺序**拼接，所以 `1.MOV`、`2.MOV`、……、`10.MOV` 会正确排序，无需补零（`01-`、`02-` 也可以）。
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

常用参数：`--language en`（或任意 Whisper 语言代码 / `auto` 自动识别，字幕换行会自动适配）、
`-j 3`（多核并行处理多段素材，约快 1.4 倍）、`--speed 1.3`（调整倍速，默认 1.1）。
素材很多时用一条命令跑完即可，**不要自己分批或两两合并**——工具会一次性剪辑、转写、归一化并拼接。

## 常用后续操作

- **删掉口头禅**（然后、就是… / um、uh…）——工具**先建议、你来定**：扫描后列出每处及上下文，
  在你用 `--indices` 选定之前不会删任何东西。`--word` 可省略（内置 `zh`/`en` 默认词表），
  匹配大小写不敏感，也支持多字词（于是、"you know"）：
  ```sh
  # 1. 扫描（--json 输出机器可读的匹配项，便于挑选）
  video-prep-cut-filler out/<日期>/final.mp4 --json
  # 2. 只删你选中的几处（或 --indices all）
  video-prep-cut-filler out/<日期>/final.mp4 --indices 1,4,5
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
