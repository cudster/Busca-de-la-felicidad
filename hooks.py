#!/usr/bin/env python3
"""
hooks.py — Puente entre el motor de contenido y las skills `ig-*`.

Qué resuelve: el generador escribía el caption y buscaba la foto, pero NUNCA
elegía una fórmula de gancho ni registraba cuál usó. Sin eso no se puede
aprender: `ig-audit` sólo puede decirte qué funciona si sabe qué probaste.

Tres cosas:
  1. `brief_para_prompt()` — las 26 fórmulas de `ig-reel/hooks.json` en formato
     compacto, para que el modelo elija una por post en vez de improvisar.
  2. `puntuar(texto)` — `hookscore.py` de la skill. Cinco heurísticas locales.
     OJO con su alcance real, declarado por la propia skill: distingue bien un
     gancho de verdad de uno malo (AUC 0,83), pero NO predice cuál de dos
     ganchos decentes va a viajar (0,56, casi moneda al aire). Sirve para
     atajar saludos, preámbulos y ganchos sin nada concreto. Nada más.
  3. `registrar(posts)` — escribe en `~/.claude/instagram/log.md`, que es
     justo donde `ig-audit` va a buscar qué fórmula usó cada post.

Uso:
    python3 hooks.py --list                       # ver las fórmulas
    python3 hooks.py --score "Tu gancho acá"      # puntuar una línea
    python3 hooks.py --check-month 2026-11        # puntuar todo un mes
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILL = Path.home() / ".claude" / "skills" / "ig-reel"
LOG = Path.home() / ".claude" / "instagram" / "log.md"
UMBRAL_DEBIL = 55          # bajo esto, el gancho se revisa a mano


def _hooks() -> list[dict]:
    f = SKILL / "hooks.json"
    if not f.exists():
        return []
    return json.loads(f.read_text(encoding="utf-8")).get("hooks", [])


def reglas() -> list[str]:
    f = SKILL / "hooks.json"
    if not f.exists():
        return []
    return json.loads(f.read_text(encoding="utf-8")).get("rules", [])


def brief_para_prompt(max_formulas: int = 26) -> str:
    """Las fórmulas en formato compacto para inyectar en el prompt. '' si no hay skill."""
    hs = _hooks()
    if not hs:
        return ""
    lineas = [f"{h['id']}. {h['name']} — {h.get('template','')}" for h in hs[:max_formulas]]
    rs = [f"- {r}" for r in reglas()]
    return ("HOOK FORMULAS (pick ONE per post and put its id in `hook_id`):\n"
            + "\n".join(lineas)
            + ("\n\nHOOK RULES:\n" + "\n".join(rs) if rs else ""))


def puntuar(texto: str) -> dict | None:
    """{'score': int, 'verdict': str, 'flags': [...]} o None si la skill no está."""
    if not (SKILL / "hookscore.py").exists():
        return None
    sys.path.insert(0, str(SKILL))
    try:
        import hookscore                                   # type: ignore
        res = hookscore.run(texto)
    except Exception as e:
        print(f"   (no pude puntuar el gancho: {type(e).__name__})")
        return None
    finally:
        if str(SKILL) in sys.path:
            sys.path.remove(str(SKILL))
    # run() devuelve una tupla; se normaliza sin asumir el orden exacto.
    if isinstance(res, dict):
        return res
    vals = list(res) if isinstance(res, (tuple, list)) else [res]
    out: dict = {}
    for v in vals:
        if isinstance(v, (int, float)) and "score" not in out:
            out["score"] = int(v)
        elif isinstance(v, str) and "verdict" not in out:
            out["verdict"] = v
        elif isinstance(v, (list, tuple)) and "flags" not in out:
            out["flags"] = list(v)
    return out or None


def registrar(posts: list[dict], niche: str = "epic-plane") -> int:
    """Deja constancia de qué fórmula usó cada post, donde `ig-audit` la busca."""
    if not posts:
        return 0
    LOG.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not LOG.exists()
    with LOG.open("a", encoding="utf-8") as f:
        if nuevo:
            f.write("# Registro de posts publicados\n\n"
                    "Qué fórmula de gancho usó cada post, para que `ig-audit` pueda\n"
                    "cruzarlo después con las métricas reales.\n\n"
                    "| fecha | cuenta | post | hook_id | score | gancho |\n"
                    "|---|---|---|---|---|---|\n")
        for p in posts:
            g = (p.get("hook_en") or "").replace("|", "/")[:70]
            s = puntuar(g) if g else None
            f.write(f"| {p.get('date','')} | {niche} | {p.get('id','')} | "
                    f"{p.get('hook_id','-')} | {s.get('score','-') if s else '-'} | {g} |\n")
    return len(posts)


def main() -> None:
    ap = argparse.ArgumentParser(description="Fórmulas de gancho y puntuación (skills ig-*).")
    ap.add_argument("--list", action="store_true", help="Muestra las fórmulas.")
    ap.add_argument("--score", help="Puntúa una línea.")
    ap.add_argument("--check-month", help="Puntúa los ganchos de un mes (YYYY-MM).")
    a = ap.parse_args()

    if a.list:
        for h in _hooks():
            print(f"{h['id']:3}. {h['name']:24} {h.get('template','')[:70]}")
        return
    if a.score:
        print(json.dumps(puntuar(a.score), ensure_ascii=False, indent=2))
        return
    if a.check_month:
        f = ROOT / "calendar" / f"{a.check_month}.json"
        if not f.exists():
            sys.exit(f"No existe {f}")
        posts = json.loads(f.read_text(encoding="utf-8"))["posts"]
        debiles = 0
        for p in posts:
            g = p.get("hook_en", "")
            s = puntuar(g) or {}
            sc = s.get("score")
            flojo = isinstance(sc, int) and sc < UMBRAL_DEBIL
            debiles += flojo
            print(f"  {p['id'][-3:]} {str(sc):>4} {'⚠ débil' if flojo else '      '}  {g[:62]}")
        print(f"\n{debiles} de {len(posts)} ganchos bajo {UMBRAL_DEBIL}.")
        return
    ap.print_help()


if __name__ == "__main__":
    main()
