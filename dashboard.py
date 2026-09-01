"""CEO Dashboard (Fase 1): junta métricas de IG + estado de contenido por cliente,
calcula salud y decisiones, y genera dashboard.html estático."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import smtplib
import ssl
import urllib.parse
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GRAPH = "https://graph.facebook.com/v21.0/"


def load_clients(base: Path = ROOT) -> list[dict]:
    cdir = base / "clients"
    if not cdir.exists():
        return []
    out = []
    for p in sorted(cdir.glob("*/config.json")):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def _parse_ts(s: str) -> dt.datetime:
    return dt.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)


def summarize_period(posts: list[dict], days: int = 7) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    def age(p): return (now - _parse_ts(p["timestamp"])).days
    cur = [p for p in posts if age(p) < days]
    prev = [p for p in posts if days <= age(p) < 2 * days]
    def agg(lst):
        n = len(lst) or 1
        return {"n": len(lst),
                "reach": round(sum((p.get("reach") or 0) for p in lst) / n),
                "likes": round(sum(p.get("like", 0) for p in lst) / n, 1),
                "comments": round(sum(p.get("comment", 0) for p in lst) / n, 1)}
    c, pv = agg(cur), agg(prev)
    trend = round((c["reach"] - pv["reach"]) / pv["reach"] * 100) if pv["reach"] else 0
    return {"cur": c, "prev": pv, "reach_trend_pct": trend}


def _graph(path: str, params: dict, tok: str):
    url = GRAPH + path + "?" + urllib.parse.urlencode(dict(params, access_token=tok))
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.load(r)
    except Exception:
        return {}


def instagram_snapshot(ch: dict, env: dict) -> dict | None:
    ig = env.get(ch.get("ig_user_id_env", "IG_USER_ID"))
    tok = env.get(ch.get("token_env", "META_PAGE_TOKEN"))
    if not ig or not tok:
        return None
    followers = _graph(ig, {"fields": "followers_count"}, tok).get("followers_count", 0)
    media = _graph(ig + "/media",
                   {"fields": "id,media_product_type,timestamp,permalink,like_count,comments_count,caption",
                    "limit": "20"}, tok).get("data", [])
    posts = []
    for m in media:
        reach = None
        ins = _graph(m["id"] + "/insights", {"metric": "reach"}, tok)
        for x in ins.get("data", []):
            reach = x["values"][0]["value"]
        posts.append({"timestamp": m["timestamp"], "like": m.get("like_count", 0),
                      "comment": m.get("comments_count", 0), "reach": reach,
                      "permalink": m.get("permalink", ""),
                      "hook": (m.get("caption") or "").split("\n")[0][:60]})
    s = summarize_period(posts)
    top = max(posts[:7], key=lambda p: p.get("like", 0), default=None) if posts else None
    return {"followers": followers, "cur": s["cur"], "prev": s["prev"],
            "reach_trend_pct": s["reach_trend_pct"], "top": top}


def _tf(v) -> bool:
    return str(v).strip().upper() in ("TRUE", "1")


def content_status(rows: list[list], header: list, month_prefix: str = "") -> dict:
    idx = {h: i for i, h in enumerate(header)}
    def g(r, k, d=""):
        i = idx.get(k)
        return r[i] if (i is not None and i < len(r)) else d
    pend = pub_week = 0
    proximo = None
    today = dt.date.today().isoformat()
    for r in rows:
        if not g(r, "id"):
            continue
        appr, publ, date = _tf(g(r, "approved")), _tf(g(r, "published")), g(r, "date")
        if appr and not publ:
            if proximo is None or (date and date < proximo):
                proximo = date
        if not appr and not publ and date >= today:
            pend += 1
    return {"pendientes": pend, "publicados_semana": pub_week, "proximo": proximo}


def sheet_content(slug: str) -> dict:
    try:
        import sheets
        _, ws = sheets.get_worksheet()
        rows = ws.get_all_values()
        return content_status(rows[1:], rows[0])
    except Exception:
        return {}


def compute_health(snap: dict | None) -> str:
    if not snap or not snap.get("cur"):
        return "gray"
    t = snap.get("reach_trend_pct", 0)
    coms = snap["cur"].get("comments", 0)
    if t > 10 and coms > 0:
        return "green"
    if t < -10:
        return "red"
    return "yellow"


def build_decisions(cfg: dict, snap: dict | None, content: dict) -> dict:
    # 1. Contenido
    pend = content.get("pendientes", 0)
    prox = content.get("proximo")
    if not content:
        contenido = "Estado de contenido no disponible (revisar conexión a la hoja)."
    elif pend:
        contenido = f"⚠️ {pend} post(s) sin aprobar. Revísalos para no perder días."
    elif prox:
        contenido = f"Al día. Próximo publica el {prox}."
    else:
        contenido = "Sin contenido en cola — hay que generar el próximo lote."
    # 2. Estrategia por canal
    if not snap or not snap.get("cur"):
        estrategia = "Sin datos de IG (falta permiso o publicaciones)."
    elif snap.get("reach_trend_pct", 0) < -10:
        estrategia = "Alcance BAJANDO → cambio urgente: todo a reels + audio en tendencia + stories diarias."
    elif snap["cur"].get("comments", 0) == 0 and abs(snap.get("reach_trend_pct", 0)) <= 10:
        estrategia = "Alcance plano y 0 comentarios → prioriza reels + audio en tendencia y ganchos más directos."
    elif snap.get("reach_trend_pct", 0) > 10:
        estrategia = "Alcance subiendo → seguir con este estilo y aumentar frecuencia."
    else:
        estrategia = "Mantener el ritmo; medir otra semana antes de cambiar."
    # 3. Presupuesto
    top = (snap or {}).get("top")
    cur = (snap or {}).get("cur") or {}
    if top and cur.get("likes") and top.get("like", 0) > 2 * cur["likes"]:
        presupuesto = "Un post rindió muy por sobre el promedio → candidato a boost pagado chico."
    else:
        presupuesto = "Sin acción de pauta esta semana."
    # 4. Cliente
    health = compute_health(snap)
    nota = {"green": "🟢 Sano — va mejorando.",
            "yellow": "🟡 Estable/plano — vigilar.",
            "red": "🔴 En riesgo — conversar rumbo.",
            "gray": "⚪ Sin datos aún."}[health]
    cliente = f"{cfg.get('name','')}: {nota}"
    return {"contenido": contenido, "estrategia": estrategia,
            "presupuesto": presupuesto, "cliente": cliente}


_HEALTH = {"green": ("🟢", "#3FB07A"), "yellow": ("🟡", "#E9A73C"),
           "red": ("🔴", "#E9553D"), "gray": ("⚪", "#7C6E60")}
_CH_LABEL = {"instagram": "Instagram", "youtube": "YouTube", "linkedin": "LinkedIn", "tiktok": "TikTok"}


def _fmt(n):
    try:
        return f"{int(n):,}".replace(",", ".")
    except Exception:
        return str(n)


def _client_card(d: dict) -> str:
    cfg, snap, dec = d["cfg"], d.get("snap"), d["decisions"]
    emoji, color = _HEALTH[d["health"]]
    chans = cfg.get("channels", {})
    # fila de canales
    chips = []
    for key, label in _CH_LABEL.items():
        ch = chans.get(key, {})
        if key == "instagram" and ch.get("enabled") and snap:
            t = snap.get("reach_trend_pct", 0)
            arrow = "↑" if t > 10 else ("↓" if t < -10 else "→")
            chips.append(f"<div class='chan on'><b>{label}</b>"
                         f"<span>{_fmt(snap.get('followers',0))} seg · alcance {_fmt(snap['cur'].get('reach',0))} {arrow}{t:+d}% · "
                         f"{snap['cur'].get('likes',0)}♥ {snap['cur'].get('comments',0)}💬</span></div>")
        elif ch.get("enabled"):
            chips.append(f"<div class='chan on'><b>{label}</b><span>habilitado</span></div>")
        else:
            chips.append(f"<div class='chan off'><b>{label}</b><span>próximamente</span></div>")
    decs = "".join(
        f"<div class='dec'><span class='dl'>{lbl}</span><p>{dec[k]}</p></div>"
        for k, lbl in [("contenido", "Contenido"), ("estrategia", "Estrategia por canal"),
                       ("presupuesto", "Presupuesto"), ("cliente", "Cliente")])
    return (f"<section class='card'><div class='chd'><h2>{cfg.get('name','')}</h2>"
            f"<span class='badge' style='color:{color}'>{emoji}</span></div>"
            f"<div class='chans'>{''.join(chips)}</div>"
            f"<div class='decs'><h3>Decisiones de la semana</h3>{decs}</div></section>")


_HEALTH_HEX = {"green": "#3FB07A", "yellow": "#E9A73C", "red": "#E9553D", "gray": "#7C6E60"}

_TEMPLATE = r"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CEO Dashboard</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap">
<style>
:root{--bg:#120E0B;--panel:#1B1510;--card:#211A14;--ink:#F4ECE3;--soft:#AC9C8D;--faint:#7C6E60;--line:rgba(255,255,255,.09);}
*{box-sizing:border-box;} body{margin:0;background:var(--bg);color:var(--ink);font-family:'Plus Jakarta Sans',system-ui,sans-serif;}
.wrap{max-width:1080px;margin:0 auto;padding:26px 20px 70px;}
h1{font-size:24px;margin:0;} .sub{color:var(--soft);font-size:13px;margin:4px 0 20px;}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:26px;}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px;}
.kpi .l{color:var(--soft);font-size:12px;} .kpi .v{font-size:22px;font-weight:800;margin-top:3px;}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(255px,1fr));gap:16px;}
.tile{background:var(--card);border:1px solid var(--line);border-radius:18px;overflow:hidden;cursor:pointer;transition:transform .15s,border-color .15s;}
.tile:hover{transform:translateY(-3px);border-color:rgba(255,255,255,.28);}
.tile .top{height:10px;} .tile .body{padding:18px 18px 20px;}
.tile h2{margin:0;font-size:20px;} .tile .niche{color:var(--soft);font-size:12px;margin:2px 0 14px;}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-left:8px;vertical-align:middle;}
.tk{display:flex;justify-content:space-between;font-size:13px;padding:6px 0;border-top:1px solid var(--line);}
.tk .kv{color:var(--soft);} .tk .vv{font-weight:700;}
.marg-pos{color:#5FBF8A;} .marg-neg{color:#E9553D;}
.back{background:none;border:1px solid var(--line);color:var(--soft);border-radius:999px;padding:8px 16px;cursor:pointer;font-family:inherit;font-size:14px;margin-bottom:16px;}
.back:hover{color:var(--ink);}
.dhead{display:flex;align-items:center;gap:12px;margin-bottom:2px;} .dhead h1{font-size:28px;}
.secs{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:18px;}
@media(max-width:720px){.secs{grid-template-columns:1fr;}}
.sec{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:18px 20px;}
.sec h3{margin:0 0 10px;font-size:13px;text-transform:uppercase;letter-spacing:.12em;}
.row{display:flex;justify-content:space-between;gap:14px;font-size:14px;padding:9px 0;border-top:1px solid var(--line);}
.row:first-of-type{border-top:none;} .row .k{color:var(--soft);} .row .v{font-weight:700;text-align:right;}
.dec{padding:10px 0;border-top:1px solid var(--line);} .dec:first-child{border-top:none;}
.dec .dl{font-size:11px;font-weight:800;color:var(--faint);text-transform:uppercase;letter-spacing:.06em;}
.dec p{margin:4px 0 0;font-size:14px;line-height:1.5;}
.hidden{display:none;}
</style></head><body>
<div class="wrap">
 <div id="home">
  <h1>CEO Dashboard <span style="color:var(--faint);font-weight:600;font-size:15px;">· Al Día</span></h1>
  <p class="sub">Actualizado __UPDATED__ · haz clic en una marca para ver su cuadro de mando</p>
  <div class="kpis" id="kpis"></div>
  <div class="grid" id="grid"></div>
 </div>
 <div id="detail" class="hidden"></div>
 <noscript><div style="color:#AC9C8D">__FALLBACK__</div></noscript>
</div>
<script>
var DATA = __DATA__;
function clp(n){return "$" + (n||0).toLocaleString("es-CL");}
function money(n){return (n||0).toLocaleString("es-CL");}
function arrow(t){return t>10?("↑"+t+"%"):(t<-10?("↓"+t+"%"):("→"+t+"%"));}
function kpi(l,v){return "<div class='kpi'><div class='l'>"+l+"</div><div class='v'>"+v+"</div></div>";}
function homeKPIs(){
  var rev=0,cost=0,pend=0;
  DATA.forEach(function(b){rev+=b.finances.revenue;cost+=b.finances.cost;pend+=b.pendientes;});
  document.getElementById("kpis").innerHTML =
   kpi("Marcas",DATA.length)+kpi("Ingresos / mes",clp(rev))+kpi("Margen / mes",clp(rev-cost))+kpi("Decisiones pendientes",pend);
}
function grid(){
  var g=document.getElementById("grid"); g.innerHTML="";
  DATA.forEach(function(b,i){
    var m=b.finances.margin;
    var ig=b.channels.filter(function(c){return c.name=="Instagram";})[0];
    var foll=b.followers?(money(b.followers)+" seg"):"por conectar";
    var reach=(ig&&ig.state=="data")?(" · alcance "+money(ig.reach)+" "+arrow(ig.trend)):"";
    var el=document.createElement("div"); el.className="tile";
    el.innerHTML="<div class='top' style='background:"+b.color+"'></div><div class='body'>"+
      "<h2>"+b.name+"<span class='dot' style='background:"+b.healthColor+"'></span></h2>"+
      "<div class='niche'>"+foll+reach+"</div>"+
      "<div class='tk'><span class='kv'>Ingresos</span><span class='vv'>"+clp(b.finances.revenue)+"</span></div>"+
      "<div class='tk'><span class='kv'>Margen</span><span class='vv "+(m>=0?'marg-pos':'marg-neg')+"'>"+clp(m)+"</span></div>"+
      "<div class='tk'><span class='kv'>Pendientes</span><span class='vv'>"+b.pendientes+"</span></div></div>";
    el.onclick=(function(k){return function(){showDetail(k);};})(i);
    g.appendChild(el);
  });
}
function chanRows(b){
  return b.channels.map(function(c){
    var v;
    if(c.state=="data"){v=money(c.followers)+" seg · alcance "+money(c.reach)+" "+arrow(c.trend)+" · "+c.likes+"♥ "+c.comments+"💬";}
    else if(c.state=="on"){v="habilitado (por conectar datos)";}
    else{v="próximamente";}
    return "<div class='row'><span class='k'>"+c.name+"</span><span class='v'>"+v+"</span></div>";
  }).join("");
}
function showDetail(i){
  var b=DATA[i],f=b.finances,d=document.getElementById("detail");
  d.innerHTML="<button class='back' onclick='showHome()'>← Todas las marcas</button>"+
   "<div class='dhead'><span style='width:16px;height:16px;border-radius:5px;background:"+b.color+"'></span>"+
   "<h1>"+b.name+"</h1><span class='dot' style='background:"+b.healthColor+"'></span></div>"+
   "<div class='secs'>"+
     "<div class='sec'><h3 style='color:"+b.color+"'>RRSS</h3>"+chanRows(b)+"</div>"+
     "<div class='sec'><h3 style='color:"+b.color+"'>Ingresos y costos</h3>"+
       "<div class='row'><span class='k'>Ingresos / mes</span><span class='v'>"+clp(f.revenue)+"</span></div>"+
       "<div class='row'><span class='k'>Costos / mes</span><span class='v'>"+clp(f.cost)+"</span></div>"+
       "<div class='row'><span class='k'>Margen / mes</span><span class='v "+(f.margin>=0?'marg-pos':'marg-neg')+"'>"+clp(f.margin)+"</span></div>"+
       (f.note?"<div class='niche' style='margin-top:8px'>"+f.note+"</div>":"")+"</div>"+
     "<div class='sec' style='grid-column:1/-1'><h3 style='color:"+b.color+"'>Decisiones de la semana</h3>"+
       b.decisions.map(function(x){return "<div class='dec'><span class='dl'>"+x[0]+"</span><p>"+x[1]+"</p></div>";}).join("")+"</div>"+
   "</div>";
  document.getElementById("home").classList.add("hidden"); d.classList.remove("hidden"); window.scrollTo(0,0);
}
function showHome(){document.getElementById("detail").classList.add("hidden");document.getElementById("home").classList.remove("hidden");}
homeKPIs(); grid();
</script></body></html>"""


