#!/usr/bin/env python3
"""
Epic.Plane — Módulo 3b: Pipeline de media (Pexels).

Para cada post del calendario busca una foto/video REAL de aviación en Pexels
(gratis, licencia de uso comercial), y escribe en la Google Sheet:
  - asset_path : la(s) URL(s) pública(s) para publicar en Instagram.
  - preview    : una miniatura =IMAGE(...) para que revises desde el celular.

Convención por tipo de post:
  - image    -> 1 foto.
  - carousel -> hasta 4 fotos (asset_path separadas por coma).
  - reel     -> 1 video (mp4); la miniatura usa el thumbnail del video.

Uso:
  python3 media.py --month 2026-08
  python3 media.py --month 2026-08 --dry-run
  python3 media.py --month 2026-08 --post P05                 # solo un post
  python3 media.py --month 2026-08 --post P05 --query "flight instrument panel"  # forzar búsqueda

Requiere PEXELS_API_KEY en .env.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CALENDAR_DIR = ROOT / "calendar"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")
CAROUSEL_FRAMES = 4

# Aviones/temas conocidos -> query de búsqueda limpia en Pexels.
AIRCRAFT = {
    "sr-71": "SR-71 Blackbird", "blackbird": "SR-71 Blackbird", "concorde": "Concorde",
    "787": "Boeing 787", "dreamliner": "Boeing 787", "a350": "Airbus A350",
    "737": "Boeing 737", "767": "Boeing 767", "777": "Boeing 777", "747": "Boeing 747",
    "spitfire": "Spitfire aircraft", "f-35": "F-35 fighter jet", "an-225": "Antonov aircraft",
    "antonov": "Antonov aircraft", "typhoon": "Eurofighter Typhoon", "eurofighter": "Eurofighter Typhoon",
    "super hornet": "F/A-18 fighter jet", "a320": "Airbus A320", "clipper": "seaplane",
    "boeing 314": "seaplane", "gimli": "Boeing 767", "aloha": "Boeing 737",
}
SUBJECT = {
    "turbofan": "jet engine", "engine": "jet engine", "winglet": "airplane wing",
    "cockpit": "airplane cockpit", "fly-by-wire": "airplane cockpit",
    "cabin": "airplane cabin", "pressuriz": "airplane cabin", "instrument": "airplane cockpit",
    "carrier": "aircraft carrier jet",
}
PILLAR_FALLBACK = {
    "technical_awe": "jet aircraft", "spotting": "airplane sky",
    "aviation_story": "airliner", "pilot_path": "airplane cockpit",
}


def load_key() -> str:
    for l in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if l.startswith("PEXELS_API_KEY="):
            return l.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("Falta PEXELS_API_KEY en .env.")


def derive_query(post: dict) -> str:
    text = (post.get("topic", "") + " " + post.get("visual_prompt", "")).lower()
    for k, v in AIRCRAFT.items():
        if k in text:
            return v
    for k, v in SUBJECT.items():
        if k in text:
            return v
    return PILLAR_FALLBACK.get(post.get("pillar", ""), "airplane")


def _get(url: str, key: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": UA})
    try:
        return json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Pexels HTTP {e.code}: {e.read().decode('utf-8','replace')[:150]}") from None


def search_photos(query: str, key: str, n: int) -> list[dict]:
    url = ("https://api.pexels.com/v1/search?query=" + urllib.parse.quote(query) +
           f"&per_page={max(n, 1)}&orientation=portrait")
    photos = _get(url, key).get("photos", [])
    return [{"large": p["src"]["large2x"], "medium": p["src"]["medium"],
             "by": p.get("photographer", "")} for p in photos[:n]]


def search_video(query: str, key: str) -> dict | None:
    url = ("https://api.pexels.com/videos/search?query=" + urllib.parse.quote(query) +
           "&per_page=5&orientation=portrait")
    for v in _get(url, key).get("videos", []):
        files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4"]
        # Preferir el mp4 más grande con ancho <= 1080 (apto para reel vertical).
        files.sort(key=lambda f: (f.get("width") or 0))
        pick = next((f for f in reversed(files) if (f.get("width") or 0) <= 1080), files[-1] if files else None)
        if pick:
            return {"mp4": pick["link"], "thumb": v.get("image", ""), "by": v.get("user", {}).get("name", "")}
    return None


def media_for_post(post: dict, key: str, query: str) -> dict | None:
    t = post.get("type")
    if t == "reel":
        vid = search_video(query, key)
        if not vid:
            return None
        return {"asset_path": vid["mp4"], "preview_url": vid["thumb"], "note": f"video · {vid['by']}"}
    n = CAROUSEL_FRAMES if t == "carousel" else 1
    photos = search_photos(query, key, n)
    if not photos:
        return None
    asset = ",".join(p["large"] for p in photos)
    return {"asset_path": asset, "preview_url": photos[0]["medium"],
            "note": f"{len(photos)} foto(s) · {photos[0]['by']}"}


def main() -> None:
    ap = argparse.ArgumentParser(description="Epic.Plane — Pipeline de media Pexels (Módulo 3b).")
    ap.add_argument("--month", required=True, help="Mes del calendario (YYYY-MM).")
    ap.add_argument("--post", help="Solo este post (ej P05).")
    ap.add_argument("--query", help="Forzar la búsqueda (con --post).")
    ap.add_argument("--dry-run", action="store_true", help="Muestra sin escribir en la hoja.")
    args = ap.parse_args()

    path = CALENDAR_DIR / f"{args.month}.json"
    if not path.exists():
        sys.exit(f"No existe {path}.")
    posts = json.loads(path.read_text(encoding="utf-8"))["posts"]
    if args.post:
        pid = args.post if args.post.startswith(args.month) else f"{args.month}-{args.post.upper()}"
        posts = [p for p in posts if p["id"] == pid]
        if not posts:
            sys.exit(f"No encontré el post {pid}.")

    key = load_key()
    items = []
    print(f"→ Buscando media en Pexels para {len(posts)} post(s)…")
    for p in posts:
        query = args.query if (args.query and args.post) else derive_query(p)
        try:
            m = media_for_post(p, key, query)
        except RuntimeError as e:
            print(f"   ⚠️  {p['id']}: {e}")
            continue
        if not m:
            print(f"   ⚠️  {p['id']} [{p['type']}] sin resultados para '{query}'")
            continue
        print(f"   ✓ {p['id']} [{p['type']:8}] '{query}' → {m['note']}")
        items.append({"id": p["id"], "asset_path": m["asset_path"], "preview_url": m["preview_url"]})

    if args.dry_run:
        print(f"\n(DRY RUN) {len(items)} post(s) tendrían media. No se escribió en la hoja.")
        return
    if not items:
        print("Nada que escribir.")
        return

    import sheets
    n_ok, missing = sheets.batch_set_media(items)
    print(f"\n✓ {n_ok} post(s) con asset_path + miniatura escritos en la Google Sheet.")
    if missing:
        print(f"  (no encontré en la hoja: {', '.join(missing)} — ¿corriste --to-sheet?)")
    print("  Abre la hoja en el celular: la columna 'preview' muestra la miniatura para revisar.")


if __name__ == "__main__":
    main()
