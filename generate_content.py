#!/usr/bin/env python3
"""
Epic.Plane — Módulo 1: Generador de contenido.

Genera el calendario mensual de contenido para la cuenta de Instagram Epic.Plane
(nicho aviación, audiencia ~80% angloparlante) llamando a la API de Anthropic.

Flujo de trabajo:
    1. Este script arma el "esqueleto" del mes (fechas, horarios, pilar de
       contenido y tipo de post) de forma determinística, respetando las reglas
       del CLAUDE.md (4-5 posts/semana, distribución de pilares, horarios US/UK).
    2. La API rellena la parte creativa de cada post (topic, hook, caption EN,
       caption ES, hashtags, visual prompt).
    3. Se escribe el calendario a  calendar/YYYY-MM.json  (schema del CLAUDE.md)
       y un export legible a  content/YYYY-MM.md  para que revises rápido.
    4. Tú revisas el .md, editas lo que quieras en el .json y marcas
       "approved": true  en los posts que apruebas. Eso los deja listos para
       publicar (Módulo 2).

Uso:
    python3 generate_content.py                 # mes actual
    python3 generate_content.py --month 2026-09 # un mes específico
    python3 generate_content.py --force         # regenera aunque el mes ya exista
    python3 generate_content.py --month 2026-08 --export-only  # solo re-exporta el .md desde el .json

Requisitos:
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=sk-ant-...   (o ponlo en un archivo .env)
"""

from __future__ import annotations

import argparse
import calendar as _calendar
import datetime as dt
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

# Modelo definido en el CLAUDE.md. Sonnet es la opción costo-eficiente correcta
# para generación de contenido a este volumen (20 posts/mes) dentro del
# presupuesto del proyecto.
DEFAULT_MODEL = "claude-sonnet-4-6"

POSTS_PER_MONTH = 20

# Directorio raíz del proyecto (donde vive este script).
ROOT = Path(__file__).resolve().parent
CALENDAR_DIR = ROOT / "calendar"
CONTENT_DIR = ROOT / "content"

# Días de la semana en que se publica (0 = lunes ... 6 = domingo).
# Lun, Mar, Mié, Jue, Sáb -> 5 posts por semana como máximo.
POSTING_WEEKDAYS = [0, 1, 2, 3, 5]

# Horarios objetivo optimizados para audiencia US/UK (hora del Este de EE.UU.).
#   13:00 UTC  ~= 8-9 AM ET   (bloque mañana)
#   22:00 UTC  ~= 5-6 PM ET   (bloque tarde)
TIME_MORNING_UTC = "13:00"
TIME_EVENING_UTC = "22:00"

# Patrón fijo de pilares para las 20 publicaciones del mes.
# Respeta la distribución del CLAUDE.md e intercala para dar variedad al feed:
#   technical_awe  = 8 (40%)  -> asombro técnico
#   spotting       = 6 (30%)  -> spotting / visual épico
#   aviation_story = 4 (20%)  -> historias de aviación
#   pilot_path     = 2 (10%)  -> camino del piloto (aquí va el CTA de afiliado)
PILLAR_PATTERN = [
    "drama",      # 1
    "game",       # 2
    "spotting",   # 3
    "humor",      # 4
    "drama",      # 5
    "spotting",   # 6
    "game",       # 7
    "opinion",    # 8
    "spotting",   # 9
    "humor",      # 10
    "drama",      # 11
    "pilot_path", # 12
    "game",       # 13
    "spotting",   # 14
    "humor",      # 15
    "opinion",    # 16
    "drama",      # 17
    "spotting",   # 18
    "game",       # 19
    "spotting",   # 20
]  # drama=4, game=4, spotting=6, humor=3, opinion=2, pilot_path=1
# Reequilibrado 2026-09-21 con datos reales: los históricos ganadores (500-1.700 likes)
# eran drama/humor/juego/opinión. Lo educativo daba 10 likes y 0 guardados.

# Descripción de cada pilar para el prompt del modelo.
# Pilares REESCRITOS (2026-09-21) a partir de los datos reales de la cuenta: los
# posts históricos con más guardados/likes (2021-22: 500-1.700 likes) eran DRAMA,
# HUMOR, JUEGOS y OPINIÓN — entretenimiento de comunidad. Los pilares educativos
# anteriores producían "placa de museo" (10 likes, 0 guardados). No enseñes: haz
# sentir, reír o jugar.
PILLAR_BRIEFS = {
    "drama": (
        "DRAMA / spectacle: a close call, a crosswind landing that fights back, a go-around, "
        "extreme weather, a moment that makes you gasp. Write it like you just watched it happen "
        "and can't believe it. Short, breathless, emotional. NOT a lesson — a reaction. "
        "Never real tragedy or fatal accidents; awe and adrenaline, not disaster."
    ),
    "humor": (
        "HUMOR / relatable: the small absurdities every flyer and avgeek knows — the middle seat, "
        "the boarding scrum, the guy clapping on landing, delays, avgeek obsessions. Write it like "
        "a friend posting a meme caption, not like a brand. Self-aware, funny, human. "
        "This is the format that historically got this account 500+ likes."
    ),
    "game": (
        "GAME / challenge: make them PLAY. 'Can you name this aircraft?', 'Spot what's wrong in "
        "this photo', 'Guess the airline from the livery', 'How many can you identify?'. State the "
        "challenge in one line and ask them to drop their answer. Participation is the whole point — "
        "the caption is an invitation, never an explanation."
    ),
    "opinion": (
        "OPINION / this-or-that: a friendly, polarizing question the community will argue about. "
        "'Best-looking jet ever: this or that?', 'Window or aisle?', '😍 or 🤢?'. Take a light "
        "stance or present two sides. Must be genuinely divisive but never political or offensive."
    ),
    "spotting": (
        "SPOTTING / pure spectacle: one striking aircraft moment where the visual does everything. "
        "One evocative line about what makes it beautiful or rare — name the aircraft. "
        "Think 'this vortex looks like it's from a movie', not a physics explanation."
    ),
    "pilot_path": (
        "PILOT PATH: the dream of flying — what it feels like to get there, the view from the "
        "office, the moment it becomes real. Aspirational and emotional, never a tuition brochure. "
        "This is the post that carries the Pilot Institute affiliate CTA when assigned."
    ),
}

