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
import re
import subprocess
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
    "staggerwing": "Beechcraft Staggerwing", "beechcraft": "Beechcraft Staggerwing",
    "mriya": "Antonov An-225", "737": "Boeing 737 airline", "md-11": "McDonnell Douglas MD-11",
    "a320": "Airbus A320 airline", "a321": "Airbus A321 airline",
    "embraer": "Embraer E-Jet airline", "atr 72": "ATR 72 airline",
}


# El post P19 era sobre FLEXIÓN DE ALA y la búsqueda se hizo por "Boeing 777",
# que trae un lateral genérico del avión — el fenómeno no sale en la foto. Cuando
# el post trata de un FENÓMENO, el fenómeno manda sobre el modelo de avión.
FENOMENO_WIKI = {
    # Cada consulta fue PROBADA contra Commons; las que devolvían basura
    # (cabina de 1928, un Eurofighter para "tren de aterrizaje") se sacaron a
    # propósito: es mejor caer al avión genérico que ilustrar con algo ajeno.
    "wing flex": "wing bending flight",
    "wing bend": "wing bending flight",
    "winglet": "winglet wingtip",
    "sharklet": "winglet wingtip",
    "contrail": "contrail sky",
    "vortex": "wingtip vortex",
    "de-ic": "aircraft deicing",
    "deic": "aircraft deicing",
    "hangar": "aircraft hangar maintenance",
    # Claves LARGAS a propósito: "cabin" suelto aparece en medio prompt de aviación.
    "business class": "business class cabin aircraft",
    "lie-flat": "business class cabin aircraft",
    "premium cabin": "business class cabin aircraft",
    "turbofan": "turbofan engine fan blades",
    "fan blade": "turbofan engine fan blades",
}


# Si el post nombra una AEROLÍNEA, esa cabina/avión manda sobre cualquier otra
# coincidencia. Antes el desempate era por largo de clave, y "lie-flat" (8) le
# ganaba a "jetblue" (7): un post de JetBlue salía con una cabina demo de Airbus
# con "A220/AIRSPACE" escrito en los asientos. El largo no es una jerarquía.
AEROLINEA_WIKI = {
    "jetblue": "JetBlue Airways aircraft interior",
    "emirates": "Emirates Airbus A380",
    "air canada": "Air Canada Boeing 767",
    "lufthansa": "Lufthansa Boeing 747",
    "british airways": "British Airways Boeing 747",
    "pan am": "Pan Am Boeing 747",
    "singapore airlines": "Singapore Airlines Boeing 777",
    "qantas": "Qantas Airbus A380",
    "united": "United Airlines Boeing 777",
    "delta": "Delta Air Lines Airbus A350",
}


# La aerolínea SOLO manda en posts de INTERIOR. Si no, "British Airways livery"
# (que aparece en el prompt de la Concorde) mandaba a buscar un 747 de BA para
# un post sobre la Concorde. Nombrar una librea no convierte al post en uno
# sobre esa aerolínea; el modelo de avión sigue siendo más específico.
ES_INTERIOR = re.compile(r"cabin|interior|seat|lie-flat|class|aisle|legroom|galley|lavator", re.I)


def derive_aerolinea(post: dict) -> str | None:
    """Aerolínea nombrada, pero sólo si el post es de interior/cabina."""
    text = (post.get("topic", "") + " " + post.get("visual_prompt", "")).lower()
    if not ES_INTERIOR.search(text):
        return None
    for k in sorted(AEROLINEA_WIKI, key=len, reverse=True):
        if k in text:
            return AEROLINEA_WIKI[k]
    return None


def derive_fenomeno(post: dict) -> str | None:
    """Si el post trata de un fenómeno (no de un avión), devuelve esa búsqueda."""
    aero = derive_aerolinea(post)
    if aero:
        return aero
    # Si el TITULO ya nombra un avión concreto, ese manda: el post es sobre ESE avión.
    topic = (post.get("topic", "") or "").lower()
    if any(k in topic for k in _claves_por_especificidad(AIRCRAFT_WIKI)):
        return None
    text = (post.get("topic", "") + " " + post.get("visual_prompt", "")).lower()
    for k in sorted(FENOMENO_WIKI, key=len, reverse=True):
        if k in text:
            return FENOMENO_WIKI[k]
    return None


# Apodos inequívocos: identifican un avión CONCRETO mejor que su número de
# modelo. "gimli" es el 767 de Air Canada, no un 767 cualquiera; si gana "767"
# el post del Gimli Glider vuelve a salir con el avión de otra aerolínea.
APODOS = ("gimli", "mriya", "staggerwing", "blackbird", "pan am", "globemaster",
          "dreamliner", "jumbo", "raptor")


def _claves_por_especificidad(d: dict) -> list:
    """Primero las claves con número de modelo, después las de marca.

    El largo de la clave NO es jerarquía: "antonov" (7) le ganaba a "an-225" (6)
    y el post del An-225 —el avión de seis motores, único en el mundo— salía con
    un An-124, que es otro avión. Un número de modelo siempre es más específico
    que un nombre de fabricante.
    """
    apodos  = [k for k in d if k in APODOS]
    con_num = [k for k in d if k not in APODOS and any(c.isdigit() for c in k)]
    sin_num = [k for k in d if k not in APODOS and not any(c.isdigit() for c in k)]
    return (sorted(apodos, key=len, reverse=True) + sorted(con_num, key=len, reverse=True)
            + sorted(sin_num, key=len, reverse=True))


