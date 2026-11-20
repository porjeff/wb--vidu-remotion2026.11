# -*- coding: utf-8 -*-
"""量化帧 QC：从渲染出的帧序列逐镜量构图/运动指标，输出带严重度的自动问题清单。

借鉴 anything2explainer 的 frame_metrics 思路，适配本 skill 的深蓝织物底（不是黑底点阵）。
  python frame_metrics.py <片子目录> [--step 4] [--out <报告.md>]
  python frame_metrics.py <片子目录> --frames out/frames --step 4

输入：片子目录/out/ 下的帧序列（render.mjs --stills 或 --video 时可从 mp4 抽：
  ffmpeg -i out/visual_720.mp4 -vf fps=4 out/frames/f_%05d.jpg）
输出：每镜的 主体尺度、空场最长帧、字幕带占用、最长静止帧、标记（高/中/低）。

依赖：numpy、Pillow（skill 已有）。不依赖 scipy。
判据（对应 references/rules.md）：
  高  连续空场 > 1.5s（主体<80px 且无大面积光）
  中  连续空场 > 1.0s；字幕带(y>=900)有亮元素；静止 > 3s
  低  主体偏小(<120px)持续；亮度异常
注意：这是量化体检，标记不等于缺陷——每条都要答得出"为什么这里就该这样"，
答不上才改。审查流程见 references/review.md。
"""
import sys, json, argparse
from pathlib import Path
import numpy as np
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument('film')
ap.add_argument('--frames', default=None, help='帧目录（缺省 <film>/out/frames）')
ap.add_argument('--step', type=int, default=4, help='采样步长（帧）')
ap.add_argument('--fps', type=float, default=30)
ap.add_argument('--out', default=None)
ap.add_argument('--h', type=int, default=720, help='帧高（720p）')
a = ap.parse_args()

D = Path(a.film).resolve()
FR = Path(a.frames).resolve() if a.frames else D / 'out' / 'frames'
TL = json.loads((D / 'timeline.json').read_text('utf-8'))
FPS = a.fps; H = a.h
frames = sorted(FR.glob('f_*.jpg')) or sorted(FR.glob('*.jpg'))
if not frames:
    sys.exit(f'没有帧：{FR}。先抽帧：ffmpeg -i {D}/out/visual_720.mp4 -vf fps=4 {FR}/f_%05d.jpg')

def load(p):
    im = Image.open(p).convert('L'); im.thumbnail((320, 180))
    return np.asarray(im, dtype=np.int16)

imgs = [load(p) for p in frames]
idx = np.arange(0, len(frames), max(1, a.step))
# 字幕在 y=936 起、字高约 60px（到 ~1002）。检测"画面元素侵入字幕带"只看字幕下方的
# y>=1010（缩略 0.936）——字幕本身不在这里，真正侵入的图形/大字才会。
sub_row = int(180 * 0.936)

# 指标
def metrics(i):
    g = imgs[i]
    bright = g > 130
    bright_ink = int(bright.sum())
    # 主体尺度：亮像素的最大连通块近似（用行/列投影，避免 scipy）
    rows = bright.sum(1); cols = bright.sum(0)
    active_rows = np.where(rows > 4)[0]
    hero_h = (active_rows.max() - active_rows.min() + 1) if len(active_rows) else 0
    sub_ink = int(bright[sub_row:, :].sum())
    return hero_h, sub_ink, bright_ink

M = [metrics(i) for i in idx]
hero = [m[0] for m in M]; sub = [m[1] for m in M]; ink = [m[2] for m in M]

def longest_run(flags, step):
    best = run = 0
    for f in flags:
        run = run + 1 if f else 0
        best = max(best, run)
    return best * step / FPS

empty_run = longest_run([h < 12 for h in hero], a.step)      # 缩略图 12px ≈ 原 48px
sub_run = longest_run([s > 200 for s in sub], a.step)
# 静止：相邻采样帧差异极小
diffs = [float(np.abs(imgs[idx[k]].astype(np.int16) - imgs[idx[k-1]].astype(np.int16)).mean()) for k in range(1, len(idx))]
still_run = longest_run([d < 0.6 for d in diffs], a.step) if diffs else 0

flags = []
def add(sev, msg): flags.append((sev, msg))
if empty_run > 1.5: add('高', f'连续空场 {empty_run:.1f}s（无主体）')
elif empty_run > 1.0: add('中', f'空场 {empty_run:.1f}s')
# 长字幕本身会下探到 y>1010，这里只标记"明显侵入"（亮像素 > 200 的帧），且降级为低：
# 本 skill 字幕 60px 偏大，这个指标信噪比不高，真要看还是得看 sheet。
if sub_run > 1.0: add('低', f'字幕带下方疑似有内容 {sub_run:.1f}s（长字幕也会命中，看 sheet 确认）')
if still_run > 3.0: add('中', f'画面静止 {still_run:.1f}s（>3s）')
med_hero = float(np.median(hero))
if med_hero < 20: add('低', f'主体偏小（缩略中位 {med_hero:.0f}px）')

lines = [f'# 量化帧 QC：{D.name}', '',
         f'帧目录 `{FR}`，采样 {len(idx)} 帧（步长 {a.step}）。',
         f'- 主体高度中位数：{med_hero:.0f}px（缩略图，满高 180）',
         f'- 最长空场：{empty_run:.2f}s',
         f'- 字幕带占用最长：{sub_run:.2f}s',
         f'- 最长静止：{still_run:.2f}s', '',
         '## 自动标记', '']
if flags:
    for sev, msg in flags: lines.append(f'- **{sev}**：{msg}')
else:
    lines.append('- 无自动标记（仍需人工看 sheet 和连续帧）')
lines += ['', '## 怎么看', '量化标记不是判决。对照 `references/rules.md`，每条问一句',
          '"这一镜为什么就该这样"。答不上才改。人工复查仍要看 `--sheet` 和 `strip.py` 连续帧。']
report = '\n'.join(lines) + '\n'
out = Path(a.out).resolve() if a.out else D / 'out' / 'frame_metrics.md'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(report, encoding='utf-8')
print(report)
print('报告：', out)