# Cadencia semanal fija (decisión del dueño 2026-09-01): 3 reels + 2 posts por
# semana. El tipo depende SOLO del día de la semana en que cae la publicación:
#   Lun (0), Mié (2), Sáb (5) -> REEL   (3/semana; llegan a no-seguidores vía Reels/Explore)
#   Mar (1), Jue (3)          -> POST   (2/semana; imagen)
# Así cada semana completa queda exactamente 3 reels + 2 imágenes, y el feed
# mantiene un ritmo predecible.
REEL_WEEKDAYS = {0, 2, 5}   # lunes, miércoles, sábado


def _post_type(weekday: int, reel_weekdays: set | None = None) -> str:
    rw = REEL_WEEKDAYS if reel_weekdays is None else reel_weekdays
    return "reel" if weekday in rw else "image"


def _extension_for_type(post_type: str) -> str:
    return "mp4" if post_type == "reel" else "jpg"


# ---------------------------------------------------------------------------
# Calendario de ocasiones (fechas fuertes) — hace que el contenido se anticipe
# a Día de la Madre, Pascua, Fiestas Patrias, Navidad, etc. y salga temático.
# ---------------------------------------------------------------------------

OCCASIONS_DIR = ROOT / "data" / "occasions"


def load_occasions(niche: str) -> list[dict]:
    """Carga las ocasiones del nicho: data/occasions/<niche>.json.
    Devuelve [] si no existe (el feature es opcional y no rompe nada)."""
    path = OCCASIONS_DIR / f"{niche}.json"
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for o in raw.get("occasions", []):
        try:
            o = dict(o)
            o["_date"] = dt.date.fromisoformat(o["date"])
            o["lead_days"] = int(o.get("lead_days", 10))
            out.append(o)
        except Exception:
            continue
    return out


def tag_occasions(skeleton: list[dict], occasions: list[dict]) -> list[dict]:
    """Etiqueta cada post cuya fecha caiga en la ventana [fecha - lead_days, fecha]
    de una ocasión. Si hay varias, elige la más próxima. Añade slot['occasion']."""
    if not occasions:
        return skeleton
    for slot in skeleton:
        d = dt.date.fromisoformat(slot["date"])
        candidates = [
            o for o in occasions
            if (o["_date"] - dt.timedelta(days=o["lead_days"])) <= d <= o["_date"]
        ]
        if not candidates:
            continue
        best = min(candidates, key=lambda o: (o["_date"] - d).days)
        slot["occasion"] = {
            "name": best["name"],
            "date": best["date"],
            "angle": best.get("angle", ""),
            "days_until": (best["_date"] - d).days,
        }
    return skeleton


def load_rituals(niche: str) -> dict[int, dict]:
    """Carga los rituales de comunidad del nicho: data/rituals/<niche>.json.
    Devuelve {} si no existe (opcional, no rompe nada). Indexa por weekday."""
    path = ROOT / "data" / "rituals" / f"{niche}.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[int, dict] = {}
    for r in raw.get("rituals", []):
        try:
            out[int(r["weekday"])] = {"name": r["name"], "brief": r.get("brief", ""),
                                      # opcional: "reel" o "image" para acotar el ritual a
                                      # un tipo. Si no se indica, vale para el tipo que
                                      # toque ese día (un ritual de foto es igual de válido).
                                      "type": r.get("type")}
        except Exception:
            continue
    return out


