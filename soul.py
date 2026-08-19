"""Motor Fan Experto: carga la persona, los hechos y las noticias del nicho,
y asigna a cada post una fuente real (hecho o noticia) para anclar el contenido."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_persona(niche: str, base: Path = ROOT) -> str:
    path = base / "persona" / f"{niche}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"No existe el Persona Spec para el nicho '{niche}': {path}. "
            f"Crea persona/{niche}.md."
        )
    return path.read_text(encoding="utf-8")


def load_facts(niche: str, base: Path = ROOT) -> list[dict]:
    path = base / "knowledge" / niche / "facts.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_news(niche: str, base: Path = ROOT) -> list[dict]:
    path = base / "data" / "news" / f"{niche}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def assign_sources(skeleton, facts, news, reaction_every=3):
    used = set()
    news_i = 0
    for i, post in enumerate(skeleton, start=1):
        is_reaction = (i % reaction_every == 0) and news
        if is_reaction:
            item = news[news_i % len(news)]
            news_i += 1
            post["source_kind"] = "news"
            post["source_text"] = item.get("title", "")
            post["source_detail"] = item.get("summary", "")
            continue
        pick = None
        for f in facts:
            if f["id"] in used:
                continue
            if f.get("pillar") == post.get("pillar"):
                pick = f
                break
        if pick is None:
            for f in facts:
                if f["id"] not in used:
                    pick = f
                    break
        if pick is None:
            post["source_kind"] = "none"
            post["source_text"] = ""
            post["source_detail"] = ""
        else:
            used.add(pick["id"])
            post["source_kind"] = "fact"
            post["source_text"] = pick["fact"]
            post["source_detail"] = pick.get("detail", "")
    return skeleton
