# Rossacuore — Guía de accesos para salir en vivo

Objetivo: dejar `publish.py --client rossacuore --sheet` publicando en @rossacuore_chile.
Se necesitan **3 variables**: `ROSSACUORE_IG_USER_ID`, `ROSSACUORE_TOKEN`, `ROSSACUORE_SHEET_ID`.

---

## Parte 1 — Lo que hace el CLIENTE (Verónica)
1. **IG a cuenta Empresa:** en la app de Instagram de @rossacuore_chile →
   Configuración → Cuenta → *Cambiar a cuenta profesional* → **Empresa**.
2. **Página de Facebook:** crear una Página de FB para Rossacuore (si no existe) y
   **vincular** la cuenta de Instagram a esa Página (IG → Configuración → Cuentas
   vinculadas → Facebook; o desde la Página FB → Configuración → Instagram).
3. **Dar acceso a la agencia:** en **Meta Business Suite / Business Manager**, agregar a
   Felipe (o la app de la agencia) como **Administrador** de la Página → así podemos
   generar el token y gestionar.
4. **Activar "Permitir acceso a los mensajes"** en la app de IG (para DMs, a futuro).
5. **Compartir material:** link de Drive/Dropbox con fotos/videos, y el **link de
   WhatsApp Business** para la bio.

## Parte 2 — Lo que hace la AGENCIA (nosotros)
6. **Token de Rossacuore** (Graph API Explorer, app "Epic.Plane Publisher"):
   generar **User Token** eligiendo la **Página de Rossacuore** + su IG, con scopes:
   `instagram_basic`, `instagram_content_publish`, `instagram_manage_comments`,
   `instagram_manage_insights`, `pages_read_engagement`, `pages_show_list`.
7. Pegar el token corto en `.env` (`META_SHORT_TOKEN=…`) y correr:
   ```bash
   python3 setup_meta.py --client rossacuore
   ```
   → busca la página conectada a **@rossacuore_chile** y guarda
   `ROSSACUORE_IG_USER_ID` + `ROSSACUORE_TOKEN` (sin tocar los de Epic.Plane).
8. **Google Sheet de Rossacuore:** crear una hoja nueva, compartirla como **Editor** con
   el bot `epic-plane-bot@igneous-nucleus-504700-u5.iam.gserviceaccount.com`, copiar su
   ID (de la URL) y ponerlo en `.env`: `ROSSACUORE_SHEET_ID=…`.
9. **Secrets en GitHub** (para el cron 24/7): agregar `ROSSACUORE_TOKEN`,
   `ROSSACUORE_IG_USER_ID`, `ROSSACUORE_SHEET_ID`.

## Parte 3 — Primer mes en vivo
10. Generar contenido (necesita créditos Anthropic):
    ```bash
    python3 generate_content.py --niche rossacuore --month 2026-10
    python3 generate_content.py --to-sheet --month 2026-10   # sube a la hoja de Rossacuore*
    ```
    *(ojo: `--to-sheet` usa SHEET_ID; para la hoja de Rossacuore hay que pasar su ID —
    pendiente menor: exponer `--client` también en `--to-sheet`.)*
11. **Fotos:** Rossacuore usa SUS fotos → pegar la URL pública de cada foto en la columna
    `asset_path` de la hoja (las fotos deben estar hospedadas; podemos usar el mismo
    repo/jsDelivr o un Drive público).
12. Verónica/Christian **aprueban** en la hoja (checkbox), y publicamos:
    ```bash
    python3 publish.py --client rossacuore --sheet
    ```

## Estado del sistema (ya listo)
- `publish.py --client rossacuore` ✅ (idioma español automático).
- `comments.py --niche rossacuore` ✅ (plantillas en español; requiere su token con
  `instagram_manage_comments`).
- Persona, pilares, fechas fuertes y rituales de Rossacuore ✅.
