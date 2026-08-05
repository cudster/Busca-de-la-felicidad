#!/usr/bin/env python3
"""
Epic.Plane — Módulo 2: Publicador automático (Instagram Graph API).

Publica en Instagram usando el flujo oficial de la Graph API:
  1. Crea un "contenedor" de media a partir de una URL pública (imagen/video).
  2. Lo publica (media_publish) en el feed.

⚠️  La Graph API NO sube archivos locales: la imagen/video debe estar en una
    URL pública (http/https). El pipeline que sube los assets a una URL pública
    se construye en la Sesión 3 (Módulo 3).

Modos:
    # Validación segura (crea el contenedor, NO publica — no aparece nada en el feed):
    python3 publish.py --check

    # Post de prueba REAL (sí publica en la cuenta; visible para tus seguidores):
    python3 publish.py --post-test

    # Publicar del calendario los posts aprobados, no publicados y cuya hora ya pasó:
    python3 publish.py --run --month 2026-08
    python3 publish.py --run --month 2026-08 --dry-run   # muestra qué haría, sin publicar

Requisitos en .env (los deja setup_meta.py):
    IG_USER_ID=...
    META_PAGE_TOKEN=...

No usa librerías externas (solo la stdlib de Python).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
CALENDAR_DIR = ROOT / "calendar"
CONTENT_DIR = ROOT / "content"
GRAPH_VERSION = "v21.0"
BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"

# Imagen pública de prueba (JPEG directo, formato vertical apto para feed).
TEST_IMAGE_URL = "https://picsum.photos/id/1015/1080/1350.jpg"
TEST_CAPTION = "Epic.Plane test ✈️ (post de prueba del sistema — se puede borrar)"


# ---------------------------------------------------------------------------
# .env y llamadas a la Graph API
# ---------------------------------------------------------------------------

def load_env() -> dict[str, str]:
    """Carga config desde .env y desde variables de entorno.

    Las variables de entorno tienen prioridad — así funciona tanto en local
    (con .env) como en GitHub Actions (con Secrets inyectados como env vars).
    """
    import os
    env: dict[str, str] = {}
    if ENV_PATH.exists():
        for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    for key in ("IG_USER_ID", "META_PAGE_TOKEN"):
        if os.environ.get(key):
            env[key] = os.environ[key]
    return env


def _request(method: str, path: str, params: dict[str, str]) -> dict:
    url = f"{BASE}/{path}"
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        url = url + "?" + data.decode()
        req = urllib.request.Request(url, method="GET")
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            err = json.loads(body).get("error", {})
            msg = err.get("message", body)
        except Exception:
            msg = body
        raise RuntimeError(f"Graph API /{path}: {msg}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"Sin conexión con la Graph API: {e}") from None


# ---------------------------------------------------------------------------
# Flujos de publicación
# ---------------------------------------------------------------------------

def create_image_container(ig_id, token, image_url, caption, is_child=False) -> str:
    params = {"image_url": image_url, "access_token": token}
    if is_child:
        params["is_carousel_item"] = "true"
    else:
        params["caption"] = caption
    return _request("POST", f"{ig_id}/media", params)["id"]


def create_reel_container(ig_id, token, video_url, caption) -> str:
    return _request("POST", f"{ig_id}/media", {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": token,
    })["id"]


def create_carousel_container(ig_id, token, child_ids, caption) -> str:
    return _request("POST", f"{ig_id}/media", {
        "media_type": "CAROUSEL",
        "children": ",".join(child_ids),
        "caption": caption,
        "access_token": token,
    })["id"]


def wait_until_ready(container_id, token, timeout_s=180) -> None:
    """Los videos/reels se procesan de forma asíncrona; espera a FINISHED."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status = _request("GET", container_id, {
            "fields": "status_code", "access_token": token,
        }).get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError("El procesamiento del video falló (status ERROR).")
        print(f"   … procesando media ({status})")
        time.sleep(5)
    raise RuntimeError("Timeout esperando el procesamiento del media.")


def publish_container(ig_id, token, creation_id) -> str:
    return _request("POST", f"{ig_id}/media_publish", {
        "creation_id": creation_id, "access_token": token,
    })["id"]


def publish_post(ig_id, token, post_type, caption, media_url=None, media_urls=None) -> str:
    """Publica un post según su tipo. Devuelve el ID del media publicado."""
    if post_type == "carousel":
        urls = media_urls or ([media_url] if media_url else [])
        if len(urls) < 2:
            raise RuntimeError("Un carrusel necesita al menos 2 URLs (media_urls).")
        children = [create_image_container(ig_id, token, u, "", is_child=True) for u in urls]
        for child in children:
            wait_until_ready(child, token)
        container = create_carousel_container(ig_id, token, children, caption)
    elif post_type == "reel":
        if not media_url:
            raise RuntimeError("Un reel necesita media_url (URL del video).")
        container = create_reel_container(ig_id, token, media_url, caption)
    else:  # image
        if not media_url:
            raise RuntimeError("Una imagen necesita media_url (URL de la imagen).")
        container = create_image_container(ig_id, token, media_url, caption)
    # Espera a que el contenedor esté FINISHED antes de publicar (evita el error
    # "Media ID is not available" cuando el media aún se está procesando).
    wait_until_ready(container, token)
    return publish_container(ig_id, token, container)


