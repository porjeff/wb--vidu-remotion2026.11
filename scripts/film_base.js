// film_base.js —— 每条片都一样的底座（不是镜头）：读时间线、按字取时刻、实拍取帧、镜头登记、按时刻找镜头、字幕、预加载。
// 载入顺序：stage25d.js → film_base.js → moves.js → film.js。画面一律在 film.js 里按这条片自己现写。
// 用法（film.js）：
//   window.ready=(async()=>{
//     const F=await FB.init({counts:['assets/clips/counts.json'],cuts:['jensen'],preload:['stage_navy.jpg'],fonts:['60px Shu','60px Num']});
//     const {cue,B,fr,clipSrc,shot}=F;
//     shot(0,B('b02'),t=>`...这一镜的画面...`);
//     ...
//     return F.go({frame:h=>`<div style="position:absolute;inset:0">${h}</div>`});   // frame 可选：给整帧统一包一层（调色、颗粒）
//   })();
// 时刻一律写成 cue(句id,'词')，不写死秒数；同一个 t 永远画出同一帧。
(()=>{
const C=x=>Math.max(0,Math.min(1,x));
const lat=s=>s.replace(/([A-Za-z0-9][A-Za-z0-9 .,$%-]*[A-Za-z0-9]|[A-Za-z0-9])/g,'<span class="lat">$1</span>');

async function init(o={}){
 const A=o.assets??'assets/';
 const T=await fetch(o.timeline??'timeline.json').then(r=>r.json());
 const stage=document.querySelector(o.stage??'#stage');
 const fit=()=>stage.style.transform=`scale(${Math.min(innerWidth/1920,innerHeight/1080)})`;addEventListener('resize',fit);fit();

 // 时间线：B(句) 开口、BE(句) 说完、cue(句,'词') 那个字的时刻；INS 原声插段
 const BT=Object.fromEntries(T.beats.map(b=>[b.id,b]));
 const need=id=>{if(!BT[id])throw Error(`timeline.json 里没有句子 ${id}`);return BT[id];};
 const B=id=>need(id).start,BE=id=>need(id).end;
 const cue=(id,s)=>{const b=need(id),i=b.text.indexOf(s);if(i<0)throw Error(`${id} 里找不到「${s}」`);return b.chars[i][1];};
 const INS=Object.fromEntries((T.inserts||[]).map(i=>[i.id,i]));

 // 实拍帧序列（footage.py extract 写的 counts.json）；没登记的片段直接报错，不出黑屏
 const CL={};
 for(const p of o.counts??[])Object.assign(CL,await fetch(p).then(r=>{if(!r.ok)throw Error('读不到 '+p);return r.json();}));
 const fr=(n,f)=>{if(!CL[n])throw Error(`实拍 ${n} 没有登记帧数（counts.json）`);return `${A}clips/${n}/${String(Math.max(1,Math.min(CL[n],Math.round(f)))).padStart(4,'0')}.jpg`;};
 const clipSrc=(n,t,t0,rate=1)=>fr(n,Math.floor(Math.max(0,t-t0)*30*rate)+1);

 // 抠像（matte.py + matte_clean.py 写的 box.json），之后用 S25.cutP
 if(o.cuts?.length)await S25.loadCuts(o.cuts,A+'cut/');
 await Promise.all((o.preload??[]).map(n=>new Promise(r=>{const im=new Image();im.onload=im.onerror=r;im.src=A+n;})));
 await Promise.all((o.fonts??[]).map(f=>document.fonts.load(f)));

 // 标准双语字幕（借鉴 bilingual-subtitle-skill 的 merge_bilingual：原文句和翻译句同一时间窗）。
 // 一句 = 一条记录 {start,end,zh,en}，中英整句同起止、同时出现、同时消失。
 // 不按字切块——块级切换容易漏字（之前 chars[..]?.[1] 的 bug 就是这么来的）。
 // 逐字时刻仍在 timeline 的 chars 里，cue() 照常用；字幕只按整句显示。
 // 描边用 16+8+4 方向 text-shadow 环（比 -webkit-text-stroke 干净，没有尖角刺）。
 function stroke(w=4,col='#000'){
  const ring=(r,k)=>Array.from({length:k},(_,i)=>{const a=(i/k)*Math.PI*2;
   return `${(Math.cos(a)*r).toFixed(1)}px ${(Math.sin(a)*r).toFixed(1)}px 0 ${col}`;});
  return [...ring(w,16),...ring(w*.6,8),...ring(w*.3,4)].join(',');}
 const ZH_STROKE=stroke(4),EN_STROKE=stroke(2,'#000');
 const SUBS=[...T.beats.map(b=>({start:b.start,end:b.end+.12,zh:b.text,en:b.en||''}))];
 for(const i of T.inserts||[])for(const p of i.parts)
  SUBS.push({start:p.start,end:p.end,zh:p.sub,en:p.en||''});
 SUBS.sort((a,b)=>a.start-b.start);
 // 字号自适应（借鉴 anything2explainer 的 fitSize）：中文按字数缩，保证一行放下，不折行压英文。
 // 60px 基准按 20 字算，每多 2 字缩 4px，最低 42px；英文按字符数缩，最低 22px。
 const fitZh=n=>Math.max(42,Math.min(60,Math.round(60*20/Math.max(20,n))));
 const fitEn=n=>Math.max(22,Math.min(30,Math.round(30*85/Math.max(85,n))));
 const subAt=t=>{
  const s=SUBS.find(x=>t>=x.start&&t<x.end);
  if(!s)return null;
  const zh=s.zh.replace(/[。]$/,''),en=s.en;
  const zs=fitZh(zh.length),es=fitEn(en.length);
  return {text:zh,en,
   html:`<div class="sub-wrap">`
     +`<div class="sub" style="font-size:${zs}px;text-shadow:${ZH_STROKE}">${lat(zh)}</div>`
     +(en?`<div class="sub-en" style="font-size:${es}px;text-shadow:${EN_STROKE}">${en}</div>`:'')
     +`</div>`};};

 // 章节进度条：timeline.json 有 chapters:[{n,title,start}] 才画，缺省不显示（向后兼容）。
 // 底部一条 6px 细线，已播部分高亮；只在章界显示章节名 1.2 秒。字幕在 y=936，不冲突。
 const CH=T.chapters||[];
 function progHTML(t){
  if(!CH.length)return '';
  const p=C(t/T.duration);
  let label='';
  for(const c of CH)if(t>=c.start&&t<c.start+1.2)label=c.title;
  return `<div class="prog"><div class="prog-fill" style="width:${(p*100).toFixed(2)}%"></div>`
    +CH.map(c=>`<div class="prog-tick" style="left:${(C(c.start/T.duration)*100).toFixed(2)}%"></div>`).join('')
    +(label?`<div class="prog-label">${label}</div>`:'')+`</div>`;}

 // 镜头登记：shot(起, 止, t=>这一帧的 HTML)
 const shots=[];const shot=(t0,t1,f)=>{shots.push({t0,t1,f});return f;};

 function go(g={}){
  // 镜头之间不能有空档或重叠（空档那一段会落到最后一镜上，画面跳）
  const ss=[...shots].sort((a,b)=>a.t0-b.t0),eps=1e-3;
  if(!ss.length)console.error('film.js 一个镜头都没有登记');
  else{if(ss[0].t0>eps)console.error(`0–${ss[0].t0.toFixed(2)} 秒没有镜头`);
   for(let i=0;i<ss.length-1;i++){const a=ss[i],b=ss[i+1];
    if(b.t0>a.t1+eps)console.error(`镜头之间有空档：${a.t1.toFixed(2)}–${b.t0.toFixed(2)}`);
    if(b.t0<a.t1-eps)console.error(`镜头重叠：${b.t0.toFixed(2)} 开始的镜头和上一镜（到 ${a.t1.toFixed(2)}）叠在一起`);}
   if(ss.at(-1).t1<T.duration-eps)console.error(`最后一镜在 ${ss.at(-1).t1.toFixed(2)} 结束，片长 ${T.duration}`);}
  const frame=g.frame??(h=>h),defs=g.defs??S25.DEFS;
  window.timeline=T;window.duration=T.duration;
  // dry=true：只算一遍这一帧（render.mjs --moves 用），不写进页面、不等图片
  window.seek=async(t,dry=false)=>{
   t=Math.max(0,Math.min(T.duration-1/300,t));
   const i=shots.findIndex(x=>t>=x.t0&&t<x.t1),k=i<0?shots.length-1:i,s=shots[k];
   FB.cur={shot:k,t};
   let h=s.f(t);const sub=subAt(t);if(sub)h+=sub.html;
   const prog=progHTML(t);
   if(dry)return {time:t,shot:k};
   stage.innerHTML=defs+frame(h)+prog;
   await Promise.all([...document.images].map(im=>im.decode().catch(()=>{})));await document.fonts.ready;
   return {time:t,shot:k,sub:sub?.text??''};
  };
  return window.seek(0);
 }

 const F={T,A,stage,C,B,BE,cue,INS,CL,fr,clipSrc,shot,shots,go,subAt};
 Object.assign(FB,{T,A,fr,clipSrc,CL,shots});
 return F;
}
window.FB={init,cur:{shot:0,t:0}};
})();
