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
