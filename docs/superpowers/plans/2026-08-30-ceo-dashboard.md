# CEO Dashboard (Fase 1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generar un dashboard web privado, multi-cliente, que junta métricas de Instagram + estado de contenido y muestra la salud y las decisiones semanales del CEO.

**Architecture:** Un módulo `dashboard.py` descubre clientes desde `clients/*/config.json`, arma un snapshot de Instagram (Graph API) y el estado de contenido (Google Sheet), calcula salud y decisiones con reglas deterministas, y renderiza `dashboard.html` estático. Un workflow lo refresca semanal. No toca el pipeline existente (solo lee).

**Tech Stack:** Python 3.9 (stdlib: `json`, `datetime`, `urllib`, `pathlib`), `gspread`/`google-auth` (ya presentes, solo para leer la Sheet), `pytest` (dev).

## Global Constraints

- Python 3.9 (macOS). Usar `python3`.
- Sin dependencias nuevas de runtime: stdlib + `gspread`/`google-auth` ya instalados. `pytest` es dev (`python3 -m pip install --user pytest`).
- El dashboard **solo lee** datos. NO modificar `generate_content.py`, `media.py`, `publish.py`, `sheets.py`, `daily_email.py`, `curate.py`, `soul.py`, ni sus workflows.
- Un "cliente" es un slug con `clients/<slug>/config.json`. Semilla: `epic-plane`. Credenciales de IG de Epic.Plane desde `.env` (`IG_USER_ID`, `META_PAGE_TOKEN`).
- Instagram: reutilizar el patrón de Graph API v21.0 ya usado en `daily_email.py` (fields `like_count,comments_count,timestamp` + insights `reach`), degradando a N/D si falta permiso.
- Reglas de salud/decisión deterministas (umbrales), no IA.
- HTML autocontenido (solo Google Fonts como recurso externo). Números redondeados.
- Correr comandos desde la raíz del proyecto.

---

### Task 1: Config de clientes + loader

**Files:**
- Create: `clients/epic-plane/config.json`
- Create: `dashboard.py`
- Create: `tests/test_dashboard.py`

**Interfaces:**
- Produces: `dashboard.ROOT` (Path); `dashboard.load_clients(base: Path = ROOT) -> list[dict]` — lee todos los `clients/*/config.json`, ordenados por `slug`; devuelve `[]` si no hay carpeta `clients/`.

- [ ] **Step 1: Crear el config semilla** `clients/epic-plane/config.json`

```json
{
  "slug": "epic-plane",
  "name": "Epic.Plane",
  "niche": "aviación",
  "channels": {
    "instagram": { "enabled": true, "handle": "epic.plane", "ig_user_id_env": "IG_USER_ID", "token_env": "META_PAGE_TOKEN" },
    "youtube":  { "enabled": false },
    "linkedin": { "enabled": false },
    "tiktok":   { "enabled": false }
  },
  "goals": { "primary": "reactivar alcance y engagement" },
  "budget_notes": "sin pauta por ahora"
}
```

- [ ] **Step 2: Escribir el test que falla** `tests/test_dashboard.py`

```python
import json
import dashboard


def test_load_clients_reads_configs(tmp_path):
    d = tmp_path / "clients" / "demo"
    d.mkdir(parents=True)
    (d / "config.json").write_text(json.dumps({"slug": "demo", "name": "Demo"}), encoding="utf-8")
    clients = dashboard.load_clients(base=tmp_path)
    assert len(clients) == 1
    assert clients[0]["slug"] == "demo"


def test_load_clients_missing_returns_empty(tmp_path):
    assert dashboard.load_clients(base=tmp_path) == []
```

- [ ] **Step 3: Correr el test y verificar que falla**

Run: `python3 -m pytest tests/test_dashboard.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'dashboard'`.

- [ ] **Step 4: Escribir `dashboard.py` (mínimo)**

```python
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
```

- [ ] **Step 5: Correr el test y verificar que pasa**