def tag_rituals(skeleton: list[dict], rituals: dict[int, dict]) -> list[dict]:
    """Etiqueta los posts cuyo día de la semana tenga un ritual.

    Las ocasiones tienen prioridad: si el post ya es temático, no se le pone ritual.
    Un ritual puede acotarse a un tipo con el campo opcional "type" ("reel"/"image");
    sin ese campo sirve para días de foto también (hay rituales que son de foto,
    como presentar una pieza de la semana).
    """
    if not rituals:
        return skeleton
    # MÁXIMO 1 RITUAL POR SEMANA (2026-09-21). Antes caían lunes Y sábado, o sea 2 de
    # cada 3 reels, y se comían los formatos que los datos muestran como ganadores
    # (drama/humor/opinion). Se alterna por número de semana ISO para que ambos
    # rituales sigan apareciendo y mantengan el efecto de "evento recurrente".
    orden = sorted(rituals.keys())
    usados: set[tuple] = set()
    for slot in skeleton:
        if slot.get("occasion"):
            continue  # la ocasión manda
        d = dt.date.fromisoformat(slot["date"])
        r = rituals.get(d.weekday())
        if not r:
            continue
        if r.get("type") and r["type"] != slot.get("type"):
            continue  # el ritual pide otro tipo de post
        semana = d.isocalendar()[:2]          # (año, semana ISO)
        if semana in usados:
            continue                           # esta semana ya tiene su ritual
        if len(orden) > 1:
            # alterna: semanas pares -> primer ritual, impares -> segundo, etc.
            preferido = orden[d.isocalendar()[1] % len(orden)]
            if d.weekday() != preferido:
                continue
        usados.add(semana)
        slot["ritual"] = {"name": r["name"], "brief": r["brief"]}
    return skeleton


# ---------------------------------------------------------------------------
# 1. Esqueleto del calendario (determinístico, sin IA)
# ---------------------------------------------------------------------------

def build_schedule(year: int, month: int, cfg: dict | None = None) -> list[dict]:
    """Arma las ranuras del mes: fecha, hora, pilar, tipo, rutas de assets.
    cfg (por nicho) define posts_per_month, reel_weekdays, pillar_pattern y CTA."""
    cfg = cfg or load_content_config("epic-plane")
    posts_per_month = int(cfg.get("posts_per_month", POSTS_PER_MONTH))
    reel_weekdays = cfg.get("reel_weekdays", REEL_WEEKDAYS)
    pattern = cfg.get("pillar_pattern", PILLAR_PATTERN)
    cta_pillar = cfg.get("cta_pillar")
    cta_value = cfg.get("cta_value", "none")
    cta_from_week = int(cfg.get("cta_from_week", 3))
    client_photos = cfg.get("media_mode") == "client_photos"
    days_in_month = _calendar.monthrange(year, month)[1]

    # Selecciona las fechas de publicación (días válidos de la semana), en orden.
    posting_dates: list[dt.date] = []
    for day in range(1, days_in_month + 1):
        d = dt.date(year, month, day)
        if d.weekday() in POSTING_WEEKDAYS:
            posting_dates.append(d)
        if len(posting_dates) >= posts_per_month:
            break

    if len(posting_dates) < posts_per_month:
        # Mes corto (p. ej. febrero): completa con los siguientes días hábiles.
        d = dt.date(year, month, days_in_month)
        while len(posting_dates) < posts_per_month:
            d += dt.timedelta(days=1)
            if d.weekday() in POSTING_WEEKDAYS:
                posting_dates.append(d)

    posting_dates = posting_dates[:posts_per_month]

    skeleton: list[dict] = []
    pillar_counters: dict[str, int] = {}
    for i, date in enumerate(posting_dates):
        pillar = pattern[i % len(pattern)]
        seq = pillar_counters.get(pillar, 0)
        pillar_counters[pillar] = seq + 1

        post_type = _post_type(date.weekday(), reel_weekdays)
        week = i // 5 + 1  # 5 posts por "semana" -> carpetas assets/semana-N/
        pos = i + 1
        post_id = f"{year:04d}-{month:02d}-P{pos:02d}"
        time_utc = TIME_MORNING_UTC if i % 2 == 0 else TIME_EVENING_UTC
        # CTA de venta: solo en el pilar de CTA del nicho y desde la semana N.
        cta = cta_value if (cta_pillar and pillar == cta_pillar and week >= cta_from_week) else "none"
        ext = _extension_for_type(post_type)
        # media_mode client_photos -> la foto la pone el cliente (no stock).
        asset = "" if client_photos else f"assets/semana-{week}/p{pos:02d}.{ext}"

        skeleton.append(
            {
                "id": post_id,
                "date": date.isoformat(),
                "time_utc": time_utc,
                "type": post_type,
                "pillar": pillar,
                "cta": cta,
                "asset_path": asset,
                "approved": False,
                "published": False,
            }
        )
    return skeleton


# ---------------------------------------------------------------------------
# 2. Prompts para la IA
# ---------------------------------------------------------------------------