def derive_aircraft_wiki(post: dict) -> str | None:
    """Si el post trata de un avión específico, devuelve la búsqueda de Commons; si no, None."""
    # El TOPIC es el tema del post; el visual_prompt es decoración. Se mira el
    # topic primero para que "MD-11 — Underrated Trijet" no termine ilustrado con
    # un winglet sólo porque el prompt menciona winglets de pasada.
    for campo in ("topic", "visual_prompt"):
        text = (post.get(campo, "") or "").lower()
        for k in _claves_por_especificidad(AIRCRAFT_WIKI):
            if k in text:
                return AIRCRAFT_WIKI[k]
    return None


# Commons rankea por relevancia de texto, no por tono: buscando "Boeing 777
# airline" devolvió "Japan_Airlines_777_Engine_Failure_on_Departure" y ESA foto
# se publicó bajo un texto que decía que volar es seguro (2026-09-28, P19).
# Nunca una foto de incidente: ni para ilustrar, ni por accidente.
FOTO_PROHIBIDA = re.compile(
    r"fire|crash|accident|incident|failure|burn|smoke|wreck|emergency|explos|"
    r"collision|damag|destroy|disaster|hijack|shot[_ ]down|shootdown|debris|"
    r"memorial|funeral|victim|fatal|mayday|evacuat|skidded|overrun",
    re.I)


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
        if FOTO_PROHIBIDA.search(p.get("title", "")):
            continue                               # incidente/accidente: descartar
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


def ffprobe_available() -> bool:
    """¿Está ffprobe? Sin él NO podemos garantizar que el reel tenga sonido."""
    try:
        subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=10)
        return True
    except Exception:
        return False


# Un stock puede traer una pista AAC COMPLETAMENTE MUDA: tener pista no es tener
# sonido. Por eso medimos volumen real; por debajo de este umbral es silencio.
SILENCE_DBFS = -50.0


def _has_audio(url: str, seconds: int = 8) -> bool | None:
    """True si el mp4 remoto trae audio QUE SUENA (no solo una pista muda).

    Mide el volumen medio de los primeros segundos con ffmpeg volumedetect.
    None = no se pudo verificar (ffmpeg ausente): nunca se asume que hay sonido.
    """
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=codec_name", "-of", "csv=p=0", url],
            capture_output=True, text=True, timeout=30)
        if not out.stdout.strip():
            return False                      # ni siquiera hay pista
    except FileNotFoundError:
        return None                           # ffprobe no instalado
    except Exception:
        return False
    try:
        p = subprocess.run(
            ["ffmpeg", "-hide_banner", "-t", str(seconds), "-i", url,
             "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True, timeout=180)
        m = re.search(r"mean_volume:\s*(-?[\d.]+|-inf) dB", p.stderr)
        if not m:
            return False
        mean = -999.0 if m.group(1) == "-inf" else float(m.group(1))
        return mean > SILENCE_DBFS            # ¿suena de verdad?
    except FileNotFoundError:
        return None
    except Exception:
        return False


def search_video(query: str, key: str) -> dict | None:
    # per_page alto: los reels MUDOS son el problema — necesitamos candidatos para
    # encontrar uno CON audio (el rugido del motor > silencio; IG no deja poner
    # audio de tendencia por API, así que el audio natural del clip es la mejor vía).
    url = ("https://api.pexels.com/videos/search?query=" + urllib.parse.quote(query) +
           "&per_page=15&orientation=portrait")
    def score(f: dict) -> tuple:
        w, h = f.get("width") or 0, f.get("height") or 0
        vertical = 1 if h > w else 0                       # reels van verticales
        hd = 1 if f.get("quality") == "hd" else 0
        good_size = 1 if 720 <= h <= 1920 else 0           # ni muy chico ni gigante
        return (vertical, good_size, hd, -abs(1350 - h))
    if not ffprobe_available():
        # Antes se devolvía el primer candidato "a ciegas" -> por eso salían reels mudos.
        # Preferimos fallar fuerte: sin ffprobe no hay garantía de sonido.
        sys.exit("✋ Falta ffprobe (viene con ffmpeg) y sin él no puedo garantizar que el "
                 "reel tenga audio.\n   Instálalo con:  brew install ffmpeg")
    fallback = None
    for v in _get(url, key).get("videos", []):
        files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4"]
        if not files:
            continue
        pick = max(files, key=score)
        cand = {"mp4": pick["link"], "thumb": v.get("image", ""),
                "by": v.get("user", {}).get("name", ""), "has_audio": True}
        if fallback is None:
            fallback = {**cand, "has_audio": False}
        if _has_audio(pick["link"]):     # ¡tiene audio! este es el bueno
            return cand
    # Ninguno tenía audio: devolvemos el mejor igual, marcado (mejor algo que nada).
    if fallback:
        fallback["by"] = fallback["by"] + " · ⚠ SIN AUDIO"
    return fallback


def media_for_post(post: dict, key: str, query: str) -> dict | None:
    # 1) ¿Avión específico? -> foto curada de Commons (garantiza que corresponde).
    # Orden: fenómeno -> avión específico -> Pexels. Si el fenómeno no devuelve
    # foto, NO se queda sin imagen: cae al modelo de avión como antes.
    candidatas = [q for q in (derive_fenomeno(post), derive_aircraft_wiki(post)) if q]
    for wq in candidatas:
        ph = commons_photo(wq)
        if ph:
            a = crop_45(ph["url"])
            return {"asset_path": a, "preview_url": a,
                    "note": f"foto curada Wikimedia 4:5 · {wq}", "force_type": "image"}
    # si ninguna candidata dio foto, cae a Pexels (mejor algo que nada).
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
