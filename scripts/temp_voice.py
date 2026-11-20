# -*- coding: utf-8 -*-
"""配音 + 时间线：script.json → voice/<id>.wav + timeline.json（画面全部挂在这份时间线的字上）

引擎（无 Kokoro——自然度不够，2026-11-20 移除）：
  - minimax：MINIMAX_API_KEY 存在时自动用，speech-2.8-hd 高清中文，音质天花板；带逐词时间戳
  - edge：免费兜底，默认 zh-CN-YunyangNeural（新闻播报男声，财经解说最合适）
  script.json 的 "tts_engine": "auto"(默认) | "minimax" | "edge"；命令行 --engine 覆盖。

配音一律：切首尾静音、原速（不用 atempo 事后加速）。句间停顿只由 gap 决定。
有正式配音（voice/<id>.final.wav）自动换上，--asr 用 faster-whisper 重新逐字对齐。

script.json：
{
  "voice": "zh-CN-YunyangNeural", "rate": "+0%", "pre": 0.3,
  "minimax_voice": "Chinese (Mandarin)_Reliable_Executive",
  "chapters": [{"after":"b01","title":"第一幕"}],
  "lines": [
    {"id":"b01","text":"...","en":"English translation","gap":0.35},
    {"id":"b10b","text":"难怪他总爱说这句：","gap":0.5,
     "bite":{"pre":0.15,"post":0.4,"parts":[["footage/jensen.m4a",101.6,1.95,"字幕",2.5]]}}
  ]
}
- say：只给 TTS 读的写法（数字、英文怎么念），不改屏上的 text
- en：中英双语字幕的英文行；多块用 | 分隔，与中文块一一对应
- bite：这句后插原声；pre：开头空多久；title：哪句后留片名时间

  python temp_voice.py film/script.json
  python temp_voice.py film/script.json --redo
  python temp_voice.py film/script.json --engine edge    # 强制 edge
  python temp_voice.py film/script.json --asr            # 正式配音后逐字对齐
"""
import asyncio, binascii, difflib, json, os, subprocess, sys, urllib.request, urllib.error
from pathlib import Path

SP = Path(sys.argv[1]).resolve(); D = SP.parent
S = json.loads(SP.read_text('utf-8'))
REDO, ASR = '--redo' in sys.argv, '--asr' in sys.argv
VOICE = S.get('voice', 'zh-CN-YunyangNeural')      # 新闻播报男声，比 Yunxi 更贴财经解说
RATE = S.get('rate', '+0%')
MM_VOICE = S.get('minimax_voice', 'Chinese (Mandarin)_Reliable_Executive')
MM_ENDPOINT = S.get('minimax_endpoint', 'https://api.minimaxi.com/v1/t2a_v2')
MM_MODEL = S.get('minimax_model', 'speech-2.8-hd')
ENGINE = S.get('tts_engine', 'auto')
if '--engine' in sys.argv: ENGINE = sys.argv[sys.argv.index('--engine') + 1]
HAS_KEY = bool(os.environ.get('MINIMAX_API_KEY', '').strip())
if ENGINE == 'auto': ENGINE = 'minimax' if HAS_KEY else 'edge'
if ENGINE not in ('minimax', 'edge'): raise SystemExit(f'未知引擎 {ENGINE}（minimax / edge）')
(D / 'voice').mkdir(exist_ok=True)
TRIM = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03"


def dur(f):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(f)]))


def lead_silence(f):
    out = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(f), '-af', 'silencedetect=n=-45dB:d=0.02', '-f', 'null', '-'], capture_output=True, text=True).stderr
    for ln in out.splitlines():
        if 'silence_end' in ln and 'silence_start: 0' in out.split('silence_end')[0][-60:]:
            return max(0.0, float(ln.split('silence_end:')[1].split('|')[0]) - .03)
    return 0.0


