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

# Aviones/temas conocidos -> query de búsqueda. TODAS terminan en un sustantivo
# de aviación (airplane/jet/aircraft) para no traer resultados fuera de tema
# (ej. "SR-71 Blackbird" traía pájaros: por eso NO usamos "blackbird" a secas).
AIRCRAFT = {
    "sr-71": "military jet aircraft", "concorde": "concorde airplane",
    "787": "boeing 787 airplane", "dreamliner": "boeing 787 airplane", "a350": "airbus a350 airplane",
    "737": "boeing airplane", "767": "boeing airplane", "777": "boeing airplane", "747": "boeing 747 airplane",
    "spitfire": "vintage military airplane", "f-35": "fighter jet aircraft", "an-225": "cargo airplane",
    "antonov": "cargo airplane", "typhoon": "fighter jet aircraft", "eurofighter": "fighter jet aircraft",
    "super hornet": "fighter jet aircraft", "a320": "airbus airplane", "clipper": "seaplane airplane",
    "boeing 314": "seaplane airplane", "gimli": "boeing airplane", "aloha": "boeing 737 airplane",
}
SUBJECT = {
    "turbofan": "jet engine airplane", "engine": "jet engine airplane", "winglet": "airplane wing",
    "cockpit": "airplane cockpit", "fly-by-wire": "airplane cockpit",
    "cabin": "airplane cabin interior", "pressuriz": "airplane cabin interior",
    "instrument": "airplane cockpit", "carrier": "fighter jet aircraft carrier",
}
PILLAR_FALLBACK = {
    "technical_awe": "jet airplane", "spotting": "airplane flying sky",
    "aviation_story": "airliner airplane", "pilot_path": "airplane cockpit",
}

# Un resultado se acepta solo si su texto descriptivo (alt) menciona aviación.
AVIATION_WORDS = (
    "plane", "airplane", "aeroplane", "aircraft", "jet", "aviation", "flight",
    "flying", "airline", "airliner", "airport", "runway", "cockpit", "fighter",
    "boeing", "airbus", "fuselage", "wing", "hangar", "aviator", "helicopter",
)


def is_aviation(text: str) -> bool:
    t = (text or "").lower()
    return any(w in t for w in AVIATION_WORDS)


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
           "&per_page=20&orientation=portrait")
    photos = _get(url, key).get("photos", [])
    # Quedarse solo con fotos cuyo alt/descripción sea de aviación.
    good = [p for p in photos if is_aviation(p.get("alt", ""))]
    chosen = good[:n] if good else photos[:n]  # si ninguna pasa el filtro, no dejar el post vacío
    return [{"large": p["src"]["large2x"], "medium": p["src"]["medium"],
             "by": p.get("photographer", ""), "aviation": is_aviation(p.get("alt", ""))}
            for p in chosen]


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
    warn = "" if photos[0].get("aviation") else "  ⚠ revisar (no confirmé aviación)"
    return {"asset_path": asset, "preview_url": photos[0]["medium"],
            "note": f"{len(photos)} foto(s) · {photos[0]['by']}{warn}"}


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
    print(f"\n✓ {n_ok} post(s) con asset_path + enlace de preview escritos en la Google Sheet.")
    if missing:
        print(f"  (no encontré en la hoja: {', '.join(missing)} — ¿corriste --to-sheet?)")
    print("  En la hoja, la columna 'preview' tiene un enlace 'ver foto': tócalo para ver la imagen.")


if __name__ == "__main__":
    main()
