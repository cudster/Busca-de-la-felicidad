#!/usr/bin/env python3
"""Motor YouTube (Fase 2a): genera planes de video (Shorts + long-form) para un canal
faceless. Python arma el esqueleto determinístico del mes; la API rellena lo creativo
(guión, SEO, miniatura, plan de tomas). Escribe un JSON + un Markdown legible.

Uso:
    python3 youtube_generate.py --channel autos-pov --month 2026-10
    python3 youtube_generate.py --channel autos-pov            # mes actual
    python3 youtube_generate.py --channel autos-pov --force    # regenera aunque exista
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT_DIR = ROOT / "content"
DEFAULT_MODEL = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# 1. Carga de canal y persona
# ---------------------------------------------------------------------------
def load_channel(channel: str, base: Path = ROOT) -> dict:
    p = base / "youtube" / channel / "config.json"
    if not p.exists():
        raise FileNotFoundError(
            f"No existe el canal '{channel}': {p}. Crea youtube/{channel}/config.json."
        )
    return json.loads(p.read_text(encoding="utf-8"))


def load_persona(channel: str, base: Path = ROOT) -> str:
    p = base / "youtube" / channel / "persona.md"
    if not p.exists():
        raise FileNotFoundError(f"No existe la persona de '{channel}': {p}.")
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 2. Esqueleto determinístico del mes
# ---------------------------------------------------------------------------
def build_month(cfg: dict, year: int, month: int) -> list[dict]:
    mix = cfg.get("mix", {"short": 8, "long": 4})
    n_short, n_long = int(mix.get("short", 0)), int(mix.get("long", 0))
    items: list[dict] = []
    for i in range(n_short):
        items.append({"format": "short", "id": f"{year:04d}-{month:02d}-S{i+1:02d}"})
    for i in range(n_long):
        items.append({"format": "long", "id": f"{year:04d}-{month:02d}-L{i+1:02d}"})
    days = calendar.monthrange(year, month)[1]
    weekdays = [d for d in range(1, days + 1) if dt.date(year, month, d).weekday() < 5]
    for idx, it in enumerate(items):
        d = weekdays[idx % len(weekdays)] if weekdays else 1
        it["date"] = f"{year:04d}-{month:02d}-{d:02d}"
    return items


# ---------------------------------------------------------------------------
# 3. Prompt + tool
# ---------------------------------------------------------------------------
def build_prompt(cfg: dict, persona: str, skeleton: list[dict]) -> str:
    lines = [
        persona,
        "\n---\n",
        f"Genera los planes de video para el canal '{cfg.get('name','')}' "
        f"(nicho: {cfg.get('niche','')}, idioma: {cfg.get('language','es')}).",
        f"CTAs de suscripción a usar (varía entre ellas): {cfg.get('cta_lines', [])}.",
        f"Estilo del canal: {cfg.get('reference_style','')}.",
        "\nReglas por formato:",
        "- short: guión ~150-200 palabras, gancho brutal en los primeros 3 segundos, "
        "1-2 datos que impactan, cierre con 1 CTA de suscripción.",
        "- long: guión ~1200-1800 palabras, estructura gancho → segmentos "
        "(diseño, motor, interior, la experiencia al manejarlo, exclusividad) → cierre "
        "emocional + CTA. Además entrega 2-4 shortable_moments (frases/momentos que se "
        "pueden cortar como Shorts).",
        "\nPara cada video entrega: título clickeable, descripción con keywords "
        "(y timestamps si es long), tags, hashtags, concepto de miniatura (faceless: el "
        "auto + texto bold) y shot_list (qué tomas/clips se necesitan).",
        "No inventes cifras exactas dudosas; usa rangos o la sensación.",
        "\nAquí está el esqueleto — rellena cada id:",
    ]
    for p in skeleton:
        lines.append(f"- id={p['id']} | format={p['format']} | date={p['date']}")
    lines.append("\nDevuelve TODO vía la tool submit_videos, un objeto por id, nada más.")
    return "\n".join(lines)


VIDEO_TOOL = {
    "name": "submit_videos",
    "description": "Entrega el plan creativo de cada video del mes.",
    "input_schema": {
        "type": "object",
        "properties": {
            "videos": {
                "type": "array",
                "description": "Un objeto por id del esqueleto, en el mismo orden.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "format": {"type": "string", "description": "short | long"},
                        "topic": {"type": "string", "description": "Auto/tema del video."},
                        "hook_es": {"type": "string", "description": "Primera línea, gancho de 3 segundos."},
                        "script_es": {"type": "string", "description": "El guión narrado completo en español."},
                        "title": {"type": "string", "description": "Título clickeable de YouTube."},
                        "description": {"type": "string", "description": "Descripción con keywords (timestamps si es long)."},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "hashtags": {"type": "array", "items": {"type": "string"}},
                        "thumbnail_concept": {"type": "string", "description": "Concepto/prompt visual de la miniatura."},
                        "shot_list": {"type": "array", "items": {"type": "string"}, "description": "Tomas/clips necesarios."},
                        "shortable_moments": {"type": "array", "items": {"type": "string"}, "description": "Solo long: 2-4 momentos cortables como Shorts."},
                    },
                    "required": ["id", "format", "topic", "hook_es", "script_es",
                                 "title", "description", "tags", "hashtags",
                                 "thumbnail_concept", "shot_list"],
                },
            }
        },
        "required": ["videos"],
    },
}


# ---------------------------------------------------------------------------
# 4. Llamada al modelo
# ---------------------------------------------------------------------------
def _load_dotenv() -> None:
    p = ROOT / ".env"
    if not p.exists():
        return
    import os
    for l in p.read_text(encoding="utf-8").splitlines():
        if "=" in l and not l.strip().startswith("#"):
            k, _, v = l.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def generate(skeleton: list[dict], cfg: dict, persona: str, model: str) -> dict[str, dict]:
    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("Falta 'anthropic'. Instala con: pip install -r requirements.txt")
    _load_dotenv()
    client = Anthropic()
    user = build_prompt(cfg, persona, skeleton)
    print(f"→ Generando {len(skeleton)} planes de video con {model}…")
    try:
        with client.messages.stream(
            model=model, max_tokens=32000,
            tools=[VIDEO_TOOL], tool_choice={"type": "tool", "name": "submit_videos"},
            messages=[{"role": "user", "content": user}],
        ) as stream:
            message = stream.get_final_message()
    except Exception as e:
        sys.exit(f"Error de la API: {e}")
    for block in message.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_videos":
            return {v["id"]: v for v in block.input.get("videos", []) if "id" in v}
    sys.exit("La API no devolvió videos.")


# ---------------------------------------------------------------------------
# 5. Merge + escritura
# ---------------------------------------------------------------------------
def merge(skeleton: list[dict], creative: dict[str, dict]) -> list[dict]:
    out = []
    for p in skeleton:
        c = creative.get(p["id"], {})
        out.append({
            "id": p["id"], "format": p["format"], "date": p["date"],
            "topic": c.get("topic", ""), "hook_es": c.get("hook_es", ""),
            "script_es": c.get("script_es", ""), "title": c.get("title", ""),
            "description": c.get("description", ""), "tags": c.get("tags", []),
            "hashtags": c.get("hashtags", []), "thumbnail_concept": c.get("thumbnail_concept", ""),
            "shot_list": c.get("shot_list", []),
            "shortable_moments": c.get("shortable_moments", []),
        })
    return out


def write_json(channel: str, year: int, month: int, videos: list[dict]) -> Path:
    d = ROOT / "youtube" / channel
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"plan-{year:04d}-{month:02d}.json"
    path.write_text(json.dumps(videos, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_markdown(channel: str, year: int, month: int, videos: list[dict]) -> Path:
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    path = CONTENT_DIR / f"youtube-{channel}-{year:04d}-{month:02d}.md"
    lines = [f"# YouTube — {channel} — {year:04d}-{month:02d}\n"]
    for v in videos:
        lines.append(f"## {v['id']} · {v['format'].upper()} · {v['date']}")
        lines.append(f"**Título:** {v['title']}")
        lines.append(f"**Gancho:** {v['hook_es']}\n")
        lines.append(f"**Guión:**\n{v['script_es']}\n")
        lines.append(f"**Descripción:** {v['description']}")
        lines.append(f"**Tags:** {', '.join(v['tags'])}")
        lines.append(f"**Hashtags:** {' '.join(v['hashtags'])}")
        lines.append(f"**Miniatura:** {v['thumbnail_concept']}")
        lines.append(f"**Plan de tomas:** {'; '.join(v['shot_list'])}")
        if v.get("shortable_moments"):
            lines.append(f"**Momentos Short-ables:** {'; '.join(v['shortable_moments'])}")
        lines.append("\n---\n")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _parse_month(value: str | None) -> tuple[int, int]:
    if not value:
        t = dt.date.today()
        return t.year, t.month
    y, m = value.split("-")
    return int(y), int(m)


def main() -> None:
    ap = argparse.ArgumentParser(description="Motor YouTube (Fase 2a) — genera planes de video.")
    ap.add_argument("--channel", required=True, help="Canal (ej. autos-pov).")
    ap.add_argument("--month", help="Mes YYYY-MM (por defecto: mes actual).")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--force", action="store_true", help="Regenera aunque el plan ya exista.")
    args = ap.parse_args()

    try:
        cfg = load_channel(args.channel)
        persona = load_persona(args.channel)
    except FileNotFoundError as e:
        sys.exit(str(e))
    year, month = _parse_month(args.month)

    out_json = ROOT / "youtube" / args.channel / f"plan-{year:04d}-{month:02d}.json"
    if out_json.exists() and not args.force:
        sys.exit(f"Ya existe {out_json}. Usa --force para regenerar.")

    skeleton = build_month(cfg, year, month)
    creative = generate(skeleton, cfg, persona, args.model)
    videos = merge(skeleton, creative)
    jp = write_json(args.channel, year, month, videos)
    mp = write_markdown(args.channel, year, month, videos)
    n_s = sum(1 for v in videos if v["format"] == "short")
    n_l = sum(1 for v in videos if v["format"] == "long")
    print(f"✓ Listo. {len(videos)} videos ({n_s} Shorts, {n_l} long-form).")
    print(f"  Plan JSON : {jp}")
    print(f"  Revisión  : {mp}")


if __name__ == "__main__":
    main()
