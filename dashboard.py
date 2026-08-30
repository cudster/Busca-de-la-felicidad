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
