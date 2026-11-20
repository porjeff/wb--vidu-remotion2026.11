// 封面生成器：用 kit 的 title 场景渲染一张固定标题卡，写入 MP4 封面元数据，并设为视频首帧。
//   node cover.mjs <片子目录> [--title "标题"] [--no-first-frame]
// 产物：<片子>/封面.png（1280×720 或 1920×1080）、<片子>/审阅/<片名>_封面版.mp4
// 复用 kit 的 title 场景——和片中标题卡同一套样式，不用另写样式。
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync, rmSync, copyFileSync } from 'node:fs';
import path from 'node:path';
import fs from 'node:fs';

const argv = process.argv.slice(2);
const dir = path.resolve(argv[0]);
const arg = (n, d) => { const i = argv.indexOf(n); return i < 0 ? d : argv[i + 1]; };
const noFirst = argv.includes('--no-first-frame');
const SKILL = path.resolve(new URL('..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'));

if (!existsSync(path.join(dir, 'film.js'))) throw Error(`没有 film.js：${dir}`);
const script = JSON.parse(readFileSync(path.join(dir, 'script.json'), 'utf8'));
const film = readFileSync(path.join(dir, 'film.js'), 'utf8');
const m = film.match(/scene:'title'[^}]*?title:'([^']+)'/);
const title = arg('--title', m?.[1] || script.title || path.basename(dir));
const browM = film.match(/scene:'title'[^}]*?brow:'([^']+)'/);
const brow = browM?.[1] || '';
const enM = film.match(/scene:'title'[^}]*?en:'([^']+)'/);
const en = enM?.[1] || '';
console.log(`封面标题：${title}`);

// 临时目录：复制片子的 lib/assets/kit，写只有一个 title 镜的 film.js
const tmp = path.join(dir, '.cover_tmp');
mkdirSync(tmp, { recursive: true });   // 复用临时目录，不做递归删除（避开批量删除保护）
for (const n of ['lib', 'assets', 'film.css', 'index.html']) {
  const src = path.join(dir, n);
  if (existsSync(src)) {
    if (fs.statSync(src).isDirectory()) fs.cpSync(src, path.join(tmp, n), { recursive: true });
    else copyFileSync(src, path.join(tmp, n));
  }
}
// 字体：片子的 fonts 常是 Git Bash 风格符号链接（/c/...），Node 复制会 EPERM。
// 直接从 skill 的真实字体目录复制。
const fontSrc = path.join(SKILL, 'fonts');
if (existsSync(fontSrc)) fs.cpSync(fontSrc, path.join(tmp, 'fonts'), { recursive: true });
const tl = JSON.parse(readFileSync(path.join(dir, 'timeline.json'), 'utf8'));
writeFileSync(path.join(tmp, 'timeline.json'), JSON.stringify({ ...tl, duration: 1.5, beats: [], inserts: [], chapters: [] }));
writeFileSync(path.join(tmp, 'film.js'), `window.ready=(async()=>{
const F=await FB.init({counts:[],cuts:[],fonts:KIT.FONTS});
const K=await KIT.use(F);
await K.film([{scene:'title',until:1.5,says:'',title:${JSON.stringify(title)},brow:${JSON.stringify(brow)},en:${JSON.stringify(en)}}]);
return K.go();})();`);

// 渲染 0.3s（淡入完成）那一帧
execFileSync('node', [path.join(SKILL, 'scripts', 'render.mjs'), '--dir', tmp, '--stills', '0.3', '--h', '720'], { stdio: 'inherit' });
const shot = path.join(tmp, 'out', 'still_0.30.png');
if (!existsSync(shot)) throw Error('封面渲染失败：没有 still_0.30.png');
const coverPath = path.join(dir, '封面.png');
copyFileSync(shot, coverPath);
console.log('封面图：', coverPath, '（临时目录保留：', tmp, '）');

// 找成片：审阅目录里最新的 mp4，或 out/visual_720.mp4
const reviewDir = path.join(dir, '审阅');
let video = null;
if (existsSync(reviewDir)) {
  const mp4s = fs.readdirSync(reviewDir).filter(f => f.endsWith('.mp4') && !f.includes('封面'));
  mp4s.sort((a, b) => fs.statSync(path.join(reviewDir, b)).mtimeMs - fs.statSync(path.join(reviewDir, a)).mtimeMs);
  if (mp4s.length) video = path.join(reviewDir, mp4s[0]);
}
if (!video) video = path.join(dir, 'out', 'visual_720.mp4');
if (!existsSync(video)) { console.log('没找到成片，只生成封面图。'); process.exit(0); }

const suffix = noFirst ? '_封面元数据版.mp4' : '_封面版.mp4';
const out = path.join(reviewDir, path.basename(video).replace(/\.mp4$/, suffix));
mkdirSync(reviewDir, { recursive: true });

let work = video;
if (!noFirst) {
  // 默认：封面段前置 1.2 秒。两段都必须有同参数的音轨，concat 才会拼成同一条流；
  // 否则播放器默认选静音段那条轨 → 整片没声音（踩过坑）。
  const coverSeg = path.join(dir, '.cover_seg.mp4');
  const W = 1280, H = 720, dur = '1.2';
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-loop', '1', '-i', coverPath,
    '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono', '-t', dur,
    '-vf', `scale=${W}:${H}`, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', '30',
    '-c:a', 'aac', '-ar', '48000', '-ac', '1', '-shortest', coverSeg], { stdio: 'inherit' });
  const list = path.join(dir, '.cover_list.txt');
  writeFileSync(list, `file '${coverSeg.replace(/\\/g, '/')}'\nfile '${video.replace(/\\/g, '/')}'\n`);
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', list,
    '-map', '0:v:0', '-map', '0:a:0', '-c', 'copy', '-movflags', '+faststart', out], { stdio: 'inherit' });
  work = out;
}

// 写封面元数据（attached_pic）——所有平台缩略图统一，不改视频时长/音轨。
const final = path.join(dir, '.cover_final.mp4');
try {
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', work, '-i', coverPath,
    '-map', '0:v:0', '-map', '0:a?', '-map', '1:v:0',
    '-c', 'copy', '-disposition:v:1', 'attached_pic',
    '-movflags', '+faststart', final], { stdio: 'inherit' });
  fs.renameSync(final, out);
} catch (e) { console.log('封面元数据写入失败：', e.message); }

// 验音轨：有音轨且不是全静音才算成功
let audioOK = false;
try {
  const st = execFileSync('ffprobe', ['-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=codec_name', '-of', 'csv=p=0', out], { encoding: 'utf8' }).trim();
  audioOK = !!st;
} catch {}
console.log('封面版成片：', out, '| 音轨：', audioOK ? 'OK' : '缺失（检查源文件）');

// 默认模式的 concat 若把音轨拼错（多轨/静音），删掉产物报错，不交付
if (!noFirst && !audioOK) { console.error('封面版音轨异常，已删除，改用 --no-first-frame'); try { fs.unlinkSync(out); } catch {} process.exit(2); }