def render_html(clients_data: list[dict]) -> str:
    payload = []
    for c in clients_data:
        cfg = c["cfg"]; snap = c.get("snap"); dec = c.get("decisions", {}) or {}
        fin = cfg.get("finances", {}) or {}
        rev = fin.get("monthly_revenue", 0) or 0
        cost = fin.get("monthly_costs", 0) or 0
        chans = []
        for key, label in _CH_LABEL.items():
            ch = cfg.get("channels", {}).get(key, {})
            if key == "instagram" and ch.get("enabled") and snap:
                chans.append({"name": label, "state": "data",
                              "followers": snap.get("followers", 0),
                              "reach": snap["cur"].get("reach", 0),
                              "trend": snap.get("reach_trend_pct", 0),
                              "likes": snap["cur"].get("likes", 0),
                              "comments": snap["cur"].get("comments", 0)})
            elif ch.get("enabled"):
                chans.append({"name": label, "state": "on"})
            else:
                chans.append({"name": label, "state": "off"})
        payload.append({
            "slug": cfg.get("slug", ""), "name": cfg.get("name", ""),
            "color": cfg.get("brand_color", "#E9553D"),
            "healthColor": _HEALTH_HEX.get(c.get("health", "gray"), "#7C6E60"),
            "followers": (snap or {}).get("followers", 0),
            "channels": chans,
            "decisions": [["Contenido", dec.get("contenido", "")],
                          ["Estrategia por canal", dec.get("estrategia", "")],
                          ["Presupuesto", dec.get("presupuesto", "")],
                          ["Cliente", dec.get("cliente", "")]],
            "finances": {"revenue": rev, "cost": cost, "margin": rev - cost, "note": fin.get("note", "")},
            "pendientes": (c.get("content") or {}).get("pendientes", 0),
        })
    data_json = json.dumps(payload, ensure_ascii=False)
    updated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    fb = []
    for p in payload:
        fb.append("<b>" + p["name"] + "</b> (" + p.get("healthColor", "") + ")")
        for lbl, tx in p["decisions"]:
            fb.append(lbl + ": " + tx)
        fb.append("Seguidores: " + str(p["followers"]) + " · canales sin conectar: próximamente")
    fallback = " — ".join(fb)
    return (_TEMPLATE.replace("__DATA__", data_json)
            .replace("__UPDATED__", updated).replace("__FALLBACK__", fallback))