# ---- edge-tts：免费兜底，自带 WordBoundary ----
async def edge(text, mp3):
    import edge_tts
    last = None
    for attempt in range(4):                       # 微软服务偶尔超时，重试
        words = []
        try:
            com = edge_tts.Communicate(text, VOICE, rate=RATE, boundary='WordBoundary')
            with open(mp3, 'wb') as fp:
                async for ch in com.stream():
                    if ch['type'] == 'audio': fp.write(ch['data'])
                    elif ch['type'] == 'WordBoundary':
                        words.append([ch['text'], ch['offset'] / 1e7, (ch['offset'] + ch['duration']) / 1e7])
            if mp3.stat().st_size > 1000: return words
        except Exception as e:
            last = e
        import asyncio as _a; await _a.sleep(1 + attempt)
    raise SystemExit(f'edge-tts 重试 4 次仍失败：{last}')


# ---- MiniMax speech-2.8-hd：高清中文，带逐词时间戳（抄 wlzh/skills 的实现）----
def minimax(text, mp3, words_json):
    key = os.environ.get('MINIMAX_API_KEY', '').strip()
    if not key: raise SystemExit('MINIMAX_API_KEY 未设置')
    payload = {
        'model': MM_MODEL, 'text': text, 'stream': False,
        'voice_setting': {'voice_id': MM_VOICE, 'speed': float(S.get('speed', 1.0)),
                          'vol': float(S.get('volume', 1.0)), 'pitch': int(S.get('pitch', 0))},
        'audio_setting': {'sample_rate': 32000, 'bitrate': 128000, 'format': 'mp3', 'channel': 1},
        'subtitle_enable': True, 'subtitle_type': 'word',
    }
    req = urllib.request.Request(MM_ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read().decode('utf-8'))
    base = data.get('base_resp') or {}
    if base.get('status_code') not in (None, 0):
        raise SystemExit(f'MiniMax 错误 {base.get("status_code")}: {base.get("status_msg","")}')
    audio_hex = (data.get('data') or {}).get('audio')
    if not audio_hex: raise SystemExit('MiniMax 未返回音频')
    Path(mp3).write_bytes(binascii.unhexlify(audio_hex))
    words = []
    sub = (data.get('data') or {}).get('subtitle_file')
    if sub:                                   # 下载逐词时间戳
        try:
            with urllib.request.urlopen(sub, timeout=60) as r:
                segs = json.loads(r.read().decode('utf-8'))
            for seg in segs:
                words.append([str(seg.get('text', '')).strip(),
                              float(seg.get('time_begin', 0)), float(seg.get('time_end', 0))])
        except Exception as e:
            print('  MiniMax 字幕下载失败，退回按字插值：', e)
    if words: Path(words_json).write_text(json.dumps(words, ensure_ascii=False), encoding='utf-8')
    return words


def char_times(caption, words):
    seq = []
    for w, s, e in words:
        w = w.strip()
        for i, ch in enumerate(w): seq.append((ch, s + (e - s) * i / max(1, len(w))))
    a, b = list(caption), [c for c, _ in seq]; tm = [None] * len(a)
    for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size): tm[blk.a + k] = seq[blk.b + k][1]
    known = [i for i, x in enumerate(tm) if x is not None]
    for i in range(len(tm)):
        if tm[i] is None:
            p = max([k for k in known if k < i], default=None); n = min([k for k in known if k > i], default=None)
            tm[i] = (0 if p is None and n is None else (tm[n] - .12 * (n - i)) if p is None else (tm[p] + .12 * (i - p)) if n is None
                     else tm[p] + (tm[n] - tm[p]) * (i - p) / (n - p))
    for i in range(1, len(tm)): tm[i] = max(tm[i], tm[i - 1])
    return [max(0.0, x) for x in tm]


whisper = None
def asr_words(wav):
    global whisper
    if whisper is None:
        from faster_whisper import WhisperModel
        try: whisper = WhisperModel('large-v3', device='cuda', compute_type='float16')
        except Exception: whisper = WhisperModel('large-v3', device='cpu', compute_type='int8')
    segs, _ = whisper.transcribe(str(wav), language='zh', word_timestamps=True)
    return [[w.word, float(w.start), float(w.end)] for s in segs for w in s.words]


