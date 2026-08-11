#!/usr/bin/env python3
"""
Epic.Plane — Módulo 5: Reporte de métricas semanal.

Baja los insights de la Instagram Graph API (alcance, guardados, compartidos,
likes, comentarios) de los posts recientes + del perfil, los compara con los
mejores posts históricos de la cuenta, y genera un reporte accionable estilo
"revisión semanal": qué funcionó / qué matar / qué duplicar.

Salida: reports/YYYY-WW.md

Uso:
    python3 metrics.py                 # última semana (7 días)
    python3 metrics.py --days 14       # ventana distinta

Requiere IG_USER_ID y META_PAGE_TOKEN en .env.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
GRAPH = "https://graph.facebook.com/v21.0/"


def env() -> dict:
    e = {}
    for l in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in l and not l.strip().startswith("#"):
            k, _, v = l.partition("=")
            e[k.strip()] = v.strip().strip('"').strip("'")
    return e


def g(path: str, params: dict, tok: str) -> dict:
    params = dict(params, access_token=tok)
    url = GRAPH + path + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return {"_error": json.loads(e.read().decode()).get("error", {}).get("message", "")}
        except Exception:
            return {"_error": str(e)}


def media_insights(mid: str, tok: str):
    """Alcance/guardados/compartidos de un post. Devuelve dict, o None si falta
    el permiso instagram_manage_insights."""
    for metrics in ("reach,saved,shares,total_interactions", "reach,saved,shares", "reach"):
        d = g(f"{mid}/insights", {"metric": metrics}, tok)
        if "_error" not in d:
            return {m["name"]: m["values"][0]["value"] for m in d.get("data", [])}
        if "permission" in (d.get("_error", "") or "").lower():
            return None  # falta instagram_manage_insights
    return {}


def load_pillar_map() -> dict:
    """Mapea el inicio del caption -> pilar, usando el calendario local."""
    m = {}
    for f in (ROOT / "calendar").glob("*.json"):
        try:
            for p in json.loads(f.read_text(encoding="utf-8")).get("posts", []):
                key = (p.get("caption_en", "")[:30]).strip().lower()
                if key:
                    m[key] = p.get("pillar", "")
        except Exception:
            pass
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()

    e = env()
    ig, tok = e.get("IG_USER_ID"), e.get("META_PAGE_TOKEN")
    if not ig or not tok:
        sys.exit("Faltan IG_USER_ID / META_PAGE_TOKEN en .env.")

    prof = g(ig, {"fields": "username,followers_count,media_count"}, tok)
    if "_error" in prof:
        sys.exit(f"Error Graph API: {prof['_error']}")
    followers = prof.get("followers_count", 0)

    media = g(ig + "/media", {
        "fields": "id,media_type,media_product_type,timestamp,permalink,like_count,comments_count,caption",
        "limit": "50",
    }, tok).get("data", [])

    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=args.days)
    pillars = load_pillar_map()

    def ts(p):
        # La Graph API devuelve p.ej. '2026-08-08T13:55:03+0000' (offset sin ':').
        return dt.datetime.strptime(p["timestamp"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)

    recent = [p for p in media if ts(p) >= cutoff]
    print(f"→ {len(recent)} posts en los últimos {args.days} días. Bajando insights…")
    insights_ok = True
    for p in recent:
        ins = media_insights(p["id"], tok)
        if ins is None:
            insights_ok = False
            ins = {}
        p["reach"] = ins.get("reach")
        p["saved"] = ins.get("saved")
        p["shares"] = ins.get("shares")
        p["inter"] = ins.get("total_interactions", (p.get("like_count", 0) + p.get("comments_count", 0)))
        key = (p.get("caption") or "")[:30].strip().lower()
        p["pillar"] = pillars.get(key, "")
    if not insights_ok:
        print("   ⚠️  Sin permiso instagram_manage_insights → alcance/guardados/compartidos = N/D.")

    # Mejores históricos (por likes) para tener el "formato ganador".
    top = sorted(media, key=lambda p: p.get("like_count", 0), reverse=True)[:6]

    # Métricas agregadas de la semana. (reach puede ser None si falta permiso.)
    n = len(recent)
    reach_sum = sum((p.get("reach") or 0) for p in recent)
    avg_like = round(sum(p.get("like_count", 0) for p in recent) / n, 1) if n else 0
    avg_reach = round(reach_sum / n, 1) if n else 0
    avg_com = round(sum(p.get("comments_count", 0) for p in recent) / n, 1) if n else 0
    tot_saved = sum((p.get("saved") or 0) for p in recent)
    tot_shares = sum((p.get("shares") or 0) for p in recent)
    reach_pct = round(avg_reach / followers * 100, 2) if (followers and insights_ok) else 0
    er = round(sum(p.get("inter", 0) for p in recent) / reach_sum * 100, 1) if reach_sum else 0

    write_report(args, prof, followers, recent, top, insights_ok, {
        "n": n, "avg_like": avg_like, "avg_reach": avg_reach, "avg_com": avg_com,
        "tot_saved": tot_saved, "tot_shares": tot_shares, "reach_pct": reach_pct, "er": er,
    })


def write_report(args, prof, followers, recent, top, insights_ok, agg) -> None:
    REPORTS.mkdir(exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    yr, wk, _ = now.isocalendar()
    path = REPORTS / f"{yr}-W{wk:02d}.md"

    def emoji_type(p):
        return "🎬 reel" if p.get("media_product_type") == "REELS" else \
               ("🖼️ carrusel" if p["media_type"] == "CAROUSEL_ALBUM" else "📷 imagen")

    def cell(v):
        return str(v) if (insights_ok and v is not None) else "N/D"

    L = []
    L.append(f"# Reporte semanal — Epic.Plane · {yr}-W{wk:02d}")
    L.append(f"\n_Generado {now:%Y-%m-%d %H:%M} UTC · @{prof.get('username')} · "
             f"{followers:,} seguidores · ventana {args.days} días_\n")

    L.append("## Resumen")
    L.append(f"- Posts publicados: **{agg['n']}**")
    L.append(f"- Likes promedio: **{agg['avg_like']}** · Comentarios promedio: **{agg['avg_com']}**")
    if insights_ok:
        L.append(f"- Alcance promedio: **{agg['avg_reach']:.0f}** ({agg['reach_pct']}% de tus seguidores)")
        L.append(f"- Guardados: **{agg['tot_saved']}** · Compartidos: **{agg['tot_shares']}** · "
                 f"Engagement rate: **{agg['er']}%**")
    else:
        L.append("- Alcance / guardados / compartidos: **N/D** — falta el permiso "
                 "`instagram_manage_insights` en el token (se agrega en 2 min, ver al final).")

    # Diagnóstico automático
    L.append("\n## Diagnóstico")
    like_pct = round(agg["avg_like"] / followers * 100, 3) if followers else 0
    L.append(f"- 🔴 **Engagement bajísimo**: {agg['avg_like']} likes promedio sobre {followers:,} seguidores "
             f"(~{like_pct}%). Lo esperable para una cuenta sana es 1-3%. La cuenta estuvo inactiva ~1 año: "
             f"Instagram dejó de mostrar el contenido a la mayoría; se **reconstruye gradualmente** con "
             f"constancia y señales de engagement.")
    if insights_ok and agg["reach_pct"] and agg["reach_pct"] < 5:
        L.append(f"- 🔴 **Alcance muy bajo** ({agg['reach_pct']}% de seguidores) — confirma el freno de alcance.")
    if agg["avg_com"] < 2:
        L.append(f"- 🔴 **Casi cero comentarios** ({agg['avg_com']} prom). Los comentarios son la señal más "
                 f"fuerte para el algoritmo. Falta el **gancho interactivo** que invita a responder.")
    if top:
        best = top[0]
        L.append(f"- 🟢 **Tu fórmula probada existe:** el mejor post histórico tiene **{best.get('like_count',0)} "
                 f"likes** y **{best.get('comments_count',0)} comentarios**. Cuando la cuenta crecía, funcionaba "
                 f"un estilo distinto al actual (ver abajo).")

    # Posts de la semana
    if recent:
        L.append("\n## Posts de esta semana")
        L.append("| Fecha | Tipo | Pilar | ♥ | 💬 | Alcance | Guard. | Comp. |")
        L.append("|---|---|---|--:|--:|--:|--:|--:|")
        for p in sorted(recent, key=lambda x: x.get("like_count", 0), reverse=True):
            L.append(f"| {p['timestamp'][:10]} | {emoji_type(p)} | {p.get('pillar','')} | "
                     f"{p.get('like_count',0)} | {p.get('comments_count',0)} | {cell(p.get('reach'))} | "
                     f"{cell(p.get('saved'))} | {cell(p.get('shares'))} |")

    # Fórmula ganadora histórica
    if top:
        L.append("\n## Qué funcionaba cuando la cuenta crecía (tus top históricos)")
        L.append("| ♥ | 💬 | Caption |")
        L.append("|--:|--:|---|")
        for p in top:
            cap = (p.get("caption") or "").split("\n")[0][:70]
            L.append(f"| {p.get('like_count',0)} | {p.get('comments_count',0)} | {cap} |")

    # Recomendaciones
    L.append("\n## Recomendaciones — qué matar / qué duplicar")
    L.append("**Matar:**")
    L.append("- Captions educativos largos sin gancho para comentar.")
    L.append("- Fotos genéricas de stock que no detienen el scroll.")
    L.append("\n**Duplicar (lo que a esta cuenta le funcionó):**")
    L.append("- 🗣️ **Ganchos interactivos**: \"guess the airport?\", \"😍 o 🤢?\", \"can you guess the engine?\", "
             "\"solve this\". Fueron los que generaron 40-114 comentarios.")
    L.append("- 🎥 **Repostear contenido épico de otros creadores CON crédito** (@usuario). Varios de los top "
             "eran reposts de reels de spotters — bajo esfuerzo, alto alcance.")
    L.append("- 😍 **Eye-candy aspiracional** (cabinas premium, tomas jaw-dropping), caption ultra-corto + emoji.")
    L.append("\n**Para reconstruir alcance (cuenta dormida):**")
    L.append("- Publicar con **constancia** y priorizar **Reels** (más alcance para recuperar).")
    L.append("- **Engagement diario**: responder cada comentario y comentar en cuentas del nicho (30 min/día).")
    L.append("- Usar **Stories** a diario (señal de cuenta activa) e invitar a comentar/guardar en cada post.")
    L.append("- Dar 3-4 semanas: el alcance de una cuenta revivida se recupera de a poco.")

    if not insights_ok:
        L.append("\n## Para desbloquear alcance / guardados / compartidos")
        L.append("El token actual no tiene el permiso `instagram_manage_insights`. Con él, este reporte "
                 "mostrará alcance real, guardados y compartidos (no solo likes/comentarios). Se agrega "
                 "regenerando el token en el Graph API Explorer con ese permiso marcado y corriendo "
                 "`setup_meta.py` de nuevo.")

    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"✓ Reporte: {path}")
    print(f"  {agg['n']} posts · ♥{agg['avg_like']} prom · alcance {agg['reach_pct']}% · ER {agg['er']}%")


if __name__ == "__main__":
    main()
