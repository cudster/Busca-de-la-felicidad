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


# --- Curación de aviones específicos vía Wikimedia Commons ---------------------
# Pexels casi nunca devuelve el avión EXACTO (trae "aviones bonitos genéricos").
# Para estos modelos vamos directo a Commons y forzamos FOTO: una foto correcta
# gana siempre a un reel/foto equivocada. Pexels queda para reels spotter y
# conceptos genéricos (cabina, contrails, motor, etc.).
WIKI_UA = "EpicPlaneBot/1.0 (felipecood@gmail.com; personal aviation IG project)"
AIRCRAFT_WIKI = {
    "sr-71": "Lockheed SR-71 Blackbird", "blackbird": "Lockheed SR-71 Blackbird",
    "concorde": "Concorde airliner", "747": "Boeing 747 airline", "jumbo": "Boeing 747 airline",
    "767": "Boeing 767 airline", "777": "Boeing 777 airline", "787": "Boeing 787 airline",
    "dreamliner": "Boeing 787 airline", "a350": "Airbus A350", "a380": "Airbus A380",
    "a220": "Airbus A220", "md-11": "McDonnell Douglas MD-11", "md11": "McDonnell Douglas MD-11",
    "an-225": "Antonov An-225", "antonov": "Antonov An-124", "spitfire": "Supermarine Spitfire",
    "f-22": "F-22 Raptor", "raptor": "F-22 Raptor", "f-35": "F-35 Lightning II",
    "c-17": "Boeing C-17 Globemaster III", "globemaster": "Boeing C-17 Globemaster III",
    "gimli": "Air Canada Boeing 767", "pan am": "Pan Am Boeing 747",
    "typhoon": "Eurofighter Typhoon", "eurofighter": "Eurofighter Typhoon",
    "ge90": "General Electric GE90 engine", "dc-3": "Douglas DC-3",
}


def derive_wiki(post: dict) -> str | None:
    """Si el post trata de un avión específico, devuelve la búsqueda de Commons; si no, None."""
    text = (post.get("topic", "") + " " + post.get("visual_prompt", "")).lower()
    for k, v in AIRCRAFT_WIKI.items():
        if k in text:
            return v
    return None


def commons_photo(query: str, width: int = 1600) -> dict | None:
    """Trae una foto JPEG correcta y nítida de Wikimedia Commons (URL pública)."""
    url = ("https://commons.wikimedia.org/w/api.php?action=query&generator=search"
           "&gsrsearch=" + urllib.parse.quote(query + " aircraft") +
           "&gsrnamespace=6&gsrlimit=8&prop=imageinfo&iiprop=url|mime"
           "&iiurlwidth=" + str(width) + "&format=json")
    req = urllib.request.Request(url, headers={"User-Agent": WIKI_UA})
    try:
        data = json.load(urllib.request.urlopen(req, timeout=30))
    except (urllib.error.HTTPError, urllib.error.URLError):
        return None
    pages = (data.get("query", {}).get("pages", {}) or {}).values()
    for p in sorted(pages, key=lambda x: x.get("index", 999)):
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("mime") == "image/jpeg" and ii.get("thumburl"):
            asset = ii["thumburl"].split("?")[0]   # thumb nítido; sin el ?utm_source
            return {"url": asset, "thumb": asset}
    return None


def crop_45(url: str) -> str:
    """Recorta la foto a 4:5 (1080x1350) con enfoque inteligente, vía weserv.nl
    (CDN gratis, sin cuenta). 4:5 es el formato de foto que más ocupa el feed de IG."""
    return ("https://images.weserv.nl/?url=" + urllib.parse.quote(url, safe="") +
            "&w=1080&h=1350&fit=cover&a=attention&output=jpg")


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
    def score(f: dict) -> tuple:
        w, h = f.get("width") or 0, f.get("height") or 0
        vertical = 1 if h > w else 0                       # reels van verticales
        hd = 1 if f.get("quality") == "hd" else 0
        good_size = 1 if 720 <= h <= 1920 else 0           # ni muy chico ni gigante
        return (vertical, good_size, hd, -abs(1350 - h))
    for v in _get(url, key).get("videos", []):
        files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4"]
        if files:
            pick = max(files, key=score)
            return {"mp4": pick["link"], "thumb": v.get("image", ""), "by": v.get("user", {}).get("name", "")}
    return None


def media_for_post(post: dict, key: str, query: str) -> dict | None:
    # 1) ¿Avión específico? -> foto curada de Commons (garantiza que corresponde).
    wq = derive_wiki(post)
    if wq:
        ph = commons_photo(wq)
        if ph:
            a = crop_45(ph["url"])
            return {"asset_path": a, "preview_url": a,
                    "note": f"foto curada Wikimedia 4:5 · {wq}", "force_type": "image"}
        # si Commons no responde, cae a Pexels (mejor algo que nada).
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
    asset = ",".join(crop_45(p["large"]) for p in photos)
    warn = "" if photos[0].get("aviation") else "  ⚠ revisar (no confirmé aviación)"
    return {"asset_path": asset, "preview_url": crop_45(photos[0]["medium"]),
            "note": f"{len(photos)} foto(s) 4:5 · {photos[0]['by']}{warn}"}


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
        item = {"id": p["id"], "asset_path": m["asset_path"], "preview_url": m["preview_url"]}
        if m.get("force_type"):
            item["type"] = m["force_type"]
        items.append(item)

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

    # Escribir el tipo -> image para los posts de avión específico (foto curada).
    forced = [(it["id"], it["type"]) for it in items if it.get("type")]
    if forced:
        from gspread.utils import rowcol_to_a1
        _, ws = sheets.get_worksheet()
        rows = ws.get_all_values()
        col = rows[0].index("type")
        idrow = {r[0]: i + 2 for i, r in enumerate(rows[1:])}
        ws.batch_update(
            [{"range": rowcol_to_a1(idrow[i], col + 1), "values": [[t]]}
             for i, t in forced if i in idrow],
            value_input_option="USER_ENTERED",
        )
        print(f"  ✓ tipo → foto en {len(forced)} post(s) de avión específico.")
    print("  En la hoja, la columna 'preview' tiene un enlace 'ver foto': tócalo para ver la imagen.")


if __name__ == "__main__":
    main()
