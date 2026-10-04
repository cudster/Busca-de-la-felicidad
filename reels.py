#!/usr/bin/env python3
"""
reels.py — Genera el video de los posts tipo `reel` con Kling 3.0 (API Higgsfield).

La jugada: NO se inventa el avión. Se parte de la foto REAL y gratis de Wikimedia
Commons que ya cura `media.py` (avión correcto, librea correcta) y se le paga sólo
el MOVIMIENTO. Así el reel es video de verdad y el avión corresponde al caption.

Por qué Kling 3.0 y no Wan 3.0: en la comparación del 2026-09-23 Wan salió más
barata y en 1080p, pero fusionó un segundo avión dentro del fuselaje. Kling respeta
la geometría (4 motores, librea legible). Para una cuenta de aviación, donde la
gente CUENTA MOTORES, correcto le gana a bonito.

El mp4 queda en el CDN de Higgsfield con URL pública, que es justo lo que
`publish.py` necesita en asset_path — no hay que hospedar nada.

Uso:
    python3 reels.py --month 2026-10 --posts P02,P03,P05        # genera y muestra
    python3 reels.py --month 2026-10 --posts P02 --to-sheet     # además lo escribe
    python3 reels.py --month 2026-10 --posts P02 --duration 5   # más barato
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import media

ROOT = Path(__file__).resolve().parent
API = "https://api.higgsfield.ai"
MODELO = "kling-video/v3.0/std/image-to-video"
USD_POR_SEGUNDO = 0.042          # precio con el descuento vigente (ver open.higgsfield.ai)
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")

# Lo que NUNCA debe aparecer. El pecado capital en aviación es el conteo de motores:
# un A380 de seis motores lo caza cualquiera de tus seguidores.
NEGATIVO = ("extra engines, wrong engine count, duplicate aircraft, second airplane, "
            "two fuselages, morphing wings, deformed fuselage, warped livery, "
            "distorted text, garbled letters, watermark, cartoon, CGI look, "
            "crash, fire, smoke, explosion")


def credenciales() -> dict:
    for l in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if l.startswith("HF_CREDENTIALS="):
            cred = l.split("=", 1)[1].strip().strip('"').strip("'")
            if ":" not in cred:
                sys.exit("HF_CREDENTIALS debe ser 'key-id:key-secret'.")
            kid, ksec = cred.split(":", 1)
            return {"hf-api-key": kid, "hf-secret": ksec, "User-Agent": UA,
                    "Accept": "application/json", "Content-Type": "application/json"}
    sys.exit("Falta HF_CREDENTIALS en .env.")


def foto_inicial(post: dict) -> str | None:
    """La foto real del avión/fenómeno, recortada 9:16 para que el reel nazca vertical."""
    for q in (media.derive_fenomeno(post), media.derive_aircraft_wiki(post)):
        if not q:
            continue
        ph = media.commons_photo(q, width=1920)
        if ph:
            url = ("https://images.weserv.nl/?url=" + urllib.parse.quote(ph["url"], safe="") +
                   "&w=1080&h=1920&fit=cover&a=attention&output=jpg")
            _precalentar(url)
            return url
    return None


def _precalentar(url: str) -> None:
    """Pide la imagen una vez para dejarla cacheada en weserv.

    Si Commons devuelve el ORIGINAL (no una miniatura ya generada), weserv tiene
    que bajarlo y procesarlo en frío, y el descargador de Higgsfield se rinde
    antes de que responda: el job muere con "Could not download the file".
    Así le llega una URL que contesta al instante.
    """
    try:
        urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60).read()
    except Exception:
        pass        # si falla, igual se intenta: Higgsfield puede alcanzar a bajarla


def prompt_de(post: dict) -> str:
    """Movimiento suave + la orden explícita de no alterar el avión."""
    return (f"Real aviation footage. {post.get('visual_prompt', '')[:220]} "
            "The camera moves slowly and steadily. The aircraft keeps its exact original "
            "shape, its correct number of engines and its real livery. Photorealistic, "
            "no text overlay.")


def generar(post: dict, headers: dict, duracion: int) -> dict | None:
    img = foto_inicial(post)
    if not img:
        print(f"   ⚠️  {post['id']}: no encontré foto base en Commons.")
        return None
    body = {"prompt": prompt_de(post), "image_url": img, "duration": duracion,
            "cfg_scale": 0.5, "negative_prompt": NEGATIVO}
    req = urllib.request.Request(f"{API}/{MODELO}", data=json.dumps(body).encode(),
                                 headers=headers, method="POST")
    try:
        out = json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as e:
        print(f"   ⚠️  {post['id']}: HTTP {e.code} {e.read()[:200].decode('utf-8','replace')}")
        return None
    rid = out.get("request_id") or out.get("id")
    print(f"   → {post['id']} encolado ({duracion}s · ~${duracion * USD_POR_SEGUNDO:.2f}) id={rid}")
    return {"id": post["id"], "request_id": rid}


def esperar(trabajos: list[dict], headers: dict, max_min: int = 15) -> dict:
    """Devuelve {post_id: url_mp4}. Kling tarda 1-3 min por clip."""
    h = {k: v for k, v in headers.items() if k != "Content-Type"}
    listos: dict[str, str] = {}
    fallidos: set[str] = set()
    for _ in range(max_min * 3):
        for t in trabajos:
            if t["id"] in listos or t["id"] in fallidos:
                continue
            try:
                d = json.load(urllib.request.urlopen(urllib.request.Request(
                    f"{API}/requests/{t['request_id']}/status", headers=h), timeout=40))
            except Exception:
                continue
            st = d.get("status")
            if st in ("completed", "succeeded"):
                url = (d.get("video") or {}).get("url")
                if url:
                    listos[t["id"]] = url
                    print(f"   ✓ {t['id']} listo")
                else:
                    fallidos.add(t["id"])
            elif st in ("failed", "canceled", "nsfw"):
                print(f"   ⚠️  {t['id']}: {st}")
                fallidos.add(t["id"])
        if len(listos) + len(fallidos) >= len(trabajos):
            break
        time.sleep(20)
    return listos


def main() -> None:
    ap = argparse.ArgumentParser(description="Genera los reels con Kling 3.0 desde la foto real.")
    ap.add_argument("--month", required=True, help="Mes del calendario (YYYY-MM).")
    ap.add_argument("--posts", required=True, help="Ids separados por coma, ej P02,P03,P05.")
    ap.add_argument("--duration", type=int, default=10, choices=[5, 10], help="Segundos por clip.")
    ap.add_argument("--to-sheet", action="store_true", help="Escribe el mp4 en asset_path.")
    a = ap.parse_args()

    path = ROOT / "calendar" / f"{a.month}.json"
    if not path.exists():
        sys.exit(f"No existe {path}.")
    todos = json.loads(path.read_text(encoding="utf-8"))["posts"]
    pedidos = {p.strip().upper() for p in a.posts.split(",")}
    posts = [p for p in todos if p["id"].rsplit("-", 1)[-1] in pedidos]
    if not posts:
        sys.exit(f"No encontré esos posts en {a.month}.")

    no_reel = [p["id"] for p in posts if p.get("type") != "reel"]
    if no_reel:
        print(f"⚠️  No son tipo reel y se omiten: {', '.join(no_reel)}")
        posts = [p for p in posts if p.get("type") == "reel"]
    if not posts:
        sys.exit("Nada que generar.")

    costo = len(posts) * a.duration * USD_POR_SEGUNDO
    print(f"→ {len(posts)} reel(s) con Kling 3.0 · {a.duration}s c/u · costo estimado ${costo:.2f}\n")

    headers = credenciales()
    trabajos = [t for t in (generar(p, headers, a.duration) for p in posts) if t]
    if not trabajos:
        sys.exit("No se encoló nada.")
    print("\n   esperando el render…")
    listos = esperar(trabajos, headers)

    print(f"\n✓ {len(listos)}/{len(trabajos)} reel(s) generados:")
    for pid, url in listos.items():
        print(f"   {pid}  {url}")

    if not listos:
        return
    if not a.to_sheet:
        print("\n(no se escribió en la hoja; agrega --to-sheet cuando los hayas revisado)")
        return
    import sheets
    n_ok, faltan = sheets.batch_set_media(
        [{"id": pid, "asset_path": url, "preview_url": url} for pid, url in listos.items()])
    print(f"\n✓ {n_ok} reel(s) escritos en la Google Sheet.")
    if faltan:
        print(f"  (no estaban en la hoja: {', '.join(faltan)})")


if __name__ == "__main__":
    main()