t = .15 + S.get('pre', 0.0); beats, inserts, title, chapters = [], [], None, []
meta_p = D / 'voice' / 'words.json'; meta = json.loads(meta_p.read_text('utf-8')) if meta_p.exists() else {}
for ln in S['lines']:
    lid, text = ln['id'], ln['text']; wav = D / 'voice' / f'{lid}.wav'; final = D / 'voice' / f'{lid}.final.wav'
    src_key = f"{ln.get('say', text)}|{ENGINE}|{VOICE if ENGINE=='edge' else MM_VOICE}|{RATE}|{final.exists()}"
    if REDO or not wav.exists() or meta.get(lid, {}).get('key') != src_key:
        if final.exists():
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(final), '-af', f'{TRIM},areverse,{TRIM},areverse', '-ar', '48000', '-ac', '1', str(wav)], check=True)
            words = asr_words(wav)
        elif ENGINE == 'minimax':
            mp3 = D / 'voice' / f'{lid}.mm.mp3'; wjp = D / 'voice' / f'{lid}.mmwords.json'
            words = minimax(ln.get('say', text), mp3, wjp)
            lead = lead_silence(mp3)
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(mp3), '-af', f'{TRIM},areverse,{TRIM},areverse', '-ar', '48000', '-ac', '1', str(wav)], check=True)
            words = [[w, s - lead, e - lead] for w, s, e in words]
        else:
            mp3 = D / 'voice' / f'{lid}.edge.mp3'; words = asyncio.run(edge(ln.get('say', text), mp3))
            lead = lead_silence(mp3)
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(mp3), '-af', f'{TRIM},areverse,{TRIM},areverse', '-ar', '48000', '-ac', '1', str(wav)], check=True)
            words = [[w, s - lead, e - lead] for w, s, e in words]
        meta[lid] = {'key': src_key, 'engine': ENGINE, 'words': words}
    elif ASR:
        meta[lid]['words'] = asr_words(wav)
    d = dur(wav); tm = char_times(text, meta[lid]['words'])
    beats.append({'id': lid, 'text': text, 'start': round(t, 4), 'end': round(t + d, 4), 'wav': f'voice/{lid}.wav',
                  'chars': [[c, round(t + x, 4)] for c, x in zip(text, tm)], 'en': ln.get('en', '')})
    for ch in S.get('chapters', []):
        if ch.get('after') == lid:
            chapters.append({'n': len(chapters) + 1, 'title': ch['title'], 'start': round(t, 4)})
    t += d + ln.get('gap', .35)
    if 'bite' in ln:
        bt = ln['bite']; t += bt.get('pre', .15) - ln.get('gap', .35); t0 = t; parts = []
        for src, a, l, sub, g in bt['parts']:
            parts.append({'src': src, 'in': a, 'dur': l, 'gain_db': g, 'start': round(t, 4), 'end': round(t + l, 4), 'sub': sub}); t += l
        inserts.append({'id': f'bite_{lid}', 'after': lid, 'start': round(t0, 4), 'end': round(t, 4), 'parts': parts}); t += bt.get('post', .4)
    if S.get('title', {}).get('after') == lid:
        title = {'start': round(t, 4), 'end': round(t + S['title']['len'], 4)}; t += S['title']['len']
meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=1), 'utf-8')
tl = {'fps': 30, 'duration': round(t + .95, 4), 'pre': S.get('pre', 0.0), 'title': title, 'beats': beats, 'inserts': inserts,
      'chapters': chapters, 'tts_engine': ENGINE, 'tts_voice': VOICE if ENGINE == 'edge' else MM_VOICE}
(D / 'timeline.json').write_text(json.dumps(tl, ensure_ascii=False, indent=1), 'utf-8')
for b in beats: print(f"{b['id']:6s} {b['start']:7.2f}–{b['end']:6.2f}  {b['text'][:28]}")
for i in inserts: print(f"{i['id']:6s} {i['start']:7.2f}–{i['end']:6.2f}  原声 {len(i['parts'])} 段")
print('总长', tl['duration'], '秒；片名', title, '；引擎', ENGINE, '；音色', tl['tts_voice'])