def build_caption(post: dict) -> str:
    """Caption en inglés (audiencia US/UK) + hashtags."""
    parts = [post.get("caption_en", "").strip()]
    tags = post.get("hashtags", [])
    if tags:
        parts.append(" ".join(tags))
    return "\n\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Modos de la CLI
# ---------------------------------------------------------------------------

def cmd_check(env) -> None:
    """Crea un contenedor de imagen de prueba SIN publicar (validación segura)."""
    ig_id, token = env["IG_USER_ID"], env["META_PAGE_TOKEN"]
    print("→ Validando credenciales creando un contenedor de prueba (no publica)…")
    container = create_image_container(ig_id, token, TEST_IMAGE_URL, TEST_CAPTION)
    print(f"   ✓ Contenedor creado: {container}")
    print("   ✓ Token, IG_USER_ID y descarga de imagen OK. Nada se publicó en el feed.")


def cmd_post_test(env) -> None:
    """Publica un post de prueba REAL en la cuenta."""
    ig_id, token = env["IG_USER_ID"], env["META_PAGE_TOKEN"]
    print("→ Publicando post de prueba REAL en @epic.plane…")
    media_id = publish_post(ig_id, token, "image", TEST_CAPTION, media_url=TEST_IMAGE_URL)
    print(f"   ✓ Publicado. Media ID: {media_id}")
    print("   Puedes borrarlo desde la app de Instagram cuando quieras.")


def cmd_run(env, month: str, dry_run: bool) -> None:
    """Publica del calendario los posts aprobados, no publicados y ya vencidos."""
    ig_id, token = env["IG_USER_ID"], env["META_PAGE_TOKEN"]
    path = CALENDAR_DIR / f"{month}.json"
    if not path.exists():
        sys.exit(f"No existe {path}.")
    data = json.loads(path.read_text(encoding="utf-8"))
    now = dt.datetime.now(dt.timezone.utc)

    due = []
    for p in data["posts"]:
        if not p.get("approved") or p.get("published"):
            continue
        when = dt.datetime.fromisoformat(f"{p['date']}T{p['time_utc']}:00+00:00")
        if when <= now:
            due.append(p)

    if not due:
        print("No hay posts aprobados, no publicados y ya vencidos. Nada que hacer.")
        return

    print(f"→ {len(due)} post(s) por publicar" + (" (DRY RUN)" if dry_run else "") + ":")
    for p in due:
        url = p.get("media_url") or (p["asset_path"] if str(p.get("asset_path", "")).startswith("http") else None)
        urls = p.get("media_urls")
        print(f"   - {p['id']} [{p['type']}] {p['date']} {p['time_utc']}UTC")
        if dry_run:
            continue
        if not url and not urls:
            print(f"     ⚠️  Sin URL pública (media_url/media_urls). Saltado. "
                  f"El pipeline de assets es la Sesión 3.")
            continue
        try:
            media_id = publish_post(ig_id, token, p["type"], build_caption(p),
                                    media_url=url, media_urls=urls)
            p["published"] = True
            p["published_media_id"] = media_id
            p["published_at"] = now.isoformat()
            print(f"     ✓ Publicado. Media ID: {media_id}")
        except RuntimeError as e:
            print(f"     ⚠️  Error: {e}")

    if not dry_run:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("→ Calendario actualizado (published:true en los que salieron).")


def main() -> None:
    ap = argparse.ArgumentParser(description="Epic.Plane — Publicador de Instagram (Módulo 2).")
    ap.add_argument("--check", action="store_true", help="Valida credenciales creando un contenedor de prueba (no publica).")
    ap.add_argument("--post-test", action="store_true", help="Publica un post de prueba REAL en la cuenta.")
    ap.add_argument("--run", action="store_true", help="Publica del calendario los posts aprobados y vencidos.")
    ap.add_argument("--month", help="Mes del calendario (YYYY-MM) para --run.")
    ap.add_argument("--dry-run", action="store_true", help="Con --run: muestra qué haría, sin publicar.")
    args = ap.parse_args()

    env = load_env()
    for k in ("IG_USER_ID", "META_PAGE_TOKEN"):
        if not env.get(k):
            sys.exit(f"Falta {k} en .env. Corre setup_meta.py primero.")

    try:
        if args.check:
            cmd_check(env)
        elif args.post_test:
            cmd_post_test(env)
        elif args.run:
            month = args.month or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")
            cmd_run(env, month, args.dry_run)
        else:
            ap.print_help()
    except RuntimeError as e:
        sys.exit(f"\n⚠️  {e}\n")


if __name__ == "__main__":
    main()