VOICE_RULES = """Format & voice rules (apply to EVERY post):
- ULTRA-short: 1-2 lines, ~10-25 words. Never a paragraph.
- Lead with awe/feeling, not a lesson. If there's a fact, ONE punchy line.
- OBJECTIVE (this decides distribution): SAVES and SHARES first, comments second. Instagram ranks by saves, shares and watch time — not by likes. Every post must give a concrete REASON to save it (a fact/number/name worth keeping) or to send it to someone.
- Every post ENDS with ONE call to action, and you must ROTATE across posts between these three kinds: (a) SAVE — "save this for your next spotting session"; (b) SHARE/TAG — "send this to the avgeek who'd lose it"; (c) COMMENT — a guess or this-or-that. Aim for roughly 40% save, 30% share/tag, 30% comment across the month. Never the same CTA two posts in a row.
- Save-worthiness test: before writing, ask "would someone screenshot or save this?" If the answer is no, add a concrete, specific, keepable detail (exact model, a number, a record, a name) — vague awe is not saveable.
- Emojis welcome and natural (✈️ signature; 😍🔥👀😱 when they fit). Never a robotic row of identical emojis.
- Vary the structure across posts — do NOT reuse the same closing formula post after post.
- Ground every specific claim in the fact/news provided for that post. Invent nothing.
- hook_en: scroll-stopping first line (max ~8 words). caption_en: the full short caption. caption_es: same tone in neutral Latin-American Spanish ("tú").
- hashtags: EXACTLY 5, lowercase, each starting with '#'. Mix broad (#aviation) with niche (#avgeek #planespotting) + 1-2 specific to the post. Five targeted beats ten stuffed. topic: short specific title. visual_prompt: vivid English prompt matched to the post type.
Return your answer by calling submit_calendar exactly once, one entry per post id, nothing else."""


# ---------------------------------------------------------------------------
# Config de contenido POR NICHO (multi-cliente). Externaliza lo que antes estaba
# amarrado a aviación: pilares, briefs, voz, marca, idioma y modo de media.
# Si no existe knowledge/<niche>/content.json, cae a los defaults de Epic.Plane
# (comportamiento idéntico al anterior — no rompe nada).
# ---------------------------------------------------------------------------

