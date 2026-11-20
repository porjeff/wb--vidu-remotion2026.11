# -*- coding: utf-8 -*-
"""字幕/数字一致性自检——每次出片前必跑，防止重犯 2026-11-20 的三类错误。

  python qc_subs.py <片子目录>

检查：
1. 英文字幕按 id 和中文一一对应（防整体错位——上次 zip 顺序错位的根因）
2. 英文字幕无反斜杠/斜杠残留（转义符会显示成画面上的多余符号）
3. 英文行长度 <= 95 字符（超了会折行压中文）
4. 画面大字的数字口径和英文一致（亿 vs billion：画面 $1300亿 配 英文 $130 billion 看着像错）
5. timeline 的英文和 script 的英文一致（改了 script 没重跑 temp_voice 会不同步）
"""
import sys, json, re
from pathlib import Path

D = Path(sys.argv[1]).resolve()
S = json.loads((D / 'script.json').read_text('utf-8'))
TL = json.loads((D / 'timeline.json').read_text('utf-8'))
errs, warns = [], []

lines = {l['id']: l for l in S['lines']}
beats = {b['id']: b for b in TL['beats']}

# 1. 按 id 对齐（不按顺序）
for lid, l in lines.items():
    b = beats.get(lid)
    if not b:
        errs.append(f'{lid}: timeline 缺这条 beat')
        continue
    if l['text'] != b['text']:
        errs.append(f'{lid}: 中文文案和 timeline 不一致（改了 script 没重配音？）')
    if (l.get('en') or '') != (b.get('en') or ''):
        errs.append(f'{lid}: 英文和 timeline 不一致（要重跑 temp_voice.py）')

# 2/3. 英文质量
for lid, l in lines.items():
    en = l.get('en', '')
    if not en:
        errs.append(f'{lid}: 缺英文字幕')
        continue
    if '\\' in en or '/' in en:
        errs.append(f'{lid}: 英文含多余斜杠/反斜杠 → {en[:50]}')
    if len(en) > 95:
        warns.append(f'{lid}: 英文 {len(en)} 字符，可能折行（>95）')

# 4. 数字口径：中文/画面用"亿"，英文用标准 billion（1亿 = 0.1 billion）。
#    中文 1300亿 ↔ 英文 $130 billion ↔ 画面 $1300亿。这是财经双语片的标准换算法。
filmjs = (D / 'film.js').read_text('utf-8') if (D / 'film.js').exists() else ''
bigs = re.findall(r"value:'(\$[^']*)'", filmjs)
for v in bigs:
    if '亿' not in v and any(c.isdigit() for c in v):
        errs.append(f'画面大字 {v} 没用中文"亿"口径——和中文文案数字对不上')

CN_NUM = {'一千一百五十八': 1158, '一千三百': 1300, '一千零七十六': 1076, '三百九十七': 397}
for lid, l in lines.items():
    t, en = l['text'], l.get('en', '')
    if '亿' in en:
        errs.append(f'{lid}: 英文句子里夹中文"亿"——英文要用 billion 标准换算（$1300亿 → $130 billion）')
    for cn, yi in CN_NUM.items():
        if cn + '亿' in t:
            want = yi / 10                       # 亿 → billion
            nums = [float(x) for x in re.findall(r'\$([\d.]+)\s*billion', en, re.I)]
            if nums and not any(abs(n - want) < 0.01 for n in nums):
                errs.append(f'{lid}: 中文"{cn}亿"(=${want}billion) 但英文写 {nums}——换算不一致')

print(f'## 字幕/数字 QC：{D.name}')
print(f'检查 {len(lines)} 句；错误 {len(errs)}，提醒 {len(warns)}')
if errs:
    print('\n### 错误（必须修）')
    for e in errs: print(' -', e)
if warns:
    print('\n### 提醒（看一眼）')
    for w in warns: print(' -', w)
if not errs and not warns: print('\n全过。')
sys.exit(1 if errs else 0)
