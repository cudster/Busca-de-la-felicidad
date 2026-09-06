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
    "spotting",       # 1
    "spotting",       # 2
    "technical_awe",  # 3
    "spotting",       # 4
    "spotting",       # 5
    "aviation_story", # 6
    "spotting",       # 7
    "spotting",       # 8
    "technical_awe",  # 9
    "spotting",       # 10
    "spotting",       # 11
    "pilot_path",     # 12
    "spotting",       # 13
    "spotting",       # 14
    "technical_awe",  # 15
    "aviation_story", # 16
    "spotting",       # 17
    "spotting",       # 18
    "technical_awe",  # 19
    "pilot_path",     # 20
]  # spotting=12, technical_awe=4, aviation_story=2, pilot_path=2 (post-métricas: visual épico corto)

# Descripción de cada pilar para el prompt del modelo.
PILLAR_BRIEFS = {
    "technical_awe": (
        "Technical awe: mind-blowing aircraft facts, physics of flight, "
        "engineering marvels. Should teach something surprising."
    ),
    "spotting": (
        "Spotting / epic visual: striking aircraft photography or video moments. "
        "Caption is short, punchy, evocative — the image does the heavy lifting."
    ),
    "aviation_story": (
        "Aviation story: famous incidents resolved, airline history, records, "
        "legendary flights. Narrative arc that keeps people reading."
    ),
    "pilot_path": (
        "Pilot path: how to become a pilot, training costs, licenses, career. "
        "This post ALWAYS ends with a natural call-to-action pointing followers "
        "to Pilot Institute via the link in bio."
    ),
}

# Cadencia semanal fija (decisión del dueño 2026-09-01): 3 reels + 2 posts por
# semana. El tipo depende SOLO del día de la semana en que cae la publicación:
#   Lun (0), Mié (2), Sáb (5) -> REEL   (3/semana; llegan a no-seguidores vía Reels/Explore)
#   Mar (1), Jue (3)          -> POST   (2/semana; imagen)
# Así cada semana completa queda exactamente 3 reels + 2 imágenes, y el feed
# mantiene un ritmo predecible.
REEL_WEEKDAYS = {0, 2, 5}   # lunes, miércoles, sábado


def _post_type(weekday: int) -> str:
    return "reel" if weekday in REEL_WEEKDAYS else "image"


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
            out[int(r["weekday"])] = {"name": r["name"], "brief": r.get("brief", "")}
        except Exception:
            continue
    return out


def tag_rituals(skeleton: list[dict], rituals: dict[int, dict]) -> list[dict]:
    """Etiqueta los posts tipo 'reel' cuyo día de la semana tenga un ritual.
    Las ocasiones tienen prioridad: si el post ya es temático, no se le pone ritual."""
    if not rituals:
        return skeleton
    for slot in skeleton:
        if slot.get("occasion"):
            continue  # la ocasión manda
        if slot.get("type") != "reel":
            continue  # los rituales viven en los días-reel
        d = dt.date.fromisoformat(slot["date"])
        r = rituals.get(d.weekday())
        if r:
            slot["ritual"] = {"name": r["name"], "brief": r["brief"]}
    return skeleton


# ---------------------------------------------------------------------------
# 1. Esqueleto del calendario (determinístico, sin IA)
# ---------------------------------------------------------------------------

