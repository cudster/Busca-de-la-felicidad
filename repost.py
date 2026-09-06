#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
repost.py — Motor de repost con crédito (Epic.Plane / Al Día)

La cuenta creció históricamente reposteando a otros spotters CON CRÉDITO. Esto lo
hace sistemático y — clave — RESPETANDO DERECHOS: nunca republica contenido ajeno
sin permiso del autor.

Flujo:
  1) Pedir permiso (una vez por autor):
       python3 repost.py --dm @creator
     Imprime el DM listo para enviar. Guarda la respuesta.

  2) Con el permiso YA otorgado, agendar el repost:
       python3 repost.py --add --date 2026-10-11 --creator @creator \\
           --credit-name "Jane Doe" --media-url https://... \\
           --topic "Low pass brutal" --type reel --permission-confirmed [--to-sheet]

     Sin --permission-confirmed, se niega (recordatorio de pedir permiso primero).
     El post queda approved=false para que lo revises antes de publicar.

Notas:
  - --media-url debe ser una URL PÚBLICA del medio que el autor te autorizó a usar
    (la Graph API de IG exige URL pública). No descarga ni scrapea nada.
  - El crédito va SIEMPRE en el caption: "📷 @creator (reposteado con permiso)".
"""
from __future__ import annotations
import argparse, datetime as dt, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CALENDAR_DIR = ROOT / "calendar"

DM_TEMPLATE = (
    "Hola {creator} 👋 Soy de @epic.plane. Nos ENCANTÓ tu toma"
    "{about} — tiene justo la vibra que aman nuestros seguidores. "
    "¿Nos das permiso para compartirla en nuestro feed dándote el crédito completo "
    "(@{handle} en la foto y en el caption)? Por supuesto la bajamos al instante si "
    "prefieres que no. ¡Gracias por el gran trabajo! ✈️"
)


def dm_template(creator: str, about: str = "") -> str:
    handle = creator.lstrip("@")
    about = f" \"{about}\"" if about else ""
    return DM_TEMPLATE.format(creator=creator if creator.startswith("@") else "@"+handle,
                              handle=handle, about=about)


def _next_repost_id(posts: list[dict], month_label: str) -> str:
    n = 0
    for p in posts:
        pid = p.get("id", "")
        if pid.startswith(f"{month_label}-R"):
            try:
                n = max(n, int(pid.rsplit("R", 1)[1]))
            except Exception:
                pass
    return f"{month_label}-R{n+1:02d}"


def build_caption(topic: str, creator: str, hook: str | None) -> tuple[str, str]:
    handle = creator if creator.startswith("@") else "@" + creator
    hook = hook or topic
    credit_en = f"📷 {handle} (reposted with permission)"
    credit_es = f"📷 {handle} (reposteado con permiso)"
    cap_en = f"{hook} 😍✈️\nDouble tap if this blew your mind 👇 and give {handle} a follow\n\n{credit_en}"
    cap_es = f"{hook} 😍✈️\nDale doble tap si te encanta 👇 y sigue a {handle}\n\n{credit_es}"
    return cap_en, cap_es


def add_repost(args) -> None:
    if not args.permission_confirmed:
        sys.exit(
            "✋ Falta --permission-confirmed.\n"
            "   Primero pide permiso al autor (usa:  python3 repost.py --dm "
            f"{args.creator} ) y, cuando te diga que sí, vuelve a correr esto con "
            "--permission-confirmed."
        )
    try:
        date = dt.date.fromisoformat(args.date)
    except ValueError:
        sys.exit(f"Fecha inválida: {args.date} (usa YYYY-MM-DD).")
    month_label = f"{date.year:04d}-{date.month:02d}"
    path = CALENDAR_DIR / f"{month_label}.json"
    if not path.exists():
        sys.exit(f"No existe {path}. Genera el mes primero con generate_content.py.")
    data = json.loads(path.read_text(encoding="utf-8"))
    posts = data.setdefault("posts", [])

    rid = _next_repost_id(posts, month_label)
    cap_en, cap_es = build_caption(args.topic, args.creator, args.hook)
    post = {
        "id": rid,
        "date": args.date,
        "time_utc": args.time,
        "type": args.type,
        "pillar": "community_repost",
        "cta": "none",
        "topic": args.topic,
        "hook_en": args.hook or args.topic,
        "caption_en": cap_en,
        "caption_es": cap_es,
        "hashtags": ["#avgeek", "#planespotting", "#aviation", "#aviationphotography",
                     "#instaplane", "#megaplane"],
        "visual_prompt": f"(repost autorizado de {args.creator})",
        "asset_path": args.media_url,
        "credit": {"creator": args.creator, "name": args.credit_name or "",
                    "permission": True, "source_url": args.source_url or ""},
        "approved": False,
        "published": False,
    }
    posts.append(post)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"✓ Repost agregado: {rid} [{args.type}] {args.date} — crédito a {args.creator}")
    print(f"  Caption:\n    {cap_en.splitlines()[0]}  …  {cap_en.splitlines()[-1]}")
    print("  approved=false → revísalo y apruébalo antes de publicar.")

    if args.to_sheet:
        try:
            import sheets
            sheets.write_calendar_to_sheet(posts)
            print("✓ Subido a la Google Sheet (upsert).")
        except Exception as e:
            print(f"⚠️  No pude subir a la hoja: {e}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Motor de repost con crédito (permiso-primero).")
    ap.add_argument("--dm", metavar="@creator", help="Imprime el DM para pedir permiso al autor.")
    ap.add_argument("--about", default="", help="(con --dm) descripción corta de la toma, para personalizar.")

    ap.add_argument("--add", action="store_true", help="Agenda un repost YA autorizado en el calendario.")
    ap.add_argument("--date", help="Fecha del repost YYYY-MM-DD.")
    ap.add_argument("--time", default="22:00", help="Hora UTC (por defecto 22:00).")
    ap.add_argument("--type", default="reel", choices=["reel", "image"], help="Tipo de post.")
    ap.add_argument("--creator", help="@usuario del autor a acreditar.")
    ap.add_argument("--credit-name", help="Nombre real del autor (opcional).")
    ap.add_argument("--media-url", help="URL pública del medio autorizado.")
    ap.add_argument("--topic", default="Repost de la comunidad", help="Tema/one-liner.")
    ap.add_argument("--hook", help="Gancho del caption (opcional).")
    ap.add_argument("--source-url", help="Link al post original (opcional, para registro).")
    ap.add_argument("--permission-confirmed", action="store_true",
                    help="Confirmas que el autor te dio permiso. Requerido para --add.")
    ap.add_argument("--to-sheet", action="store_true", help="Sube el calendario a la Google Sheet.")
    args = ap.parse_args()

    if args.dm:
        print(dm_template(args.dm, args.about))
        return
    if args.add:
        for req in ("date", "creator", "media_url"):
            if not getattr(args, req):
                sys.exit(f"Falta --{req.replace('_','-')} para --add.")
        add_repost(args)
        return
    ap.print_help()


if __name__ == "__main__":
    main()
