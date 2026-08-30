"""CEO Dashboard (Fase 1): junta métricas de IG + estado de contenido por cliente,
calcula salud y decisiones, y genera dashboard.html estático."""

from __future__ import annotations

import datetime as dt
import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GRAPH = "https://graph.facebook.com/v21.0/"


def load_clients(base: Path = ROOT) -> list[dict]:
    cdir = base / "clients"
    if not cdir.exists():
        return []
    out = []
    for p in sorted(cdir.glob("*/config.json")):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out
