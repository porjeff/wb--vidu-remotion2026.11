# wallstreet-explainer

> 让 AI 做华尔街风格的财经解读短片：真实新闻画面、金色大数字、深蓝织物底、镜头一直在走。

**当前版本 v2.3**（2026-11-20）· [更新记录 CHANGELOG](CHANGELOG.md) · 许可证见 [LICENSE](LICENSE)

## 它能做什么

给一个选题，它自己写文案、找素材、配音、出片。两种模式：

- **真人口播**：给了口播视频（真人或数字人），证据挂人身后的墙上，讲细节时人缩到角上小窗。
- **无人出镜**：没口播视频，把新闻当事人抠出来站在大字前面，或纯动效包装。

中英双语字幕、章节进度条、固定片名封面都内置。成片例子见 `examples/` 目录。

## 安装

最简单：把本仓库链接发给你的 AI 工具，让它装。

手动装（Claude Code）：

```bash
git clone https://github.com/porjeff/wb--vidu-remotion2026.11.git ~/.claude/skills/wallstreet-explainer
cd ~/.claude/skills/wallstreet-explainer
pip install -r requirements.txt
npm install && npx playwright install chromium
```

另外要装 `ffmpeg` 并放进 PATH。字体自己下好放进 `fonts/`：MiSans、阿里妈妈数黑体、Bebas Neue、Montserrat、Noto Sans SC（文件名要和 `kit/kit.css` 对上）。

## 使用

重启 AI 工具，直接说：

> 用 wallstreet-explainer 做一条 1 分钟的片子，讲 AI 到底有多烧钱

有口播视频就一起发给它。没有的话，它先配音，画面定了再换成你的录音。

## v2.3 新增 / 修复

| 项 | 说明 |
|---|---|
| **标准双语字幕** | 中文主行 + 英文副行，整句同起止、字号自适应不折行。修掉了"念了不显示""英文有斜杠""翻译整体错位"三个 bug。 |
| **字幕 QC 自检** | `scripts/qc_subs.py`，出片前按 id 核对中英对齐、斜杠残留、数字口径。错误必须为 0。 |
| **TTS 换引擎** | 移除 Kokoro（自然度不够）。MiniMax `speech-2.8-hd` 高清优先（需 `MINIMAX_API_KEY`），edge-tts 免费兜底（默认 Yunyang 新闻播报男声）。 |
| **固定片名封面** | `scripts/cover.mjs`，把片名写成 MP4 封面元数据，不改视频时长和音轨。 |
| **多代理并行建镜** | 长片按 `references/parallel-build.md` 分组，解决镜头过长、切点太少。 |

数字口径约定：中文和画面用"亿"（`$1300亿`），英文用标准 billion（`$130 billion`，1 亿 = 0.1 billion）。英文句子里不夹中文单位。

## 配置

- **TTS**：`script.json` 写 `"tts_engine": "auto" | "minimax" | "edge"`。auto = 有 `MINIMAX_API_KEY` 用 MiniMax，否则 edge。音色改 `"voice"`（edge）或 `"minimax_voice"`。
- **双语字幕**：每行写 `"en": "English translation"`；章节写 `"chapters":[{"after":"句id","title":"章名"}]`。
- **封面**：出片后跑 `node scripts/cover.mjs <片子目录> --no-first-frame`，产物 `封面.png` 和 `审阅/xxx_封面元数据版.mp4`。
- 更多本机细节和踩坑见 [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md)。

## 常见问题

| 问题 | 办法 |
|---|---|
| yt-dlp、edge-tts 报 403 | `pip install -U yt-dlp edge-tts` |
| 抠人报错 | 装 `onnxruntime-gpu`（N 卡）或 `onnxruntime` |
| 逐字对齐太慢 | 用 N 卡跑 faster-whisper |
| 字体不在 `fonts/` | 在 `scripts/local.json` 写 `"fonts_dir": "<路径>"` |
| Playwright 装在别处 | 设环境变量 `PLAYWRIGHT_FROM` |
| 封面版视频没声音 | 别用前置封面段那版；用 `--no-first-frame` 的元数据版 |

## 目录

| 位置 | 内容 |
|---|---|
| `SKILL.md` | AI 读的入口：流程、规矩、工具表 |
| `references/` | 做片方法（选题、钩子、并行建镜、TTS 方案对比） |
| `scripts/` | 配音、渲染、混音、QC、封面 |
| `kit/` | 现成场景模板（大数字、图表、抠像、口播层……） |
| `starter/` | 新片子的基础文件 |
| `examples/` | 成片例子 |
| `docs/` | 本机配置细节 |