def load_content_config(niche: str) -> dict:
    cfg = {
        "brand": "Epic.Plane",
        "language": "en",                 # idioma del caption que se publica
        "posts_per_month": POSTS_PER_MONTH,
        "reel_weekdays": sorted(REEL_WEEKDAYS),
        "pillar_pattern": list(PILLAR_PATTERN),
        "pillars": dict(PILLAR_BRIEFS),
        "voice_rules": VOICE_RULES,
        "media_mode": "auto",             # auto = stock/wiki (media.py) ; client_photos = las pone el cliente
        "cta_pillar": "pilot_path",
        "cta_value": "affiliate_pilot_institute",
        "cta_from_week": 3,
    }
    path = ROOT / "knowledge" / niche / "content.json"
    if path.exists():
        try:
            cfg.update(json.loads(path.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"⚠️  content.json de '{niche}' inválido; uso defaults. ({e})")
    cfg["reel_weekdays"] = set(cfg["reel_weekdays"])
    return cfg


def build_user_prompt(skeleton: list[dict], month_label: str, cfg: dict | None = None) -> str:
    cfg = cfg or load_content_config("epic-plane")
    brand = cfg.get("brand", "Epic.Plane")
    pillars = cfg.get("pillars", PILLAR_BRIEFS)
    lang_note = ""
    if cfg.get("language") == "es":
        lang_note = ("\nIMPORTANT — this brand publishes in SPANISH: `caption_es` is the REAL "
                     "published caption (write it beautifully in Chilean Spanish, tuteo). "
                     "`caption_en` = a short faithful English mirror. `hook_en` may be in Spanish.")
    lines = [
        f"Generate the creative content for {brand}'s {month_label} calendar "
        f"({len(skeleton)} posts). Here is the fixed schedule — fill in the "
        f"creative fields for each id:{lang_note}\n"
    ]
    # Radar de tendencias: lo que la COMUNIDAD de aviación está viendo esta semana
    # (trends.py). Sirve para ir a la vanguardia en vez de inventar desde cero.
    try:
        import trends as _trends
        _brief = _trends.brief_for_prompt()
    except Exception:
        _brief = ""
    if _brief:
        lines.append(
            "WHAT THE AVIATION COMMUNITY IS INTO RIGHT NOW (real posts trending in the "
            "aviation subreddits this week — this is your vanguard signal):\n"
            f"{_brief}\n"
            "PRIORITY: when one of these live signals fits a post's pillar, PREFER it over "
            "the stored fact for that post — being on the live conversation beats being "
            "encyclopedic. Aim to ride these signals in at least a third of the month. "
            "Use them for angles, subjects and tone: which aircraft, liveries and moments "
            "the community is reacting to RIGHT NOW. Never copy a title verbatim, never "
            "invent facts from a headline you cannot verify, and never touch fatal "
            "accidents or tragedy (drama = awe and adrenaline, never disaster).\n"
        )
    for p in skeleton:
        brief = pillars.get(p["pillar"], "")
        if p["cta"] and p["cta"] == cfg.get("cta_value"):
            cta_note = " [INCLUDE the sales CTA — warm, link in bio, not salesy]"
        elif cfg.get("cta_pillar") and p["pillar"] == cfg.get("cta_pillar"):
            cta_note = " [NO hard CTA: aspirational/emotional only — no sign-ups or 'link in bio']"
        else:
            cta_note = ""
        kind = p.get("source_kind", "none")
        if kind == "fact":
            ground = (f"\n    Optional flavor — ONLY if it fits in one short line, never invent beyond it: "
                      f"{p['source_text']}. But LEAD with a scroll-stopping hook and END with the comment question. "
                      f"Do NOT open with the fact or a lesson. Ultra-short.")
        elif kind == "news":
            ground = (f"\n    React in one short optional line to: {p['source_text']} — {p.get('source_detail','')}. "
                      f"Lead with the hook, end with the comment question, ultra-short.")
        else:
            ground = "\n    Pure hook + feeling + comment question. Ultra-short. Invent no facts."
        # Fórmula de engagement para REELS (2026-09): en vez de un "spotter"
        # genérico (que no gatilla likes/guardados), el reel se construye en torno a
        # UN avión específico icónico/raro + un dato que impacta, en formato
        # "adivina y revela". El visual_prompt DEBE nombrar ese avión exacto para que
        # el media que se produzca calce (el flujo genera el media según el prompt).
        if p["type"] == "reel":
            ground += ("\n    SPOT-THE-AIRCRAFT REEL (engagement formula): build it around ONE "
                       "specific, iconic or rare aircraft. hook_en = a 3-second guess prompt "
                       "('Can you name this jet? 👀'). caption_en = REVEAL the aircraft by name + "
                       "ONE jaw-dropping fact, then a comment CTA ('Did you get it? 👇'). Name the "
                       "exact model/airline in BOTH `topic` and `visual_prompt` (and describe the "
                       "shot) so the footage matches the reveal. Specificity is what drives saves "
                       "and comments — never a generic 'a jet taking off'."
                       "\n    WATCH TIME (the #1 reel ranking signal): write for a clip UNDER 15s "
                       "that loops cleanly — the reveal lands in the last beat so the viewer "
                       "rewatches to check. The hook must land in the FIRST SECOND (no intro, no "
                       "build-up). Describe that short, loopable shot in `visual_prompt`.")
        occ = p.get("occasion")
        rit = p.get("ritual")
        if occ:
            ground += (f"\n    🗓️ SEASONAL — this post is in the run-up to {occ['name']} "
                       f"({occ['date']}, in ~{occ['days_until']} days). Make it CLEARLY and "
                       f"meaningfully themed to {occ['name']}: {occ['angle']}. It must feel "
                       f"intentional and timely (not generic filler): weave the occasion into the "
                       f"hook, and when it fits, invite early orders / 'reserva anticipada'.")
        elif rit:
            ground += (f"\n    🔁 COMMUNITY RITUAL — {rit['name']}. {rit['brief']} This is a named, "
                       f"recurring weekly format followers should recognize: put the ritual name in "
                       f"the caption so it feels like an event they can return to every week.")
        lines.append(
            f"- id={p['id']} | date={p['date']} | type={p['type']} | "
            f"pillar={p['pillar']}{cta_note}\n    {brief}{ground}"
        )
    lines.append(
        "\nReturn every id via the submit_calendar tool. Keep topics unique "
        "across the month."
    )
    return "\n".join(lines)


CALENDAR_TOOL = {
    "name": "submit_calendar",
    "description": "Submit the finished creative content for every post in the month.",
    "input_schema": {
        "type": "object",
        "properties": {
            "posts": {
                "type": "array",
                "description": "One object per post id, in the same order as provided.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "The post id, exactly as given."},
                        "topic": {"type": "string"},
                        "hook_en": {"type": "string", "description": "Scroll-stopping first line, max ~8 words."},
                        "caption_en": {"type": "string", "description": "ULTRA-short (1-2 lines, ~10-25 words), hyped/awe, 1-3 emojis (✈️ signature). Must carry ONE concrete keepable detail (exact model / number / record) so it is worth SAVING, and END with one CTA rotated across posts: SAVE ('save this for...'), SHARE/TAG ('send this to the avgeek who...'), or COMMENT (a guess / this-or-that). Saves and shares drive reach - prioritise them over comments. No paragraphs, no emoji rows."},
                        "caption_es": {"type": "string", "description": "Natural neutral Latin-American Spanish."},
                        "hashtags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "EXACTLY 5 targeted hashtags, each starting with '#' (mix broad + niche).",
                        },
                        "visual_prompt": {"type": "string"},
                    },
                    "required": [
                        "id",
                        "topic",
                        "hook_en",
                        "caption_en",
                        "caption_es",
                        "hashtags",
                        "visual_prompt",
                    ],
                },
            }
        },
        "required": ["posts"],
    },
}


# ---------------------------------------------------------------------------
# 3. Llamada al modelo
# ---------------------------------------------------------------------------

def generate_creative(skeleton: list[dict], month_label: str, model: str, niche: str = "epic-plane", cfg: dict | None = None) -> dict[str, dict]:
    """Llama a la API y devuelve un dict id -> campos creativos."""
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit(
            "Falta la librería 'anthropic'. Instálala con:\n"
            "    pip install -r requirements.txt"
        )

    _load_dotenv()  # carga .env si existe (sin dependencias externas)

    try:
        client = Anthropic()
    except Exception as e:  # pragma: no cover - error de configuración
        sys.exit(f"No pude inicializar el cliente de Anthropic: {e}")

    cfg = cfg or load_content_config(niche)
    import soul
    try:
        persona = soul.load_persona(niche)
    except FileNotFoundError as e:
        sys.exit(str(e))
    system = persona + "\n\n" + cfg.get("voice_rules", VOICE_RULES)
    user = build_user_prompt(skeleton, month_label, cfg)

    print(f"→ Llamando a {model} para generar {len(skeleton)} posts…")
    try:
        # Streaming para dejar espacio de salida holgado sin timeouts HTTP.
        with client.messages.stream(
            model=model,
            max_tokens=32000,
            system=system,
            tools=[CALENDAR_TOOL],
            tool_choice={"type": "tool", "name": "submit_calendar"},
            messages=[{"role": "user", "content": user}],
        ) as stream:
            message = stream.get_final_message()
    except Exception as e:
        _explain_api_error(e)
        raise

    posts = None
    for block in message.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_calendar":
            posts = block.input.get("posts")
            break

    if not posts:
        sys.exit("La API no devolvió posts en el formato esperado. Reintenta.")

    usage = message.usage
    print(
        f"✓ Recibidos {len(posts)} posts  "
        f"(tokens in={usage.input_tokens}, out={usage.output_tokens})"
    )

    return {p["id"]: p for p in posts if "id" in p}


