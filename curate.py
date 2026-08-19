"""Trae noticias del nicho por RSS y guarda una lista corta 'reaccionable'
para que el generador reaccione a lo que pasa (data/news/<niche>.json)."""

from __future__ import annotations

import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def parse_rss(xml: str) -> list[dict]:
    root = ET.fromstring(xml)
    items = []
    for it in root.iter("item"):
        def text(tag: str) -> str:
            el = it.find(tag)
            return (el.text or "").strip() if el is not None else ""
        items.append({
            "title": text("title"),
            "summary": text("description"),
            "url": text("link"),
            "date": text("pubDate"),
        })
    return items


def select_reactionable(items: list[dict], limit: int = 5) -> list[dict]:
    out, seen = [], set()
    for it in items:
        if not it.get("title") or not it.get("url"):
            continue
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        out.append(it)
        if len(out) >= limit:
            break
    return out


def fetch_source(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def write_news(niche: str, items: list[dict], base: Path = ROOT) -> Path:
    path = base / "data" / "news" / f"{niche}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    niche = sys.argv[1] if len(sys.argv) > 1 else "epic-plane"
    cfg = json.loads((ROOT / "curate_sources.json").read_text(encoding="utf-8"))
    sources = cfg.get(niche, [])
    collected = []
    for url in sources:
        try:
            collected.extend(parse_rss(fetch_source(url)))
        except Exception as e:
            print(f"  ! fuente falló ({url}): {e}")
    items = select_reactionable(collected, limit=8)
    path = write_news(niche, items)
    print(f"✓ {len(items)} noticias guardadas en {path}")


if __name__ == "__main__":
    main()
