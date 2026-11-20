# TTS 方案对比（2026-11-20 调研）

Kokoro 已移除：82M 小模型中文自然度不够，公开评测原话"效果不好，不推荐使用"。下面是替代方案，按自然度/成本排序。

## 三档方案

| 方案 | 自然度 | 成本 | 离线 | 适合谁 |
|---|---|---|---|---|
| **MiniMax speech-2.8-hd** | ★★★★★ 天花板 | API 按量（有免费额度） | 否 | 要最好音质、愿意申请 key |
| **edge-tts YunyangNeural** | ★★★★ 新闻播报级 | 完全免费 | 否 | 零成本最优，当前默认 |
| **GPT-SoVITS / IndexTTS** | ★★★★★ 可克隆自己声音 | 免费开源 | 是 | 要专属音色、能接受慢 |

## 1. MiniMax（已接入，填 key 即用）

- 端点 `https://api.minimaxi.com/v1/t2a_v2`，模型 `speech-2.8-hd`
- 音色 `Chinese (Mandarin)_Reliable_Executive`（可靠高管，男声，财经解说绝配）
- 环境变量 `MINIMAX_API_KEY`，在 platform.minimaxi.com 申请
- 自带逐词时间戳（`subtitle_type: word`），字幕对齐更准
- 实现抄自 `wlzh/skills`（699 星）的 text-to-speech，MIT 思路
- 填了 key 后 `tts_engine: auto` 会自动切过去，无需改代码

## 2. edge-tts（当前默认，免费）

- `zh-CN-YunyangNeural`：新闻播报男声，专业可靠，财经解说最合适
- 其他男声：`YunjianNeural`（体育激情）、`YunxiNeural`（活泼，之前用的）、`YunxiaNeural`（可爱）
- 改 `script.json` 的 `"voice"` 即可切换
- 缺点：情绪表达偏平，非官方服务无 SLA

## 3. 本地开源（无独显不推荐）

- GPT-SoVITS（64k 星，MIT）：CPU 可跑但慢，5 秒零样本克隆，1 分钟微调更像
- IndexTTS 2.5（25k 星）：M4 上跑 2 分钟音频约 1 小时，太慢
- CosyVoice（24k 星）：要 N 卡 TensorRT 部署
- 评测结论：本地方案自然度普遍不如云端大模型，且慢

## 建议路径

1. **先用当前默认的 edge-Yunyang 出一版**，听是否满意（比之前的 Kokoro 明显好）
2. 要更好 → 申请 MiniMax key，填环境变量，重跑即可自动升级
3. 要专属音色 → 用 GPT-SoVITS 克隆自己的声音（需要 CPU 时间）

## 另：不想用云端 API 的折中

cloudflare 的 `kokoro`、本地 `piper` 都测过，自然度都不如 edge。edge 是免费方案里的天花板，不用再找了。