def _load_env() -> dict:
    e = {}
    p = ROOT / ".env"
    if p.exists():
        for l in p.read_text(encoding="utf-8").splitlines():
            if "=" in l and not l.strip().startswith("#"):
                k, _, v = l.partition("=")
                e[k.strip()] = v.strip().strip('"').strip("'")
    import os
    e.update({k: os.environ[k] for k in
              ("IG_USER_ID", "META_PAGE_TOKEN", "GMAIL_USER", "GMAIL_APP_PASSWORD", "EMAIL_TO")
              if os.environ.get(k)})
    return e


def send_dashboard_email(html_path: Path, env: dict) -> None:
    """Envía el dashboard al CEO por Gmail: cuerpo corto + el HTML interactivo adjunto
    (el correo bloquea JS, así que se abre en el navegador). Entrega privada, sin hosting."""
    user = env.get("GMAIL_USER")
    pw = env.get("GMAIL_APP_PASSWORD")
    to = env.get("EMAIL_TO", "felipecood@gmail.com")
    if not user or not pw:
        print("  (sin GMAIL_USER/GMAIL_APP_PASSWORD → no se envió el correo)")
        return
    msg = MIMEMultipart()
    msg["Subject"] = "CEO Dashboard — " + dt.datetime.now().strftime("%d/%m/%Y")
    msg["From"] = user
    msg["To"] = to
    body = ("<div style=\"font-family:Arial,sans-serif;color:#2A211C\">"
            "<h2 style=\"color:#C9372A\">Tu CEO Dashboard de la semana</h2>"
            "<p>Está adjunto como <b>dashboard.html</b>. Ábrelo en el navegador para el cuadro de mando "
            "interactivo: haz clic en cada marca para ver sus RRSS, decisiones, ingresos y costos.</p>"
            "<p style=\"color:#8A7E74;font-size:13px\">Al Día · community manager automatizado</p></div>")
    msg.attach(MIMEText(body, "html", "utf-8"))
    att = MIMEApplication(Path(html_path).read_bytes(), _subtype="html")
    att.add_header("Content-Disposition", "attachment", filename="dashboard.html")
    msg.attach(att)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(user, pw)
        s.sendmail(user, [to], msg.as_string())
    print(f"✓ Dashboard enviado por correo a {to}")


def main() -> None:
    ap = argparse.ArgumentParser(description="CEO Dashboard — genera dashboard.html (y opcional lo envía por correo).")
    ap.add_argument("--email", action="store_true", help="Además, envía el dashboard al CEO por Gmail.")
    args = ap.parse_args()

    env = _load_env()
    data = []
    for cfg in load_clients():
        ig = cfg.get("channels", {}).get("instagram", {})
        snap = instagram_snapshot(ig, env) if ig.get("enabled") else None
        content = sheet_content(cfg["slug"]) if ig.get("enabled") else {}
        data.append({"cfg": cfg, "snap": snap, "content": content,
                     "health": compute_health(snap),
                     "decisions": build_decisions(cfg, snap, content)})
    html = render_html(data)
    (ROOT / "dashboard.html").write_text(html, encoding="utf-8")
    print(f"✓ dashboard.html generado ({len(data)} cliente(s)).")
    if args.email:
        send_dashboard_email(ROOT / "dashboard.html", env)


if __name__ == "__main__":
    main()