# ---------------------------------------------------------------------------
# 3b. Acortar captions de un mes ya generado
# ---------------------------------------------------------------------------

SHORTEN_SYSTEM = """You are editing Instagram captions for Epic.Plane, an aviation \
account with a native, casual-expert English voice. Rewrite each caption to be \
SHORT and punchy: 2-3 sentences, ~30-60 words max. Keep the single most striking \
fact or hook, cut everything else, and end with a short question that invites \
comments. Stay accurate and never invent facts. Also provide a natural, equally \
short Latin-American Spanish version (neutral "tú", no Argentine voseo). Return \
every id via the submit_shortened tool."""

SHORTEN_TOOL = {
    "name": "submit_shortened",
    "description": "Return the shortened captions for every post.",
    "input_schema": {
        "type": "object",
        "properties": {
            "posts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "caption_en": {"type": "string", "description": "2-3 sentences, ~30-60 words, ends with a short question."},
                        "caption_es": {"type": "string", "description": "Short natural neutral Latin-American Spanish."},
                    },
                    "required": ["id", "caption_en", "caption_es"],
                },
            }
        },
        "required": ["posts"],
    },
}


def shorten_captions(posts: list[dict], model: str) -> dict[str, dict]:
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("Falta 'anthropic'. Instala con: pip install -r requirements.txt")
    _load_dotenv()
    client = Anthropic()

    lines = ["Shorten every caption below. Keep the same id.\n"]
    for p in posts:
        lines.append(f"- id={p['id']}\n  CURRENT: {p.get('caption_en','')}")
    user = "\n".join(lines)

    print(f"→ Acortando {len(posts)} captions con {model}…")
    try:
        with client.messages.stream(
            model=model, max_tokens=16000, system=SHORTEN_SYSTEM,
            tools=[SHORTEN_TOOL], tool_choice={"type": "tool", "name": "submit_shortened"},
            messages=[{"role": "user", "content": user}],
        ) as stream:
            message = stream.get_final_message()
    except Exception as e:
        _explain_api_error(e)
        raise
    for block in message.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_shortened":
            return {p["id"]: p for p in block.input.get("posts", []) if "id" in p}
    sys.exit("La API no devolvió captions acortados.")


# ---------------------------------------------------------------------------
# 4. Merge, escritura JSON y export Markdown
# ---------------------------------------------------------------------------

def merge(skeleton: list[dict], creative: dict[str, dict]) -> list[dict]:
    merged: list[dict] = []
    for p in skeleton:
        c = creative.get(p["id"], {})
        merged.append(
            {
                "id": p["id"],
                "date": p["date"],
                "time_utc": p["time_utc"],
                "type": p["type"],
                "pillar": p["pillar"],
                "topic": c.get("topic", ""),
                "hook_en": c.get("hook_en", ""),
                "caption_en": c.get("caption_en", ""),
                "caption_es": c.get("caption_es", ""),
                "hashtags": c.get("hashtags", []),
                "cta": p["cta"],
                "visual_prompt": c.get("visual_prompt", ""),
                "asset_path": p["asset_path"],
                "approved": p["approved"],
                "published": p["published"],
            }
        )
    return merged


def _calendar_path(year: int, month: int, niche: str = "epic-plane") -> Path:
    # Epic.Plane mantiene el nombre plano (compatibilidad); otros clientes llevan prefijo.
    stem = f"{year:04d}-{month:02d}" if niche == "epic-plane" else f"{niche}-{year:04d}-{month:02d}"
    return CALENDAR_DIR / f"{stem}.json"


def _content_path(year: int, month: int, niche: str = "epic-plane") -> Path:
    stem = f"{year:04d}-{month:02d}" if niche == "epic-plane" else f"{niche}-{year:04d}-{month:02d}"
    return CONTENT_DIR / f"{stem}.md"