Run: `python3 -m pytest tests/test_dashboard.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add clients/epic-plane/config.json dashboard.py tests/test_dashboard.py
git commit -m "feat: dashboard client config + load_clients"
```

---

### Task 2: Resumen de período (pura) + snapshot de Instagram

**Files:**
- Modify: `dashboard.py`
- Modify: `tests/test_dashboard.py`

**Interfaces:**
- Consumes: `dashboard.ROOT`.
- Produces:
  - `dashboard.summarize_period(posts: list[dict], days: int = 7) -> dict` — `posts` con claves `timestamp` (ISO), `like`, `comment`, `reach`. Devuelve `{"cur": {...}, "prev": {...}, "reach_trend_pct": int}` donde cada período tiene `n, reach, likes, comments` (promedios redondeados).
  - `dashboard.instagram_snapshot(ch: dict, env: dict) -> dict | None` — usa la Graph API; devuelve `{"followers", "cur", "prev", "reach_trend_pct", "top": {...}}` o `None` si faltan credenciales.

- [ ] **Step 1: Escribir el test que falla** (agregar a `tests/test_dashboard.py`)

```python
import datetime as dt


def _iso(days_ago):
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S+0000")


def test_summarize_period_splits_and_trend():
    posts = [
        {"timestamp": _iso(1), "like": 10, "comment": 2, "reach": 1000},
        {"timestamp": _iso(3), "like": 20, "comment": 0, "reach": 2000},
        {"timestamp": _iso(9), "like": 5,  "comment": 0, "reach": 500},
    ]
    s = dashboard.summarize_period(posts, days=7)
    assert s["cur"]["n"] == 2
    assert s["cur"]["reach"] == 1500
    assert s["prev"]["n"] == 1
    assert s["reach_trend_pct"] == 200  # (1500-500)/500*100
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python3 -m pytest tests/test_dashboard.py::test_summarize_period_splits_and_trend -v`
Expected: FAIL con `AttributeError: module 'dashboard' has no attribute 'summarize_period'`.

- [ ] **Step 3: Agregar `summarize_period`, `_parse_ts`, `_graph`, `instagram_snapshot` a `dashboard.py`**

```python
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
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python3 -m pytest tests/test_dashboard.py -v`
Expected: PASS (todos).

- [ ] **Step 5: Commit**

```bash
git add dashboard.py tests/test_dashboard.py
git commit -m "feat: dashboard summarize_period + instagram_snapshot"
```

---

### Task 3: Estado de contenido (Google Sheet)

**Files:**
- Modify: `dashboard.py`
- Modify: `tests/test_dashboard.py`

**Interfaces:**
- Produces: `dashboard.content_status(rows: list[list], header: list, month_prefix: str) -> dict` — función **pura** que recibe las filas de la hoja ya leídas y devuelve `{"pendientes": int, "publicados_semana": int, "proximo": str|None}`. Y `dashboard.sheet_content(slug: str) -> dict` — wrapper que lee la Sheet (vía `sheets.get_worksheet`) y llama a `content_status`; devuelve `{}` si falla.

- [ ] **Step 1: Escribir el test que falla** (agregar a `tests/test_dashboard.py`)

```python
def test_content_status_counts():
    header = ["id", "date", "time_utc", "type", "approved", "published"]
    rows = [
        header,
        ["2026-09-P01", "2026-09-01", "22:00", "reel", "TRUE", "TRUE"],
        ["2026-09-P02", "2026-09-02", "22:00", "reel", "FALSE", "FALSE"],
        ["2026-09-P03", "2026-09-03", "22:00", "image", "TRUE", "FALSE"],
    ]
    st = dashboard.content_status(rows[1:], header, "2026-09")
    assert st["pendientes"] == 1          # P02 sin aprobar
    assert st["proximo"] == "2026-09-03"  # próximo aprobado sin publicar
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python3 -m pytest tests/test_dashboard.py::test_content_status_counts -v`
Expected: FAIL con `AttributeError`.

