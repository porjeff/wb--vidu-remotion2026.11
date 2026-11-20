# wallstreet-explainer

让 AI 做华尔街风格的财经解读短片：真实的新闻和画面，金色大数字，深蓝织物底，镜头一直在走。

<img src="examples/gold-rates/sample.gif" alt="真人口播样片" width="100%">

**真人口播版**：《打仗了，黄金为什么反而跌》，29 秒。主持人是 AI 生成的数字人。

<img src="examples/ai-burn-money/sample.gif" alt="无人出镜样片" width="100%">

**无人出镜版**：《AI 到底有多烧钱》，77 秒，GIF 是前 29 秒。

GIF 没有声音。片中新闻截图和实拍为引用，出处见 [CREDITS.md](examples/ai-burn-money/CREDITS.md)。

## 能做什么

给它一个选题，它会自己写文案、找素材、配音、出片。

- 有口播视频（真人或数字人），就围着人做：证据挂在人身后的墙上，讲细节时人缩到角上的小窗。
- 没有口播视频，就把新闻里的当事人抠出来，站在大字前面。
- 素材自己去视频网站找，新闻网页自己截，关键句刷黄。
- 数字和钱的关系用大字、柱子、图表演出来。

## 安装

最简单：把这个仓库链接发给你的 AI 工具，让它装。

Claude Code 手动装：

```bash
git clone https://github.com/HeyChengC/wallstreet-explainer.git ~/.claude/skills/wallstreet-explainer
cd ~/.claude/skills/wallstreet-explainer
pip install -r requirements.txt
npm install && npx playwright install chromium
```

另外要装 ffmpeg 并放进 PATH。

字体要自己下，放进 `fonts/`：MiSans、阿里妈妈数黑体、Bebas Neue、Montserrat、Noto Sans SC。文件名和 `kit/kit.css` 里的对上。

## 使用

重启 Claude Code，直接说：

> 用 wallstreet-explainer 做一条 1 分钟的片子，讲 AI 到底有多烧钱

有口播视频就一起发给它。没有的话，它先配音（见下），画面定了再换成你的配音。

## 本机定制（2026-11-20）

- **TTS：MiniMax 高清优先，edge 免费兜底**（Kokoro 已彻底移除——自然度不够，2026-11-20 评测确认"效果不好，不推荐"）。
  - `script.json` 的 `tts_engine`：`"auto"`（默认，有 `MINIMAX_API_KEY` 就用 MiniMax，否则 edge）、`"minimax"`、`"edge"`。命令行 `--engine edge` 强制。
  - **MiniMax `speech-2.8-hd`**：中文旁白自然度天花板，带逐词时间戳。设置环境变量 `MINIMAX_API_KEY`（在 platform.minimaxi.com 申请），音色默认 `Chinese (Mandarin)_Reliable_Executive`（可靠高管男声，财经解说合适），`minimax_voice` 可改。
  - **edge-tts**：免费兜底，默认 `zh-CN-YunyangNeural`（新闻播报男声，比 Yunxi 更贴财经）。要换音色改 `"voice"`（Yunjian 激情/Yunxi 活泼/Yunxia 可爱）。
  - 实现借鉴 `wlzh/skills` 的多引擎 TTS（MiniMax 端点 `api.minimaxi.com/v1/t2a_v2`、hex 音频、逐词字幕）。方案对比见 `references/tts-options.md`。
- **固定封面**：出片后跑 `node scripts/cover.mjs <片子目录> --no-first-frame`——用 kit 的 title 场景渲染片名卡，写进 MP4 封面元数据，不改时长/音轨。产物 `封面.png` + `审阅/xxx_封面元数据版.mp4`。
- **多代理并行建镜**：长片按 `references/parallel-build.md` 分组派代理，解决镜头过长、切点太少。
- **出片前必跑字幕 QC**：`python scripts/qc_subs.py <片子目录>`，按 id 核对中英文字幕一一对应、无斜杠、画面大字与英文数字口径一致。
  - **数字口径按语言分工**：中文文案和画面大字用"亿"（`$1300亿`），英文用标准 billion（`$130 billion`，1亿=0.1billion）。英文句子里不夹中文单位。
- **量化帧 QC**：`python scripts/frame_metrics.py <片子目录>` 自动出空场/静止/字幕带占用清单，报告在 `out/frame_metrics.md`。
- **章节进度条 + 中英双语字幕**：`script.json` 加 `"chapters":[{"after":"句id","title":"章名"}]` 画底部进度条；每行加 `"en":"English translation"` 出英文小字。
  - 标准双语：一句一条记录 `{start,end,zh,en}`，中英整句同起止、同时出现消失。中文主行 + 英文副行包在 `.sub-wrap` 里整体贴底居中。不按字切块——块级切换曾导致"念了不显示"。
  - 字号自适应（借鉴 anything2explainer 的 `fitSize`）：中文按字数缩（60→42px）、英文按字符缩（30→22px），`white-space:nowrap` 保证单行不折行。
  - 描边用 16+8+4 方向 `text-shadow` 环（比 `-webkit-text-stroke` 干净无尖角刺）。
  - 注意：`new_film.mjs <片子> --sync` 会用新的 `lib/film_base.js` 但**不会**更新片子根目录的 `film.css`；老片子要手动把 `starter/film.css` 里的 `.prog` 和 `.sub-wrap` 样式拷进片子的 `film.css`。

## 常见问题

| 问题 | 办法 |
|---|---|
| yt-dlp、edge-tts 报 403 | `pip install -U yt-dlp edge-tts` |
| 抠人报错 | 装 `onnxruntime-gpu`（N 卡）或 `onnxruntime` |
| 逐字对齐太慢 | 用 N 卡跑 faster-whisper |
| 字体不在 `fonts/` | 在 `scripts/local.json` 写 `"fonts_dir": "<路径>"` |
| Playwright 装在别处 | 设环境变量 `PLAYWRIGHT_FROM` |

## 目录

| 位置 | 内容 |
|---|---|
| `SKILL.md` | AI 读的入口 |
| `references/` | 做片的方法和规矩 |
| `scripts/` | 下片、截图、配音、抠像、渲染、混音 |
| `kit/` | 现成场景模板 |
| `starter/` | 新片起点 |
| `examples/` | 样片的文案和画面代码 |

## 版权

素材只用于评论和解读，每条片在简介里写清出处。代码和文档是 MIT 协议，见 [LICENSE](LICENSE)。样片里的第三方画面、截图、logo 和人物不在 MIT 范围内。

## 联系

微信：Yangdavee（加的时候备注来意）

## 友情链接

[LINUX DO](https://linux.do/)
