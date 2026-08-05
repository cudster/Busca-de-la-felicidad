#!/usr/bin/env python3
"""
Epic.Plane — Módulo 3: Pipeline de assets.

Conecta el calendario con los archivos de imagen/video y sus URLs públicas.

Flujo:
  1. `prompts`: exporta una hoja por mes con, para cada post, el prompt visual y
     EXACTAMENTE cómo debe llamarse el archivo que generes (en Higgsfield u otra
     herramienta) y en qué carpeta guardarlo.
  2. Generas los medios y los dejas en  assets/semana-N/  con esos nombres.
  3. `link`: escanea las carpetas, empareja cada archivo con su post, calcula la
     URL pública (jsDelivr sobre tu repo de GitHub) y la escribe en el calendario
     como media_url / media_urls. Eso habilita  publish.py --run.
  4. `status`: te dice qué posts ya tienen asset y cuáles faltan.

Convención de nombres de archivo (dentro de assets/semana-N/):
  - imagen  -> pXX.jpg           (ej: p02.jpg)
  - reel    -> pXX.mp4           (ej: p04.mp4)
  - carrusel-> pXX_1.jpg, pXX_2.jpg, …  (un archivo por frame, en orden)

Config del repo (en .env), necesaria para `link`:
    GITHUB_REPO=usuario/repositorio
    GITHUB_BRANCH=main            # opcional, por defecto main

Uso:
    python3 assets.py prompts --month 2026-08
    python3 assets.py status  --month 2026-08
    python3 assets.py link    --month 2026-08
    python3 assets.py link    --month 2026-08 --dry-run

Sin librerías externas (solo la stdlib).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CALENDAR_DIR = ROOT / "calendar"
CONTENT_DIR = ROOT / "content"
ASSETS_DIR = ROOT / "assets"

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
VIDEO_EXTS = (".mp4", ".mov")


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    p = ROOT / ".env"
    if p.exists():
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def week_of(index: int) -> int:
    return index // 5 + 1


def load_calendar(month: str) -> tuple[Path, dict]:
    path = CALENDAR_DIR / f"{month}.json"
    if not path.exists():
        sys.exit(f"No existe {path}. Genera el mes primero con generate_content.py.")
    return path, json.loads(path.read_text(encoding="utf-8"))


def expected_names(post_index: int, post_type: str) -> str:
    pos = post_index + 1
    if post_type == "carousel":
        return f"p{pos:02d}_1.jpg, p{pos:02d}_2.jpg, … (un archivo por frame)"
    if post_type == "reel":
        return f"p{pos:02d}.mp4"
    return f"p{pos:02d}.jpg"


# ---------------------------------------------------------------------------
# prompts
# ---------------------------------------------------------------------------

def cmd_prompts(month: str) -> None:
    _, data = load_calendar(month)
    posts = data["posts"]
    lines = [
        f"# Hoja de assets — {month}",
        "",
        "Genera cada medio con el prompt visual y guárdalo con el nombre EXACTO "
        "indicado, en la carpeta indicada. Luego corre `python3 assets.py link "
        f"--month {month}`.",
        "",
    ]
    current_week = None
    for i, p in enumerate(posts):
        week = week_of(i)
        if week != current_week:
            current_week = week
            lines.append(f"\n## Semana {week}  →  carpeta `assets/semana-{week}/`\n")
        lines.append(f"### {p['id']} · {p['type']}")
        lines.append(f"- **Guardar como:** `assets/semana-{week}/{expected_names(i, p['type'])}`")
        lines.append(f"- **Topic:** {p.get('topic','')}")
        lines.append(f"- **Prompt visual:** {p.get('visual_prompt','')}")
        lines.append("")
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    out = CONTENT_DIR / f"prompts-{month}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"✓ Hoja de prompts escrita: {out}")
    print(f"  {len(posts)} posts. Genera los medios, guárdalos con los nombres "
          f"indicados y luego corre: python3 assets.py link --month {month}")


# ---------------------------------------------------------------------------
# emparejar archivos <-> posts
# ---------------------------------------------------------------------------

def find_assets(post_index: int, post_type: str) -> list[Path]:
    week = week_of(post_index)
    folder = ASSETS_DIR / f"semana-{week}"
    if not folder.exists():
        return []
    pos = post_index + 1
    stem = f"p{pos:02d}"
    if post_type == "carousel":
        # pXX_1.*, pXX_2.*, … ordenados por el número de frame.
        frames = []
        for f in folder.iterdir():
            n = f.stem  # p02_1
            if n.startswith(f"{stem}_") and f.suffix.lower() in IMAGE_EXTS:
                try:
                    idx = int(n.split("_", 1)[1])
                except ValueError:
                    continue
                frames.append((idx, f))
        return [f for _, f in sorted(frames)]
    # imagen o reel: pXX.<ext> (excluye pXX_*)
    exts = VIDEO_EXTS if post_type == "reel" else IMAGE_EXTS
    return [f for f in folder.iterdir()
            if f.stem == stem and f.suffix.lower() in exts]


def public_url(env: dict[str, str], week: int, filename: str) -> str:
    repo = env.get("GITHUB_REPO")
    branch = env.get("GITHUB_BRANCH", "main")
    if not repo:
        repo = _repo_from_git()
    if not repo:
        sys.exit(
            "Falta GITHUB_REPO en .env (formato usuario/repositorio).\n"
            "Agrégalo o crea el repo primero; lo necesito para armar las URLs públicas."
        )
    return f"https://cdn.jsdelivr.net/gh/{repo}@{branch}/assets/semana-{week}/{filename}"


def _repo_from_git() -> str | None:
    try:
        url = subprocess.check_output(
            ["git", "-C", str(ROOT), "config", "--get", "remote.origin.url"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None
    # git@github.com:user/repo.git  |  https://github.com/user/repo.git
    for sep in ("github.com:", "github.com/"):
        if sep in url:
            path = url.split(sep, 1)[1]
            return path[:-4] if path.endswith(".git") else path
    return None


# ---------------------------------------------------------------------------
# status / link
# ---------------------------------------------------------------------------

def cmd_status(month: str) -> None:
    _, data = load_calendar(month)
    ready = missing = 0
    for i, p in enumerate(data["posts"]):
        files = find_assets(i, p["type"])
        ok = (len(files) >= 2) if p["type"] == "carousel" else (len(files) == 1)
        mark = "✓" if ok else "·"
        if ok:
            ready += 1
        else:
            missing += 1
        detail = ", ".join(f.name for f in files) if files else "(sin archivo)"
        print(f" {mark} {p['id']} [{p['type']:8}] {detail}")
    print(f"\nListos: {ready} · Faltan: {missing} / {len(data['posts'])}")


def cmd_link(month: str, dry_run: bool) -> None:
    env = load_env()
    path, data = load_calendar(month)
    linked = 0
    for i, p in enumerate(data["posts"]):
        files = find_assets(i, p["type"])
        week = week_of(i)
        if p["type"] == "carousel":
            if len(files) < 2:
                continue
            urls = [public_url(env, week, f.name) for f in files]
            if not dry_run:
                p["media_urls"] = urls
                p.pop("media_url", None)
            print(f" ✓ {p['id']} carrusel · {len(urls)} frames")
        else:
            if len(files) != 1:
                continue
            url = public_url(env, week, files[0].name)
            if not dry_run:
                p["media_url"] = url
                p.pop("media_urls", None)
            print(f" ✓ {p['id']} {p['type']} · {files[0].name}")
        linked += 1

    if dry_run:
        print(f"\n(DRY RUN) Enlazaría {linked} post(s). No se escribió nada.")
        return
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n✓ {linked} post(s) enlazados con su URL pública en {path.name}.")
    if linked:
        print("  Ya puedes publicar con: python3 publish.py --run --month " + month)


def main() -> None:
    ap = argparse.ArgumentParser(description="Epic.Plane — Pipeline de assets (Módulo 3).")
    ap.add_argument("command", choices=["prompts", "status", "link"], help="Acción a ejecutar.")
    ap.add_argument("--month", required=True, help="Mes del calendario (YYYY-MM).")
    ap.add_argument("--dry-run", action="store_true", help="Con link: muestra sin escribir.")
    args = ap.parse_args()

    if args.command == "prompts":
        cmd_prompts(args.month)
    elif args.command == "status":
        cmd_status(args.month)
    elif args.command == "link":
        cmd_link(args.month, args.dry_run)


if __name__ == "__main__":
    main()