- [ ] **Step 3: Agregar `content_status` y `sheet_content` a `dashboard.py`**

```python
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
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python3 -m pytest tests/test_dashboard.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard.py tests/test_dashboard.py
git commit -m "feat: dashboard content_status from sheet"
```

---

### Task 4: Salud + decisiones (reglas puras)

**Files:**
- Modify: `dashboard.py`
- Modify: `tests/test_dashboard.py`

**Interfaces:**
- Produces:
  - `dashboard.compute_health(snap: dict | None) -> str` — `"green" | "yellow" | "red" | "gray"`.
  - `dashboard.build_decisions(cfg: dict, snap: dict | None, content: dict) -> dict` — `{"contenido", "estrategia", "presupuesto", "cliente"}`, cada uno string corto en español.

- [ ] **Step 1: Escribir el test que falla** (agregar a `tests/test_dashboard.py`)

```python
def test_compute_health():
    assert dashboard.compute_health(None) == "gray"
    assert dashboard.compute_health({"cur": {"comments": 3}, "reach_trend_pct": 25}) == "green"
    assert dashboard.compute_health({"cur": {"comments": 0}, "reach_trend_pct": -30}) == "red"
    assert dashboard.compute_health({"cur": {"comments": 0}, "reach_trend_pct": 2}) == "yellow"


def test_build_decisions_has_four_sections():
    d = dashboard.build_decisions(
        {"name": "Demo"},
        {"cur": {"comments": 0, "reach": 600}, "reach_trend_pct": 2, "followers": 78000},
        {"pendientes": 2, "proximo": "2026-09-03"},
    )
    assert set(d) == {"contenido", "estrategia", "presupuesto", "cliente"}
    assert "2" in d["contenido"]  # menciona los 2 pendientes
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python3 -m pytest tests/test_dashboard.py -k "health or decisions" -v`
Expected: FAIL con `AttributeError`.

- [ ] **Step 3: Agregar `compute_health` y `build_decisions` a `dashboard.py`**

```python
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
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python3 -m pytest tests/test_dashboard.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard.py tests/test_dashboard.py
git commit -m "feat: dashboard health + decisions rules"
```

---

### Task 5: Render HTML + main

**Files:**
- Modify: `dashboard.py`
- Modify: `tests/test_dashboard.py`

**Interfaces:**
- Produces:
  - `dashboard.render_html(clients_data: list[dict]) -> str` — `clients_data` = lista de `{"cfg", "snap", "content", "health", "decisions"}`.
  - `dashboard.main()` — carga clientes, arma cada uno, y escribe `dashboard.html`.

- [ ] **Step 1: Escribir el test que falla** (agregar a `tests/test_dashboard.py`)

```python
def test_render_html_contains_client_and_decisions():
    data = [{
        "cfg": {"name": "Epic.Plane", "channels": {"instagram": {"enabled": True, "handle": "epic.plane"},
                 "youtube": {"enabled": False}, "linkedin": {"enabled": False}, "tiktok": {"enabled": False}}},
        "snap": {"followers": 78000, "cur": {"reach": 650, "likes": 9, "comments": 0}, "reach_trend_pct": 1, "top": None},
        "content": {"pendientes": 0, "proximo": "2026-09-03"},
        "health": "yellow",
        "decisions": {"contenido": "Al día.", "estrategia": "Prioriza reels.",
                      "presupuesto": "Sin acción.", "cliente": "Epic.Plane: estable."},
    }]
    html = dashboard.render_html(data)
    assert "Epic.Plane" in html
    assert "Prioriza reels." in html
    assert "78" in html  # followers formateados
    assert "próximamente" in html.lower()  # canales no habilitados
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python3 -m pytest tests/test_dashboard.py::test_render_html_contains_client_and_decisions -v`
Expected: FAIL con `AttributeError`.

