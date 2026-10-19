#!/usr/bin/env python3
"""
evergreen.py — Plan B: que la cuenta nunca quede muda.

Si un día no hay nada aprobado y vencido en la Google Sheet, el publicador saca
un post atemporal de `data/evergreen/<nicho>.json` en vez de no publicar nada.

Por qué existe: en octubre la cuenta estuvo días sin publicar porque las URLs del
CDN donde vivían los reels expiraron (HTTP 403) y el publicador saltaba las filas.
Un hueco de contenido no debería depender de que un asset externo siga vivo.

Decisión de diseño clave: **la foto se busca en Wikimedia Commons al momento de
publicar**, no se guarda una URL. Commons es gratis y estable, así no hay nada que
pueda expirar. Son sólo fotos y sólo de aviones comunes: esto es respaldo, no
lucimiento, y los aviones raros son justo donde la búsqueda y la IA fallan.

Uso:
    python3 evergreen.py --niche epic-plane            # muestra cuál tocaría
    python3 evergreen.py --niche epic-plane --publish  # publica de verdad
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIR = ROOT / "data" / "evergreen"
# No repetir un respaldo antes de este plazo, para que no se note el truco.
DIAS_MINIMOS_ENTRE_REPETICIONES = 45


def _pool(niche: str) -> list[dict]:
    p = DIR / f"{niche}.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("posts", [])


def _usos(niche: str) -> dict:
    p = DIR / f"used-{niche}.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _marcar(niche: str, pid: str) -> None:
    usos = _usos(niche)
    usos[pid] = dt.date.today().isoformat()
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / f"used-{niche}.json").write_text(
        json.dumps(usos, ensure_ascii=False, indent=2), encoding="utf-8")


def elegir(niche: str) -> dict | None:
    """El respaldo menos usado recientemente. None si no hay pool."""
    pool = _pool(niche)
    if not pool:
        return None
    usos = _usos(niche)
    hoy = dt.date.today()

    def antiguedad(post: dict) -> int:
        """Días desde el último uso. 9999 si nunca se usó (tiene prioridad)."""
        fecha = usos.get(post["id"])
        if not fecha:
            return 9999
        try:
            return (hoy - dt.date.fromisoformat(fecha)).days
        except Exception:
            return 9999

    candidatos = [p for p in pool if antiguedad(p) >= DIAS_MINIMOS_ENTRE_REPETICIONES]
    if not candidatos:
        # Todos usados hace poco: igual sale el más antiguo. Repetir un post
        # atemporal es mejor que un día en blanco.
        candidatos = pool
    return max(candidatos, key=antiguedad)


def preparar(niche: str) -> dict | None:
    """Devuelve el respaldo con una URL de foto FRESCA de Commons, o None."""
    post = elegir(niche)
    if not post:
        return None
    import media
    foto = media.commons_photo(post["wiki"], width=1920)
    if not foto:
        print(f"   ⚠️  respaldo {post['id']}: Commons no devolvió foto para {post['wiki']!r}.")
        return None
    return {**post, "asset_path": media.crop_45(foto["url"])}


def publicar(niche: str, ig_id: str, token: str, dry_run: bool = True) -> bool:
    """Publica un respaldo. Devuelve True si salió de verdad."""
    post = preparar(niche)
    if not post:
        return False
    caption = f"{post['caption_en']}\n\n{post['hashtags']}"
    print(f"   📦 RESPALDO {post['id']} · {post['topic']}")
    print(f"      {post['asset_path'][:95]}")
    if dry_run:
        print("      (DRY RUN — no se publicó)")
        return False
    import publish
    try:
        media_id = publish.publish_post(ig_id, token, "image", caption,
                                        media_url=post["asset_path"])
    except RuntimeError as e:
        print(f"      ⚠️  no se pudo publicar el respaldo: {e}")
        return False
    _marcar(niche, post["id"])
    print(f"      ✓ Publicado. Media ID: {media_id}")
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="Plan B: respaldo cuando no hay aprobados.")
    ap.add_argument("--niche", default="epic-plane")
    ap.add_argument("--publish", action="store_true", help="Publica de verdad.")
    a = ap.parse_args()

    import publish
    env = publish.load_env(["IG_USER_ID", "META_PAGE_TOKEN"])
    publicar(a.niche, env["IG_USER_ID"], env["META_PAGE_TOKEN"], dry_run=not a.publish)


if __name__ == "__main__":
    main()
