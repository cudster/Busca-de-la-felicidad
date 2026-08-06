#!/usr/bin/env python3
"""
Epic.Plane — Capa de Google Sheets (aprobación desde el celular).

Módulo compartido entre el generador (escribe el calendario a la hoja) y el
publicador (lee solo las filas aprobadas y marca las publicadas).

Credenciales:
  - En local (dev): archivo  credentials.json  en la raíz.
  - En la nube (GitHub Actions): variable de entorno  GOOGLE_CREDENTIALS  con el
    contenido JSON completo de la cuenta de servicio.
SHEET_ID se lee de la variable de entorno o del .env.

La pestaña se busca por nombre "calendar" sin distinguir mayúsculas.

Requiere: gspread, google-auth  (ver requirements.txt).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Orden EXACTO de columnas en la hoja (sección 2 del setup).
HEADERS = [
    "id", "date", "time_utc", "type", "topic", "hook_en", "caption_en",
    "caption_es", "hashtags", "cta", "visual_prompt", "asset_path",
    "approved", "feedback", "published", "published_at",
]
# Columnas que escribe el generador (el resto son de Felipe/publicador).
GEN_COLS = HEADERS[:12]          # id … asset_path (asset_path lo comparten)
GEN_ONLY = HEADERS[:11]          # id … visual_prompt (nunca se pisan tras esto: asset_path/approved/feedback/published/published_at)

APPROVED_COL_IDX = HEADERS.index("approved")   # 12 (0-based) -> columna M
PUBLISHED_COL_IDX = HEADERS.index("published")  # 14 (0-based) -> columna O
FEEDBACK_COL_IDX = HEADERS.index("feedback")    # 13


# ---------------------------------------------------------------------------
# Config / conexión
# ---------------------------------------------------------------------------

def _env(key: str) -> str | None:
    if os.environ.get(key):
        return os.environ[key]
    p = ROOT / ".env"
    if p.exists():
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                if k.strip() == key:
                    return v.strip().strip('"').strip("'")
    return None


def _credentials():
    from google.oauth2.service_account import Credentials
    raw = os.environ.get("GOOGLE_CREDENTIALS")
    if raw:
        return Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)
    path = ROOT / "credentials.json"
    if not path.exists():
        raise RuntimeError(
            "No encontré credenciales de Google: ni GOOGLE_CREDENTIALS (env) "
            "ni credentials.json en la raíz."
        )
    return Credentials.from_service_account_file(str(path), scopes=SCOPES)


def get_worksheet():
    """Abre la hoja y devuelve la pestaña 'calendar' (case-insensitive)."""
    import gspread
    sheet_id = _env("SHEET_ID")
    if not sheet_id:
        raise RuntimeError("Falta SHEET_ID (en env o .env).")
    gc = gspread.authorize(_credentials())
    sh = gc.open_by_key(sheet_id)
    for ws in sh.worksheets():
        if ws.title.lower() == "calendar":
            return sh, ws
    # Si no existe, crea una pestaña 'calendar'.
    ws = sh.add_worksheet(title="calendar", rows=100, cols=len(HEADERS))
    return sh, ws


# ---------------------------------------------------------------------------
# Escritura (generador)
# ---------------------------------------------------------------------------

def _bool_str(v) -> str:
    return "TRUE" if v in (True, "TRUE", "true", 1, "1") else "FALSE"


def _post_to_row(post: dict, existing: dict | None) -> list[str]:
    """Fila para un post. Columnas del generador siempre frescas; las humanas
    se preservan si la fila ya existía; si es nueva, se siembran del post."""
    hashtags = post.get("hashtags", [])
    if isinstance(hashtags, list):
        hashtags = " ".join(hashtags)
    gen = {
        "id": post["id"], "date": post.get("date", ""), "time_utc": post.get("time_utc", ""),
        "type": post.get("type", ""), "topic": post.get("topic", ""),
        "hook_en": post.get("hook_en", ""), "caption_en": post.get("caption_en", ""),
        "caption_es": post.get("caption_es", ""), "hashtags": hashtags,
        "cta": post.get("cta", ""), "visual_prompt": post.get("visual_prompt", ""),
    }
    if existing:  # preservar lo que ya editó Felipe / escribió el publicador
        human = {c: existing.get(c, "") for c in
                 ("asset_path", "approved", "feedback", "published", "published_at")}
    else:  # fila nueva: sembrar del post (migra approvals previos del JSON)
        human = {
            "asset_path": post.get("media_url") or post.get("asset_path", ""),
            "approved": _bool_str(post.get("approved")),
            "feedback": "",
            "published": _bool_str(post.get("published")),
            "published_at": post.get("published_at", ""),
        }
    row = {**gen, **human}
    return [str(row.get(h, "")) for h in HEADERS]


def write_calendar_to_sheet(posts: list[dict]) -> int:
    """Upsert del calendario a la hoja por id, sin pisar approved/feedback/asset_path.
    Devuelve el número de filas escritas."""
    sh, ws = get_worksheet()
    existing_rows = ws.get_all_records() if ws.row_count and ws.get_all_values() else []
    by_id = {str(r.get("id")): r for r in existing_rows}

    values = [HEADERS] + [_post_to_row(p, by_id.get(p["id"])) for p in posts]

    ws.clear()
    ws.update(values=values, range_name="A1")

    try:
        _apply_formatting(sh, ws, len(posts))
    except Exception as e:  # el formato es cosmético; no debe romper el upsert
        print(f"   (aviso: no pude aplicar formato/casillas: {e})")
    return len(posts)


def _apply_formatting(sh, ws, n_rows: int) -> None:
    """Casillas de verificación en approved/published, encabezado congelado y
    formato condicional (verde=aprobado, amarillo=feedback sin aprobar)."""
    gid = ws.id
    last = n_rows + 1  # +1 por el encabezado
    green = {"red": 0.72, "green": 0.88, "blue": 0.72}
    yellow = {"red": 1.0, "green": 0.95, "blue": 0.70}
    requests = [
        # Casillas approved (M) y published (O)
        {"setDataValidation": {
            "range": {"sheetId": gid, "startRowIndex": 1, "endRowIndex": last,
                      "startColumnIndex": APPROVED_COL_IDX, "endColumnIndex": APPROVED_COL_IDX + 1},
            "rule": {"condition": {"type": "BOOLEAN"}, "showCustomUi": True}}},
        {"setDataValidation": {
            "range": {"sheetId": gid, "startRowIndex": 1, "endRowIndex": last,
                      "startColumnIndex": PUBLISHED_COL_IDX, "endColumnIndex": PUBLISHED_COL_IDX + 1},
            "rule": {"condition": {"type": "BOOLEAN"}, "showCustomUi": True}}},
        # Encabezado congelado
        {"updateSheetProperties": {
            "properties": {"sheetId": gid, "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount"}},
        # Verde si approved = TRUE
        {"addConditionalFormatRule": {"index": 0, "rule": {
            "ranges": [{"sheetId": gid, "startRowIndex": 1, "endRowIndex": last,
                        "startColumnIndex": 0, "endColumnIndex": len(HEADERS)}],
            "booleanRule": {
                "condition": {"type": "CUSTOM_FORMULA",
                              "values": [{"userEnteredValue": "=$M2=TRUE"}]},
                "format": {"backgroundColor": green}}}}},
        # Amarillo si hay feedback y NO está aprobado
        {"addConditionalFormatRule": {"index": 1, "rule": {
            "ranges": [{"sheetId": gid, "startRowIndex": 1, "endRowIndex": last,
                        "startColumnIndex": 0, "endColumnIndex": len(HEADERS)}],
            "booleanRule": {
                "condition": {"type": "CUSTOM_FORMULA",
                              "values": [{"userEnteredValue": '=AND($N2<>"",$M2<>TRUE)'}]},
                "format": {"backgroundColor": yellow}}}}},
    ]
    sh.batch_update({"requests": requests})


# ---------------------------------------------------------------------------
# Lectura (publicador)
# ---------------------------------------------------------------------------

def _is_true(v) -> bool:
    return v in (True, "TRUE", "true", 1, "1")


def read_approved_posts() -> list[dict]:
    """Filas con approved=TRUE y published=FALSE. Devuelve dicts con la fila +
    su número de fila en la hoja (_row) para poder marcar published después."""
    _, ws = get_worksheet()
    records = ws.get_all_records()
    out = []
    for i, r in enumerate(records, start=2):  # fila 1 = encabezado
        if _is_true(r.get("approved")) and not _is_true(r.get("published")):
            r["_row"] = i
            out.append(r)
    return out


def mark_published(row_number: int, published_at: str) -> None:
    """Marca published=TRUE y published_at en una fila (por número de fila)."""
    _, ws = get_worksheet()
    ws.update_cell(row_number, PUBLISHED_COL_IDX + 1, "TRUE")
    ws.update_cell(row_number, HEADERS.index("published_at") + 1, published_at)
