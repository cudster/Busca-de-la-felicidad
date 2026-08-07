#!/usr/bin/env python3
"""
Epic.Plane — Generador del deck de revisión (estilo Tinder) para el celular.

Lee la Google Sheet, descarga las fotos (las embebe como data URI para que se
vean solas, sin links ni clicks) y arma una página HTML de swipe:
  - swipe derecha = aprobar, izquierda = rechazar, arriba/botón = feedback
  - al final, un botón "Copiar decisiones" para pegar en el chat.

Salida: review_deck.html (Claude la publica como Artifact para abrir en el celular).

Uso:
    python3 review_deck.py --month 2026-08
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")
PILLAR_ES = {
    "technical_awe": "Asombro técnico", "spotting": "Spotting",
    "aviation_story": "Historia", "pilot_path": "Camino del piloto",
}


def fetch_posts(month: str) -> list[dict]:
    import sheets
    _, ws = sheets.get_worksheet()
    formulas = ws.get_values(value_render_option="FORMULA")
    values = ws.get_values(value_render_option="FORMATTED_VALUE")
    hdr = formulas[0]
    ix = {h: i for i, h in enumerate(hdr)}
    posts = []
    for fr, vr in zip(formulas[1:], values[1:]):
        def g(row, col):
            i = ix.get(col)
            return row[i] if i is not None and i < len(row) else ""
        pid = g(vr, "id")
        if not pid:
            continue
        # URL de la miniatura, extraída de =HYPERLINK("url","ver foto") o =IMAGE("url")
        prev_formula = g(fr, "preview")
        m = re.search(r'"(https?://[^"]+)"', prev_formula)
        img_url = m.group(1) if m else (g(fr, "asset_path").split(",")[0])
        posts.append({
            "id": pid,
            "num": pid.rsplit("-", 1)[-1],
            "type": g(vr, "type"),
            "pillar": PILLAR_ES.get(g(vr, "pillar"), g(vr, "pillar")),
            "cta": g(vr, "cta"),
            "caption_es": g(vr, "caption_es"),
            "caption_en": g(vr, "caption_en"),
            "hashtags": g(vr, "hashtags"),
            "img_url": img_url,
        })
    return posts


def to_data_uri(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=45) as r:
            raw = r.read()
        b64 = base64.b64encode(raw).decode()
        return f"data:image/jpeg;base64,{b64}"
    except Exception as e:
        print(f"   ⚠️  no pude bajar {url[:50]}…: {e}")
        return ""


HTML = r"""<meta charset="utf-8">
<style>
  :root{
    --bg:#0b0f17; --card:#141b28; --edge:#232c3d; --text:#eef2f7; --muted:#93a1b5;
    --approve:#22c55e; --reject:#f43f5e; --feedback:#f59e0b; --accent:#38bdf8;
    --radius:20px;
  }
  *{box-sizing:border-box; -webkit-tap-highlight-color:transparent;}
  #ep{position:relative; max-width:520px; margin:0 auto; height:100dvh;
    display:flex; flex-direction:column; background:var(--bg); color:var(--text);
    font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; overflow:hidden;}
  .top{display:flex; align-items:center; gap:12px; padding:12px 16px;}
  .count{font-variant-numeric:tabular-nums; font-weight:600; font-size:15px;}
  .bar{flex:1; height:6px; background:var(--edge); border-radius:99px; overflow:hidden;}
  .bar > i{display:block; height:100%; background:var(--accent); width:0; transition:width .25s;}
  .copybtn{border:1px solid var(--edge); background:transparent; color:var(--muted);
    font-size:12px; font-weight:600; padding:6px 12px; border-radius:99px; letter-spacing:.03em;}
  .deck{position:relative; flex:1; margin:4px 14px 6px;}
  .card{position:absolute; inset:0; background:var(--card); border:1px solid var(--edge);
    border-radius:var(--radius); overflow:hidden; display:flex; flex-direction:column;
    box-shadow:0 18px 40px rgba(0,0,0,.45); user-select:none; touch-action:pan-y;}
  .card.behind{transform:scale(.94) translateY(14px); filter:brightness(.7);}
  .photo{position:relative; flex:1; min-height:0; background:#0a0d14;}
  .photo img{width:100%; height:100%; object-fit:cover; display:block; pointer-events:none;}
  .badges{position:absolute; top:12px; left:12px; right:12px; display:flex; gap:6px;
    flex-wrap:wrap; align-items:center;}
  .badge{font-size:11px; font-weight:600; letter-spacing:.04em; text-transform:uppercase;
    padding:4px 9px; border-radius:99px; background:rgba(10,13,20,.72); color:#dbe4f0;
    backdrop-filter:blur(6px);}
  .badge.cta{background:rgba(56,189,248,.22); color:#bfe6fb;}
  .badge.type{background:rgba(245,158,11,.22); color:#ffd991;}
  .meta{padding:14px 16px 16px; max-height:38%; overflow-y:auto;}
  .cap{font-size:16px; line-height:1.5; white-space:pre-wrap; margin:0 0 8px;}
  .cap-en{font-size:12.5px; line-height:1.5; color:var(--muted); white-space:pre-wrap; margin:0 0 8px;}
  .tags{font-size:11.5px; color:#5f6f85; line-height:1.5;}
  .stamp{position:absolute; top:24px; font-size:30px; font-weight:800; letter-spacing:.05em;
    padding:6px 16px; border:4px solid; border-radius:12px; opacity:0; text-transform:uppercase;}
  .stamp.yes{right:18px; color:var(--approve); border-color:var(--approve); transform:rotate(12deg);}
  .stamp.no{left:18px; color:var(--reject); border-color:var(--reject); transform:rotate(-12deg);}
  .stamp.fb{left:50%; transform:translateX(-50%); color:var(--feedback); border-color:var(--feedback); top:auto; bottom:24px;}
  .actions{display:flex; justify-content:center; align-items:center; gap:22px; padding:10px 0 22px;}
  .act{width:60px; height:60px; border-radius:50%; border:1px solid var(--edge);
    background:var(--card); color:#fff; display:flex; align-items:center; justify-content:center;
    cursor:pointer;}
  .act svg{width:26px; height:26px;} .act.sm{width:50px; height:50px;} .act.sm svg{width:22px;height:22px;}
  .act.no{color:var(--reject);} .act.fb{color:var(--feedback);} .act.yes{color:var(--approve);}
  .act:active{transform:scale(.9);}
  .overlay{position:absolute; inset:0; background:rgba(6,9,14,.9); display:none;
    flex-direction:column; padding:22px; z-index:20;}
  .overlay.on{display:flex;}
  .overlay h2{font-size:17px; margin:0 0 4px;} .overlay p{color:var(--muted); font-size:13px; margin:0 0 14px;}
  textarea{width:100%; flex:1; background:var(--card); color:var(--text); border:1px solid var(--edge);
    border-radius:14px; padding:14px; font-size:15px; font-family:inherit; resize:none;}
  .row{display:flex; gap:10px; margin-top:14px;}
  .btn{flex:1; padding:14px; border-radius:14px; border:none; font-size:15px; font-weight:600; cursor:pointer;}
  .btn.primary{background:var(--feedback); color:#1a1204;} .btn.ghost{background:var(--edge); color:var(--text);}
  .done{position:absolute; inset:0; display:none; flex-direction:column; justify-content:center;
    align-items:center; text-align:center; padding:28px; z-index:15; background:var(--bg);}
  .done.on{display:flex;}
  .done h1{font-size:24px; margin:0 0 6px;} .done .sum{color:var(--muted); font-size:15px; margin:0 0 20px; line-height:1.7;}
  .done pre{width:100%; max-height:34dvh; overflow:auto; text-align:left; background:var(--card);
    border:1px solid var(--edge); border-radius:12px; padding:12px; font-size:12px; white-space:pre-wrap;}
  .big{width:100%; padding:16px; border-radius:14px; border:none; background:var(--approve);
    color:#052e14; font-size:16px; font-weight:700; cursor:pointer; margin-bottom:10px;}
  .hint{color:var(--muted); font-size:12.5px; line-height:1.5;}
  @media (prefers-reduced-motion: reduce){ *{transition:none!important;} }
</style>

<div id="ep">
  <div class="top">
    <span class="count" id="count">0 / 0</span>
    <div class="bar"><i id="prog"></i></div>
    <button class="copybtn" id="copytop">Terminar ▸</button>
  </div>
  <div class="deck" id="deck"></div>
  <div class="actions">
    <button class="act no"  id="bNo"  aria-label="Rechazar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
    <button class="act fb sm" id="bFb" aria-label="Feedback"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.5 8.5 0 0 1-12.2 7.6L3 21l1.9-5.8A8.5 8.5 0 1 1 21 11.5z"/></svg></button>
    <button class="act yes" id="bYes" aria-label="Aprobar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12.5l5 5L20 6"/></svg></button>
  </div>

  <div class="overlay" id="fbOverlay">
    <h2>¿Qué cambiarías?</h2>
    <p id="fbFor"></p>
    <textarea id="fbText" placeholder="Ej: hazlo más corto, otra foto, cambia el gancho…"></textarea>
    <div class="row">
      <button class="btn ghost" id="fbCancel">Cancelar</button>
      <button class="btn primary" id="fbSave">Guardar y seguir</button>
    </div>
  </div>

  <div class="done" id="done">
    <h1>¡Listo! ✈️</h1>
    <div class="sum" id="sum"></div>
    <button class="big" id="copyBtn">Copiar decisiones</button>
    <p class="hint">Pega esto en el chat de Claude y actualizo la hoja.</p>
    <pre id="result"></pre>
  </div>
</div>

<script>
const POSTS = __POSTS__;
const MONTH = "__MONTH__";
const deck = document.getElementById('deck');
let idx = 0;
const decisions = {}; // id -> {d:'yes'|'no'|'fb', fb:string}

function esc(s){const d=document.createElement('div'); d.textContent=s||''; return d.innerHTML;}

function render(){
  deck.innerHTML='';
  const next = POSTS[idx+1], cur = POSTS[idx];
  if(next) deck.appendChild(makeCard(next, true));
  if(cur)  deck.appendChild(makeCard(cur, false));
  document.getElementById('count').textContent = Math.min(idx+ (cur?1:0), POSTS.length) + ' / ' + POSTS.length;
  document.getElementById('prog').style.width = (idx/POSTS.length*100) + '%';
  if(!cur) finish();
}

function makeCard(p, behind){
  const c=document.createElement('div');
  c.className='card'+(behind?' behind':'');
  const cta = p.cta && p.cta!=='none' ? '<span class="badge cta">CTA</span>' : '';
  c.innerHTML =
    '<div class="photo">'+
      (p.img? '<img src="'+p.img+'" alt="">' : '')+
      '<div class="badges"><span class="badge">#'+esc(p.num)+'</span>'+
        '<span class="badge type">'+esc(p.type)+'</span>'+
        '<span class="badge">'+esc(p.pillar)+'</span>'+cta+'</div>'+
      '<div class="stamp yes">Aprobar</div><div class="stamp no">Rechazar</div>'+
      '<div class="stamp fb">Feedback</div>'+
    '</div>'+
    '<div class="meta"><p class="cap">'+esc(p.caption_es)+'</p>'+
      '<p class="cap-en">'+esc(p.caption_en)+'</p>'+
      '<p class="tags">'+esc(p.hashtags)+'</p></div>';
  if(!behind) attachDrag(c);
  return c;
}

function attachDrag(card){
  let x0=0,y0=0,dx=0,dy=0,drag=false;
  const yes=card.querySelector('.stamp.yes'), no=card.querySelector('.stamp.no'), fb=card.querySelector('.stamp.fb');
  const meta=card.querySelector('.meta');
  const down=e=>{ if(meta.contains(e.target)&&meta.scrollHeight>meta.clientHeight) return;
    drag=true; x0=e.clientX; y0=e.clientY; card.setPointerCapture(e.pointerId); card.style.transition='none';};
  const move=e=>{ if(!drag) return; dx=e.clientX-x0; dy=e.clientY-y0;
    card.style.transform='translate('+dx+'px,'+dy+'px) rotate('+(dx/18)+'deg)';
    yes.style.opacity = dx>0? Math.min(dx/100,1):0;
    no.style.opacity  = dx<0? Math.min(-dx/100,1):0;
    fb.style.opacity  = (dy<-40 && Math.abs(dx)<60)? Math.min(-dy/120,1):0; };
  const up=e=>{ if(!drag) return; drag=false; card.style.transition='transform .28s ease';
    if(dy<-90 && Math.abs(dx)<80){ reset(card); openFeedback(); return; }
    if(dx>110){ fly(card,1); decide('yes'); }
    else if(dx<-110){ fly(card,-1); decide('no'); }
    else { card.style.transform=''; yes.style.opacity=no.style.opacity=fb.style.opacity=0; }
    dx=dy=0; };
  card.addEventListener('pointerdown',down);
  card.addEventListener('pointermove',move);
  card.addEventListener('pointerup',up);
  card.addEventListener('pointercancel',up);
}
function fly(card,dir){ card.style.transform='translate('+(dir*600)+'px,60px) rotate('+(dir*30)+'deg)'; card.style.opacity=0; }
function reset(card){ card.style.transition='transform .2s'; card.style.transform='';
  card.querySelectorAll('.stamp').forEach(s=>s.style.opacity=0); }

function decide(d, fbText){
  const p=POSTS[idx]; if(!p) return;
  decisions[p.id]={d:d, fb:fbText||''};
  idx++; setTimeout(render, d==='fb'?0:180);
}

function openFeedback(){
  const p=POSTS[idx]; if(!p) return;
  document.getElementById('fbFor').textContent='Post #'+p.num+' · '+p.pillar;
  document.getElementById('fbText').value = (decisions[p.id]&&decisions[p.id].fb)||'';
  document.getElementById('fbOverlay').classList.add('on');
  document.getElementById('fbText').focus();
}
document.getElementById('fbCancel').onclick=()=>document.getElementById('fbOverlay').classList.remove('on');
document.getElementById('fbSave').onclick=()=>{
  const t=document.getElementById('fbText').value.trim();
  document.getElementById('fbOverlay').classList.remove('on');
  decide('fb', t);
};

document.getElementById('bNo').onclick=()=>{const c=deck.querySelector('.card:not(.behind)'); if(c){fly(c,-1);} decide('no');};
document.getElementById('bYes').onclick=()=>{const c=deck.querySelector('.card:not(.behind)'); if(c){fly(c,1);} decide('yes');};
document.getElementById('bFb').onclick=openFeedback;
document.getElementById('copytop').onclick=finish;

function buildResult(){
  const yes=[],no=[],fb=[];
  POSTS.forEach(p=>{ const d=decisions[p.id]; if(!d) return;
    if(d.d==='yes') yes.push(p.num);
    else if(d.d==='no') no.push(p.num);
    else if(d.d==='fb') fb.push('- '+p.num+': '+(d.fb||'(sin detalle)')); });
  const pend=POSTS.filter(p=>!decisions[p.id]).map(p=>p.num);
  let t='Epic.Plane — decisiones '+MONTH+'\n';
  t+='APROBAR: '+(yes.join(', ')||'—')+'\n';
  t+='RECHAZAR: '+(no.join(', ')||'—')+'\n';
  t+='FEEDBACK:\n'+(fb.join('\n')||'—')+'\n';
  if(pend.length) t+='PENDIENTES: '+pend.join(', ')+'\n';
  return t;
}
function finish(){
  const r=buildResult();
  document.getElementById('result').textContent=r;
  const y=(r.match(/APROBAR: (.*)/)||[])[1]||'';
  document.getElementById('sum').innerHTML='Revisaste tus posts. Copia el resumen y pégalo en el chat.';
  document.getElementById('done').classList.add('on');
}
document.getElementById('copyBtn').onclick=async()=>{
  const r=buildResult();
  try{ await navigator.clipboard.writeText(r); document.getElementById('copyBtn').textContent='¡Copiado! ✓'; }
  catch(e){ const pre=document.getElementById('result'); const sel=window.getSelection();
    const range=document.createRange(); range.selectNodeContents(pre); sel.removeAllRanges(); sel.addRange(range);
    document.getElementById('copyBtn').textContent='Selecciona y copia ↓'; }
};
render();
</script>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", required=True)
    ap.add_argument("--out", default=str(ROOT / "review_deck.html"))
    args = ap.parse_args()

    print("→ Leyendo la hoja…")
    posts = fetch_posts(args.month)
    print(f"   {len(posts)} posts. Descargando fotos…")
    for i, p in enumerate(posts, 1):
        p["img"] = to_data_uri(p["img_url"]) if p["img_url"] else ""
        print(f"   [{i}/{len(posts)}] {p['id']} {'ok' if p['img'] else 'sin foto'}")
        p.pop("img_url", None)

    # ensure_ascii=True: los acentos van como \uXXXX y se ven bien sin depender del charset.
    data = json.dumps(posts, ensure_ascii=True).replace("</", "<\\/")
    html = HTML.replace("__POSTS__", data).replace("__MONTH__", args.month)
    Path(args.out).write_text(html, encoding="utf-8")
    mb = len(html.encode()) / 1_048_576
    print(f"✓ Deck escrito: {args.out}  ({mb:.1f} MB)")


if __name__ == "__main__":
    main()
