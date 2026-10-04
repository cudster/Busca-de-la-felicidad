#!/usr/bin/env python3
"""
trends.py — Radar de tendencias de la comunidad de aviación.

Lee lo que la COMUNIDAD está subiendo y votando AHORA (no lo tuyo) para que el
motor de contenido vaya a la vanguardia en vez de inventar desde cero.

Fuente: RSS público de los subreddits de aviación (el JSON de Reddit está
bloqueado; el RSS no). El orden del feed "top of week" ES el ranking.

Uso:
    python3 trends.py                 # baja tendencias y guarda data/trends/latest.json
    python3 trends.py --show          # muestra el brief legible
    python3 trends.py --days 30       # ventana mensual en vez de semanal

El generador lo lee solo: si hay un archivo fresco, inyecta las tendencias en el
prompt (ver load_trends() en generate_content.py).
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import pathlib
import re
import time
import urllib.request
import urllib.error

ROOT = pathlib.Path(__file__).resolve().parent
OUT_DIR = ROOT / "data" / "trends"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) epicplane-trends/1.0"

# Comunidades por formato ganador (ver PILLAR_BRIEFS):
SUBS = {
    "aviation": "drama/spectacle",
    "avgeek": "avgeek culture",
    "planespotting": "spotting",
    "aviationmemes": "humor",      # el pilar humor vive aquí
    "flying": "pilot life",
    "airliners": "spotting",
}

# Ruido a descartar (posts que no sirven de inspiración de contenido)
SKIP = re.compile(r"\b(help|question|advice|which (school|course)|resume|logbook|"
                  r"interview|hiring|salary|medical|checkride|my first|rate my)\b", re.I)


def fetch_sub(sub: str, window: str = "week", limit: int = 8) -> list[dict]:
    """Reddit limita ráfagas (429): pausa entre intentos y reintenta con backoff."""
    url = f"https://www.reddit.com/r/{sub}/top/.rss?t={window}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    xml = None
    for intento in range(3):
        try:
            xml = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and intento < 2:
                time.sleep(10 * (intento + 1))  # 10s, luego 20s
                continue
            print(f"  ⚠️  r/{sub}: {e}")
            return []
        except Exception as e:
            print(f"  ⚠️  r/{sub}: {e}")
            return []
    if xml is None:
        return []
    entries = re.findall(r"<entry>(.*?)</entry>", xml, re.S)
    out = []
    for i, e in enumerate(entries):
        m = re.search(r"<title>(.*?)</title>", e, re.S)
        l = re.search(r'<link href="(.*?)"', e)
        if not m:
            continue
        title = html.unescape(re.sub(r"<.*?>", "", m.group(1))).strip()
        if not title or SKIP.search(title):
            continue
        out.append({"sub": sub, "theme": SUBS.get(sub, ""), "rank": i + 1,
                    "title": title, "url": l.group(1) if l else ""})
        if len(out) >= limit:
            break
    return out


def collect(window: str = "week") -> dict:
    print(f"📡 Leyendo la comunidad de aviación (top {window})…\n")
    items = []
    for sub in SUBS:
        got = fetch_sub(sub, window)
        print(f"  r/{sub:16} {len(got):2} señales")
        items.extend(got)
        time.sleep(6)     # ritmo amable con Reddit (limita por IP)
    data = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "window": window, "count": len(items), "items": items}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "latest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
    stamp = OUT_DIR / f"aviation-{dt.date.today().isoformat()}.json"
    stamp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ {len(items)} señales guardadas → data/trends/latest.json")
    return data


def show(data: dict | None = None) -> None:
    p = OUT_DIR / "latest.json"
    if data is None:
        if not p.exists():
            print("No hay tendencias guardadas. Corre: python3 trends.py")
            return
        data = json.loads(p.read_text(encoding="utf-8"))
    print(f"\n🛩️  LO QUE LA COMUNIDAD ESTÁ VIENDO (top {data['window']}, "
          f"{data['generated_at'][:16]})\n")
    by_sub: dict[str, list] = {}
    for it in data["items"]:
        by_sub.setdefault(it["sub"], []).append(it)
    for sub, items in by_sub.items():
        print(f"  r/{sub} — {SUBS.get(sub,'')}")
        for it in items[:5]:
            print(f"     {it['rank']}. {it['title'][:78]}")
        print()


def brief_for_prompt(max_items: int = 18) -> str:
    """Texto compacto para inyectar en el prompt del generador. '' si no hay datos frescos."""
    p = OUT_DIR / "latest.json"
    if not p.exists():
        return ""
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        gen = dt.datetime.fromisoformat(d["generated_at"])
    except Exception:
        return ""
    if (dt.datetime.now() - gen).days > 14:   # datos viejos = no sirven
        return ""
    lines = [f"- [{it['sub']}] {it['title'][:110]}" for it in d["items"][:max_items]]
    return ("\n".join(lines)) if lines else ""


def main() -> None:
    ap = argparse.ArgumentParser(description="Radar de tendencias de la comunidad de aviación.")
    ap.add_argument("--show", action="store_true", help="Muestra el brief guardado (sin bajar).")
    ap.add_argument("--days", type=int, default=7, help="Ventana: 7 (semana) o 30 (mes).")
    a = ap.parse_args()
    if a.show:
        show()
        return
    show(collect("month" if a.days > 7 else "week"))


if __name__ == "__main__":
    main()