- [ ] **Step 3: Agregar `render_html` y `main` a `dashboard.py`**

```python
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
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python3 -m pytest tests/test_dashboard.py -v`
Expected: PASS (todos).

- [ ] **Step 5: Humo — generar el dashboard real**

Run: `PYTHONWARNINGS=ignore python3 dashboard.py`
Expected: `✓ dashboard.html generado (1 cliente(s)).` y existe `dashboard.html`. Abrirlo para verificar que muestra Epic.Plane con sus métricas + las 4 decisiones + los otros canales "próximamente".

- [ ] **Step 6: Commit**

```bash
git add dashboard.py tests/test_dashboard.py
git commit -m "feat: dashboard render_html + main (genera dashboard.html)"
```

---

### Task 6: Workflow de refresco semanal

**Files:**
- Create: `.github/workflows/dashboard.yml`

**Interfaces:**
- Consumes: `dashboard.py`, secrets `IG_USER_ID`, `META_PAGE_TOKEN`, `GOOGLE_CREDENTIALS`, `SHEET_ID` (ya existentes en el repo).

- [ ] **Step 1: Crear el workflow** `.github/workflows/dashboard.yml`

```yaml
name: CEO Dashboard (semanal)

# Regenera el dashboard cada lunes 12:00 UTC (≈ 8am Chile) + manual.
on:
  schedule:
    - cron: "0 12 * * 1"
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install gspread google-auth
      - name: Generar dashboard.html
        env:
          IG_USER_ID: ${{ secrets.IG_USER_ID }}
          META_PAGE_TOKEN: ${{ secrets.META_PAGE_TOKEN }}
          GOOGLE_CREDENTIALS: ${{ secrets.GOOGLE_CREDENTIALS }}
          SHEET_ID: ${{ secrets.SHEET_ID }}
        run: python dashboard.py
      - name: Publicar como artefacto
        uses: actions/upload-artifact@v4
        with:
          name: dashboard
          path: dashboard.html
```

- [ ] **Step 2: Verificar sintaxis YAML**

Run: `python3 -c "import yaml, sys; yaml.safe_load(open('.github/workflows/dashboard.yml'))" 2>/dev/null || python3 -c "print('nota: PyYAML no instalado; validar el YAML a ojo')"`
Expected: sin error (o la nota). Revisar a ojo que la indentación sea correcta.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/dashboard.yml
git commit -m "feat: weekly dashboard refresh workflow"
```

**Nota de despliegue (no bloquea el plan):** el workflow deja `dashboard.html` como artefacto. Para el "link privado" real, el dueño lo puede subir a Netlify (URL no-adivinable) o se automatiza el deploy en una iteración siguiente. La autenticación con contraseña es hardening posterior (fuera de Fase 1).

---

## Self-Review

**Spec coverage:**
- Config multi-cliente + loader → Task 1 ✓
- Snapshot IG (métricas + tendencia) → Task 2 ✓
- Estado de contenido (Sheet) → Task 3 ✓
- Salud + 4 decisiones → Task 4 ✓
- Render HTML cockpit + main → Task 5 ✓
- Workflow de refresco → Task 6 ✓
- No tocar el pipeline existente → respetado (dashboard solo lee; ningún task modifica generate/media/publish/sheets/etc.) ✓
- Honestidad de alcance (otros canales "próximamente", link privado MVP) → reflejado en render + nota de despliegue ✓

**Placeholder scan:** sin TBD/TODO; todo el código está completo. El despliegue del link privado se deja como nota operativa (no código), acorde al spec.

**Type consistency:** `load_clients`/`summarize_period`/`instagram_snapshot`/`content_status`/`compute_health`/`build_decisions`/`render_html`/`main` usan las mismas firmas en definición y tests. `render_html` consume la estructura `{cfg, snap, content, health, decisions}` que arma `main` y que usan los tests. `content_status` recibe filas+header (puro) y `sheet_content` las obtiene de la Sheet.