def write_json(year: int, month: int, posts: list[dict], niche: str = "epic-plane") -> Path:
    CALENDAR_DIR.mkdir(parents=True, exist_ok=True)
    path = _calendar_path(year, month, niche)
    data = {"month": f"{year:04d}-{month:02d}", "posts": posts}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def write_markdown(year: int, month: int, posts: list[dict], niche: str = "epic-plane") -> Path:
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    path = _content_path(year, month, niche)

    approved = sum(1 for p in posts if p.get("approved"))
    lines = [
        f"# Calendario Epic.Plane — {year:04d}-{month:02d}",
        "",
        f"**{len(posts)} posts** · {approved} aprobados · revisa, edita el .json y "
        f"marca `\"approved\": true` en los que apruebes.",
        "",
    ]

    current_week = None
    for i, p in enumerate(posts):
        week = i // 5 + 1
        if week != current_week:
            current_week = week
            lines.append(f"\n## Semana {week}\n")

        check = "✅" if p.get("approved") else "⬜️"
        lines.append(f"### {check} {p['id']} — {p.get('topic') or '(sin título)'}")
        lines.append(
            f"`{p['date']} · {p['time_utc']} UTC · {p['type']} · {p['pillar']} · CTA: {p['cta']}`"
        )
        lines.append("")
        lines.append(f"**Hook:** {p.get('hook_en','')}")
        lines.append("")
        lines.append(f"**Caption (EN):**\n{p.get('caption_en','')}")
        lines.append("")
        lines.append(f"**Caption (ES):**\n{p.get('caption_es','')}")
        lines.append("")
        hashtags = " ".join(p.get("hashtags", []))
        lines.append(f"**Hashtags:** {hashtags}")
        lines.append("")
        lines.append(f"**Visual prompt:** {p.get('visual_prompt','')}")
        lines.append("")
        lines.append(f"**Asset:** `{p['asset_path']}`")
        lines.append("\n---\n")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _load_dotenv() -> None:
    """Carga variables de un archivo .env sin depender de python-dotenv."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _explain_api_error(e: Exception) -> None:
    name = type(e).__name__
    if name == "AuthenticationError":
        print(
            "\n⚠️  API key inválida o ausente.\n"
            "   Exporta tu key:  export ANTHROPIC_API_KEY=sk-ant-...\n"
            "   o crea un archivo .env (copia .env.example).",
            file=sys.stderr,
        )
    elif name == "RateLimitError":
        print("\n⚠️  Rate limit. Espera unos segundos y reintenta.", file=sys.stderr)
    else:
        print(f"\n⚠️  Error de la API ({name}): {e}", file=sys.stderr)


def _match_post(post_id: str, token: str) -> bool:
    """¿El post_id (ej '2026-08-P07') corresponde al token dado por el usuario?

    Acepta: id completo, 'P07', 'p7', '7', '07'.
    """
    token = token.strip().lower()
    pid = post_id.lower()
    if token == pid:
        return True
    # Número del post dentro del id (…-p07 -> 7)
    tail = pid.rsplit("-p", 1)[-1]
    try:
        post_num = int(tail)
    except ValueError:
        return False
    tnum = token.lstrip("p")
    try:
        return int(tnum) == post_num
    except ValueError:
        return False


def _set_approval(year: int, month: int, json_path: Path, approve, unapprove) -> None:
    if not json_path.exists():
        sys.exit(f"No existe {json_path}. Genera el mes primero.")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    posts = data["posts"]

    def apply(tokens, value: bool) -> list[str]:
        if not tokens:
            return []
        changed: list[str] = []
        want_all = any(t.strip().lower() == "all" for t in tokens)
        for p in posts:
            if want_all or any(_match_post(p["id"], t) for t in tokens):
                if p.get("approved") != value:
                    p["approved"] = value
                    changed.append(p["id"])
        # Avisa si algún token no calzó con ningún post.
        if not want_all:
            for t in tokens:
                if not any(_match_post(p["id"], t) for p in posts):
                    print(f"⚠️  '{t}' no corresponde a ningún post; lo ignoro.")
        return changed

    approved = apply(approve, True)
    unapproved = apply(unapprove, False)

    data["posts"] = posts
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path = write_markdown(year, month, posts)

    if approved:
        print(f"✓ Aprobados ({len(approved)}): {', '.join(approved)}")
    if unapproved:
        print(f"✓ Desaprobados ({len(unapproved)}): {', '.join(unapproved)}")
    total_ok = sum(1 for p in posts if p.get("approved"))
    print(f"→ Total aprobados ahora: {total_ok}/{len(posts)}")
    print(f"→ Markdown actualizado: {md_path}")


def _parse_month(value: str | None) -> tuple[int, int]:
    if value is None:
        today = dt.date.today()
        return today.year, today.month
    try:
        year_s, month_s = value.split("-")
        year, month = int(year_s), int(month_s)
        if not 1 <= month <= 12:
            raise ValueError
        return year, month
    except ValueError:
        sys.exit(f"Mes inválido: '{value}'. Usa el formato YYYY-MM (ej: 2026-08).")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Epic.Plane — Generador de contenido (Módulo 1).")
    parser.add_argument("--month", help="Mes a generar en formato YYYY-MM (por defecto: mes actual).")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Modelo a usar (por defecto: {DEFAULT_MODEL}).")
    parser.add_argument("--niche", default="epic-plane", help="Nicho/cliente: persona + base + noticias (por defecto: epic-plane).")
    parser.add_argument("--force", action="store_true", help="Regenera aunque el calendario del mes ya exista.")
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="No llama a la API: solo re-exporta el .md desde el .json existente.",
    )
    parser.add_argument(
        "--approve",
        nargs="+",
        metavar="ID",
        help="Marca posts como aprobados. Acepta 'P01', '1', el id completo, o 'all'. Ej: --approve P01 3 P05",
    )
    parser.add_argument(
        "--unapprove",
        nargs="+",
        metavar="ID",
        help="Desmarca posts (los vuelve a approved:false). Mismos formatos que --approve.",
    )
    parser.add_argument(
        "--to-sheet",
        action="store_true",
        help="Escribe/actualiza el calendario del mes en la Google Sheet (upsert por id).",
    )
    parser.add_argument(
        "--shorten",
        action="store_true",
        help="Reescribe los captions del mes más cortos (deja tema/hook/hashtags/fotos intactos) y actualiza JSON + hoja.",
    )
    args = parser.parse_args()

    year, month = _parse_month(args.month)
    month_label = f"{year:04d}-{month:02d}"
    json_path = _calendar_path(year, month, args.niche)

    # Modo aprobar/desaprobar: edita el .json de forma segura y re-exporta el .md.
    if args.approve or args.unapprove:
        _set_approval(year, month, json_path, args.approve, args.unapprove)
        return

    # Modo shorten: reescribe los captions del mes más cortos.
    if args.shorten:
        if not json_path.exists():
            sys.exit(f"No existe {json_path}. Genera el mes primero.")
        data = json.loads(json_path.read_text(encoding="utf-8"))
        short = shorten_captions(data["posts"], args.model)
        changed = 0
        for p in data["posts"]:
            s = short.get(p["id"])
            if s:
                p["caption_en"] = s.get("caption_en", p["caption_en"])
                p["caption_es"] = s.get("caption_es", p["caption_es"])
                changed += 1
        json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        write_markdown(year, month, data["posts"], args.niche)
        print(f"✓ {changed} captions acortados en el JSON.")
        try:
            import sheets
            sheets.write_calendar_to_sheet(data["posts"])
            print("✓ Hoja actualizada con los captions cortos.")
        except Exception as e:
            print(f"⚠️  No pude actualizar la hoja: {e}")
        return

    # Modo to-sheet: sube el calendario existente a la Google Sheet (sin regenerar).
    if args.to_sheet:
        if not json_path.exists():
            sys.exit(f"No existe {json_path}. Genera el mes primero.")
        data = json.loads(json_path.read_text(encoding="utf-8"))
        try:
            import sheets
            n = sheets.write_calendar_to_sheet(data["posts"])
        except Exception as e:
            sys.exit(f"Error escribiendo a la Google Sheet: {e}")
        print(f"✓ {n} posts escritos/actualizados en la Google Sheet.")
        return

    # Modo export-only: reconstruye el .md desde el .json ya editado.
    if args.export_only:
        if not json_path.exists():
            sys.exit(f"No existe {json_path}. Genera el mes primero (sin --export-only).")
        data = json.loads(json_path.read_text(encoding="utf-8"))
        md_path = write_markdown(year, month, data["posts"])
        print(f"✓ Re-exportado: {md_path}")
        return

    # Protección: no sobrescribir un calendario ya generado (podrías perder
    # ediciones y aprobaciones). Requiere --force explícito.
    if json_path.exists() and not args.force:
        sys.exit(
            f"Ya existe {json_path}.\n"
            "Si querías re-exportar el Markdown desde el JSON: usa --export-only.\n"
            "Si de verdad quieres REGENERAR y perder ediciones/aprobaciones: usa --force."
        )

    cfg = load_content_config(args.niche)
    print(f"Generando calendario de {month_label} para {cfg.get('brand', args.niche)}…")
    skeleton = build_schedule(year, month, cfg)
    occasions = load_occasions(args.niche)
    skeleton = tag_occasions(skeleton, occasions)
    tagged = [s for s in skeleton if s.get("occasion")]
    if tagged:
        names = sorted({s["occasion"]["name"] for s in tagged})
        print(f"  🗓️ Ocasiones detectadas este mes: {', '.join(names)} "
              f"({len(tagged)} post(s) temáticos)")
    rituals = load_rituals(args.niche)
    skeleton = tag_rituals(skeleton, rituals)
    ritual_slots = [s for s in skeleton if s.get("ritual")]
    if ritual_slots:
        rnames = sorted({s["ritual"]["name"] for s in ritual_slots})
        print(f"  🔁 Rituales de comunidad: {', '.join(rnames)} "
              f"({len(ritual_slots)} post(s))")
    import soul
    skeleton = soul.assign_sources(
        skeleton, soul.load_facts(args.niche), soul.load_news(args.niche)
    )
    creative = generate_creative(skeleton, month_label, args.model, args.niche, cfg)
    posts = merge(skeleton, creative)

    json_path = write_json(year, month, posts, args.niche)
    md_path = write_markdown(year, month, posts, args.niche)

    print(f"\n✓ Listo.")
    print(f"  Calendario JSON : {json_path}")
    print(f"  Revisión (MD)   : {md_path}")
    print(
        "\nSiguiente paso: abre el .md para revisar, edita lo que quieras en el "
        ".json y marca \"approved\": true en los posts que apruebes."
    )


if __name__ == "__main__":
    main()
