#!/usr/bin/env python3
"""
reel_local.py — Reels de video a partir de la FOTO REAL, con ffmpeg. Costo $0.

Por qué existe: los reels de "spot-the-aircraft" nombran un avión concreto
(SR-71, An-225, C-17, 777X). El video de stock no tiene esos aviones, y generar
con IA ya demostró dos problemas: cuesta plata y deforma los aviones raros
(a Kling el An-225 le quedó con cuatro motores en vez de seis).

La foto curada de Wikimedia SÍ tiene el avión correcto. Un zoom lento que abre
desde un detalle hasta el avión completo es exactamente el formato que pide el
guion —revelación en el último segundo— y es video real para efectos de
alcance, que en esta cuenta rinde ~50% más que una foto.

El mp4 queda en `assets/reels/` del repo y se sirve por jsDelivr: permanente,
a diferencia del CDN de Higgsfield, que expiró y se llevó 7 reels de octubre.

Uso:
    python3 reel_local.py --month 2026-11                 # todos los reels
    python3 reel_local.py --month 2026-11 --posts P01,P03
    python3 reel_local.py --month 2026-11 --to-sheet
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import media

ROOT = Path(__file__).resolve().parent
REELS = ROOT / "assets" / "reels"
DUR = 10                 # segundos
FPS = 30
W, H = 1080, 1920        # 9:16
# Se renderiza con headroom y se recorta: el zoompan de ffmpeg tiembla si se
# le pide ampliar más allá del tamaño de origen.
SRC_W, SRC_H = 1620, 2880


def _env(clave: str) -> str | None:
    for l in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if l.startswith(clave + "="):
            return l.split("=", 1)[1].strip()
    return None


def foto_de(post: dict) -> str | None:
    """La misma foto curada que usaría el post como imagen."""
    import re
    m = re.search(r"P(\d+)$", str(post.get("id", "")))
    var = int(m.group(1)) if m else 0
    for q in (media.derive_fenomeno(post), media.derive_aircraft_wiki(post)):
        if not q:
            continue
        ph = media.commons_photo(q, width=2400, variante=var)
        if ph:
            return ph["url"]
    return None


def construir(post: dict) -> str | None:
    pid = post["id"]
    url = foto_de(post)
    if not url:
        print(f"   ⚠️  {pid}: sin foto base en Commons.")
        return None
    REELS.mkdir(parents=True, exist_ok=True)
    jpg = REELS / f".{pid}.jpg"
    mp4 = REELS / f"{pid}.mp4"
    try:
        urllib.request.urlretrieve(media.crop_45(url).replace("w=1080&h=1350", f"w={SRC_W}&h={SRC_H}"), jpg)
    except Exception as e:
        print(f"   ⚠️  {pid}: no pude bajar la foto ({type(e).__name__})")
        return None

    total = DUR * FPS
    # Zoom-OUT: abre cerrado en un detalle y revela el avión completo al final.
    # Es la estructura que pide el guion, y además el zoom-out disimula mejor
    # la falta de resolución que un zoom-in.
    vf = (f"scale={SRC_W}:{SRC_H}:force_original_aspect_ratio=increase,"
          f"crop={SRC_W}:{SRC_H},"
          f"zoompan=z='if(eq(on,0),1.35,max(1.001,zoom-0.0012))':"
          f"d={total}:s={W}x{H}:fps={FPS},"
          f"format=yuv420p")
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(jpg),
                        "-vf", vf, "-t", str(DUR), "-r", str(FPS),
                        "-c:v", "libx264", "-crf", "24", "-preset", "medium",
                        "-pix_fmt", "yuv420p", str(mp4)],
                       check=True, timeout=600)
    except Exception as e:
        print(f"   ⚠️  {pid}: ffmpeg falló ({e})")
        return None
    finally:
        jpg.unlink(missing_ok=True)

    mb = mp4.stat().st_size / 1e6
    repo, rama = _env("GITHUB_REPO"), _env("GITHUB_BRANCH") or "main"
    if not repo:
        print(f"   ⚠️  falta GITHUB_REPO en .env")
        return None
    print(f"   ✓ {pid}  {mb:.1f} MB  ({DUR}s, {W}x{H})")
    return f"https://cdn.jsdelivr.net/gh/{repo}@{rama}/assets/reels/{pid}.mp4"


def main() -> None:
    ap = argparse.ArgumentParser(description="Reels desde la foto real, con ffmpeg. $0.")
    ap.add_argument("--month", required=True)
    ap.add_argument("--posts", help="Ids separados por coma; por defecto TODOS los reels.")
    ap.add_argument("--to-sheet", action="store_true")
    a = ap.parse_args()

    f = ROOT / "calendar" / f"{a.month}.json"
    if not f.exists():
        sys.exit(f"No existe {f}")
    posts = [p for p in json.loads(f.read_text(encoding="utf-8"))["posts"]
             if p.get("type") == "reel"]
    if a.posts:
        pedidos = {x.strip().upper() for x in a.posts.split(",")}
        posts = [p for p in posts if p["id"].rsplit("-", 1)[-1] in pedidos]
    if not posts:
        sys.exit("No hay reels que construir.")

    print(f"→ {len(posts)} reel(s) desde foto real · ffmpeg · costo $0\n")
    listos = {}
    for p in posts:
        u = construir(p)
        if u:
            listos[p["id"]] = u

    print(f"\n✓ {len(listos)}/{len(posts)} construidos en assets/reels/")
    print("   Falta: git add assets/reels && git commit && git push (jsDelivr los sirve desde el repo)")
    if not a.to_sheet or not listos:
        return
    import sheets
    n, faltan = sheets.batch_set_media(
        [{"id": k, "asset_path": v, "preview_url": v} for k, v in listos.items()])
    print(f"✓ {n} escritos en la Google Sheet." + (f" (faltan: {faltan})" if faltan else ""))


if __name__ == "__main__":
    main()
