"""CEO Dashboard (Fase 1): junta métricas de IG + estado de contenido por cliente,
calcula salud y decisiones, y genera dashboard.html estático."""

from __future__ import annotations

import datetime as dt
import json
import urllib.parse
import urllib.request
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
    if pend:
        contenido = f"⚠️ {pend} post(s) sin aprobar. Revísalos para no perder días."
    elif prox:
        contenido = f"Al día. Próximo publica el {prox}."
    else:
        contenido = "Sin contenido en cola — hay que generar el próximo lote."
    # 2. Estrategia por canal
    if not snap or not snap.get("cur"):
        estrategia = "Sin datos de IG (falta permiso o publicaciones)."
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


def render_html(clients_data: list[dict]) -> str:
    pend_total = sum(c.get("content", {}).get("pendientes", 0) for c in clients_data)
    chips = "".join(
        f"<span class='oc'>{_HEALTH[c['health']][0]} {c['cfg'].get('name','')}</span>"
        for c in clients_data)
    cards = "".join(_client_card(c) for c in clients_data)
    updated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CEO Dashboard</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap">
<style>
:root{{--bg:#140F0C;--card:#1B1410;--ink:#F4ECE3;--soft:#AC9C8D;--line:rgba(255,255,255,.09);--tomato:#E9553D;}}
*{{box-sizing:border-box;}} body{{margin:0;background:var(--bg);color:var(--ink);font-family:'Plus Jakarta Sans',system-ui,sans-serif;}}
.wrap{{max-width:1000px;margin:0 auto;padding:28px 20px 60px;}}
h1{{font-size:26px;margin:0 0 4px;}} .sub{{color:var(--soft);font-size:14px;margin-bottom:20px;}}
.overview{{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:8px;}}
.oc{{background:var(--card);border:1px solid var(--line);border-radius:999px;padding:8px 14px;font-weight:700;font-size:14px;}}
.pend{{color:var(--tomato);font-weight:800;font-size:14px;margin:8px 0 24px;}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px;margin-bottom:18px;}}
.chd{{display:flex;justify-content:space-between;align-items:center;}} .chd h2{{margin:0;font-size:22px;}} .badge{{font-size:20px;}}
.chans{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:16px 0;}}
.chan{{border:1px solid var(--line);border-radius:12px;padding:12px 14px;}} .chan b{{font-size:14px;}} .chan span{{display:block;color:var(--soft);font-size:12.5px;margin-top:4px;}}
.chan.off{{opacity:.5;}}
.decs h3{{font-size:14px;text-transform:uppercase;letter-spacing:.1em;color:var(--tomato);margin:8px 0 12px;}}
.dec{{border-top:1px solid var(--line);padding:11px 0;}} .dl{{font-size:12px;font-weight:800;color:var(--soft);text-transform:uppercase;letter-spacing:.06em;}}
.dec p{{margin:5px 0 0;font-size:15px;line-height:1.5;}}
</style></head><body><div class="wrap">
<h1>CEO Dashboard</h1><p class="sub">Actualizado {updated} · {len(clients_data)} cliente(s)</p>
<div class="overview">{chips}</div>
<p class="pend">{pend_total} decisión(es) de contenido pendientes en total</p>
{cards}
</div></body></html>"""


def _load_env() -> dict:
    e = {}
    p = ROOT / ".env"
    if p.exists():
        for l in p.read_text(encoding="utf-8").splitlines():
            if "=" in l and not l.strip().startswith("#"):
                k, _, v = l.partition("=")
                e[k.strip()] = v.strip().strip('"').strip("'")
    import os
    e.update({k: os.environ[k] for k in ("IG_USER_ID", "META_PAGE_TOKEN") if os.environ.get(k)})
    return e


def main() -> None:
    env = _load_env()
    data = []
    for cfg in load_clients():
        ig = cfg.get("channels", {}).get("instagram", {})
        snap = instagram_snapshot(ig, env) if ig.get("enabled") else None
        content = sheet_content(cfg["slug"]) if ig.get("enabled") else {}
        data.append({"cfg": cfg, "snap": snap, "content": content,
                     "health": compute_health(snap),
                     "decisions": build_decisions(cfg, snap, content)})
    (ROOT / "dashboard.html").write_text(render_html(data), encoding="utf-8")
    print(f"✓ dashboard.html generado ({len(data)} cliente(s)).")


if __name__ == "__main__":
    main()