def build_schedule(year: int, month: int) -> list[dict]:
    """Arma las 20 ranuras del mes: fecha, hora, pilar, tipo, rutas de assets."""
    days_in_month = _calendar.monthrange(year, month)[1]

    # Selecciona las fechas de publicación (días válidos de la semana), en orden.
    posting_dates: list[dt.date] = []
    for day in range(1, days_in_month + 1):
        d = dt.date(year, month, day)
        if d.weekday() in POSTING_WEEKDAYS:
            posting_dates.append(d)
        if len(posting_dates) >= POSTS_PER_MONTH:
            break

    if len(posting_dates) < POSTS_PER_MONTH:
        # Mes corto (p. ej. febrero): completa con los siguientes días hábiles.
        d = dt.date(year, month, days_in_month)
        while len(posting_dates) < POSTS_PER_MONTH:
            d += dt.timedelta(days=1)
            if d.weekday() in POSTING_WEEKDAYS:
                posting_dates.append(d)

    posting_dates = posting_dates[:POSTS_PER_MONTH]

    skeleton: list[dict] = []
    pillar_counters: dict[str, int] = {}
    for i, date in enumerate(posting_dates):
        pillar = PILLAR_PATTERN[i]
        seq = pillar_counters.get(pillar, 0)
        pillar_counters[pillar] = seq + 1

        post_type = _post_type(date.weekday())
        week = i // 5 + 1  # 5 posts por "semana" -> carpetas assets/semana-N/
        pos = i + 1
        post_id = f"{year:04d}-{month:02d}-P{pos:02d}"
        time_utc = TIME_MORNING_UTC if i % 2 == 0 else TIME_EVENING_UTC
        # Regla de fase (reactivación): semanas 1-2 SIN CTA de venta (cta=none para
        # todos). Desde la semana 3, CTA solo en el pilar "camino del piloto".
        cta = "affiliate_pilot_institute" if (pillar == "pilot_path" and week >= 3) else "none"
        ext = _extension_for_type(post_type)

        skeleton.append(
            {
                "id": post_id,
                "date": date.isoformat(),
                "time_utc": time_utc,
                "type": post_type,
                "pillar": pillar,
                "cta": cta,
                "asset_path": f"assets/semana-{week}/p{pos:02d}.{ext}",
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
- Every post ENDS with an interactive hook that begs a comment (a guess, a this-or-that, or a direct "who else?"). Comments are the #1 goal.
- Emojis welcome and natural (✈️ signature; 😍🔥👀😱 when they fit). Never a robotic row of identical emojis.
- Vary the structure across posts — do NOT reuse the same closing formula post after post.
- Ground every specific claim in the fact/news provided for that post. Invent nothing.
- hook_en: scroll-stopping first line (max ~8 words). caption_en: the full short caption. caption_es: same tone in neutral Latin-American Spanish ("tú").
- hashtags: 6-10, lowercase, each starting with '#'. topic: short specific title. visual_prompt: vivid English prompt matched to the post type.
Return your answer by calling submit_calendar exactly once, one entry per post id, nothing else."""


def build_user_prompt(skeleton: list[dict], month_label: str) -> str:
    lines = [
        f"Generate the creative content for Epic.Plane's {month_label} calendar "
        f"({len(skeleton)} posts). Here is the fixed schedule — fill in the "
        f"creative fields for each id:\n"
    ]
    for p in skeleton:
        brief = PILLAR_BRIEFS[p["pillar"]]
        if p["cta"] == "affiliate_pilot_institute":
            cta_note = " [INCLUDE the Pilot Institute CTA — warm, link in bio, not salesy]"
        elif p["pillar"] == "pilot_path":
            cta_note = (" [NO CTA: aspirational/emotional only — do NOT mention Pilot "
                        "Institute, courses, sign-ups, or 'link in bio']")
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
        # Regla de media (evita el problema histórico "la foto no corresponde"):
        # los REELS usan video de stock genérico, que NUNCA calza con un avión
        # concreto (SR-71, Concorde, etc.). Por eso un reel debe ser un "spotter"
        # universal: prohibido nombrar un modelo/aerolínea específicos en topic o
        # visual_prompt. Las FOTOS sí pueden ser de un avión específico (foto curada).
        if p["type"] == "reel":
            ground += ("\n    GENERIC SPOTTER REEL: do NOT name any specific aircraft model "
                       "or airline in `topic` or `visual_prompt` — a stock clip can't match a "
                       "specific jet. Use universal imagery (a jet taking off / landing / banking, "
                       "dramatic sky). The hook + comment question carry the post.")
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
                        "caption_en": {"type": "string", "description": "ULTRA-short (1-2 lines, ~10-25 words), hyped/awe, 1-3 emojis (✈️ signature). MUST end with an interactive hook that begs a comment (guess / this-or-that / 'who else?'). No paragraphs, no emoji rows."},
                        "caption_es": {"type": "string", "description": "Natural neutral Latin-American Spanish."},
                        "hashtags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "6-10 hashtags, each starting with '#'.",
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

def generate_creative(skeleton: list[dict], month_label: str, model: str, niche: str = "epic-plane") -> dict[str, dict]:
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

    import soul
    try:
        persona = soul.load_persona(niche)
    except FileNotFoundError as e:
        sys.exit(str(e))
    system = persona + "\n\n" + VOICE_RULES
    user = build_user_prompt(skeleton, month_label)

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


def write_json(year: int, month: int, posts: list[dict]) -> Path:
    CALENDAR_DIR.mkdir(parents=True, exist_ok=True)
    path = CALENDAR_DIR / f"{year:04d}-{month:02d}.json"
    data = {"month": f"{year:04d}-{month:02d}", "posts": posts}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def write_markdown(year: int, month: int, posts: list[dict]) -> Path:
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    path = CONTENT_DIR / f"{year:04d}-{month:02d}.md"

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
    json_path = CALENDAR_DIR / f"{month_label}.json"

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
        write_markdown(year, month, data["posts"])
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

    print(f"Generando calendario de {month_label} para Epic.Plane…")
    skeleton = build_schedule(year, month)
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
    creative = generate_creative(skeleton, month_label, args.model, args.niche)
    posts = merge(skeleton, creative)

    json_path = write_json(year, month, posts)
    md_path = write_markdown(year, month, posts)

    print(f"\n✓ Listo.")
    print(f"  Calendario JSON : {json_path}")
    print(f"  Revisión (MD)   : {md_path}")
    print(
        "\nSiguiente paso: abre el .md para revisar, edita lo que quieras en el "
        ".json y marca \"approved\": true en los posts que apruebes."
    )


if __name__ == "__main__":
    main()
