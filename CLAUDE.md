# Proyecto: Epic.Plane — Sistema de Monetización Automatizado

> Archivo de contexto para Claude Code. Colocar en la raíz de la carpeta del proyecto.
> Dueño: Felipe (Santiago, Chile). Responder siempre en español chileno.

## 1. Contexto y objetivo

- Cuenta de Instagram **Epic.Plane**: nicho aviación, ~90.000 seguidores reales, ~80% audiencia angloparlante, inactiva ~1 año. Se reactivará como fuente de ingreso.
- **Meta financiera**: primeros ingresos en 1-3 meses; USD $500-1.500/mes al mes 3; meta extendida CLP $2.000.000/mes (~USD $2.100) entre mes 6-9.
- **Restricciones**: presupuesto máx. USD $1.000 (ideal gastar <$100), 5-8 horas/semana del dueño, prioridades en orden: (1) baja inversión, (2) bajo riesgo, (3) ingreso pasivo, (4) velocidad.
- **Filosofía**: automatizar ~80% con IA. Lo único manual: engagement diario (30 min desde celular) y aprobación de contenido (15 min domingo).

## 2. Arquitectura del sistema (5 módulos)

### Módulo 1 — Generador de contenido (PRIORIDAD 1, construir primero)
- Script Python que llama a la API de Anthropic (modelo: claude-sonnet-4-6).
- Genera calendario mensual: 20 posts (4-5/semana) con hook, caption EN, caption ES, hashtags, tipo de post (imagen/carrusel/reel), y CTA de afiliado cuando corresponda.
- Output: `calendar/YYYY-MM.json` (schema en sección 4) + export legible a Markdown para revisión rápida.
- Flujo: generar → dueño revisa/edita → marca `approved: true` → queda listo para publicar.

### Módulo 2 — Publicador automático (PRIORIDAD 2)
- Instagram Graph API (Meta for Developers). Requisitos previos del dueño:
  1. Convertir Epic.Plane a cuenta profesional (Creator) si no lo está.
  2. Crear app en Meta for Developers, vincular página de Facebook, obtener token de larga duración.
- Script `publish.py`: lee el calendario aprobado, publica imagen/carrusel/reel a la hora programada.
- Scheduler: cron local o GitHub Actions (gratis). Alternativa de respaldo sin API: exportar cola a Meta Business Suite (programa gratis hasta 75 días).
- Horarios objetivo: optimizados para audiencia US/UK (mañana y tarde hora del este de EE.UU.).

### Módulo 3 — Pipeline de visuales
- Organiza assets en `assets/semana-N/`.
- Genera prompts visuales por post (para Higgsfield u otra herramienta de generación de imagen/video IA).
- Utilidades: redimensionar a formatos IG (1080x1350 feed, 1080x1920 reels/stories), plantillas de texto sobre imagen.

### Módulo 4 — Newsletter (Beehiiv)
- Script semanal: busca noticias de aviación de la semana (web search / RSS de fuentes como Aviation Week, Simple Flying, The Points Guy aviation), genera draft de newsletter en inglés con comentario editorial + links de afiliado.
- Output: Markdown listo para pegar en Beehiiv. El dueño aprueba y envía.
- Monetización: red de ads de Beehiiv + afiliados.

### Módulo 5 — Reporte semanal de métricas
- Script sábados: baja insights de la Graph API (alcance, saves, shares, follows netos, clicks al link en bio).
- Genera reporte estilo revisión semanal: qué funcionó / qué matar / qué duplicar, con recomendaciones accionables.
- Output: `reports/YYYY-WW.md`.

## 3. Monetización (en capas, por fase)

| Fase | Semanas | Fuente | Meta |
|------|---------|--------|------|
| 1 | 1-4 | Afiliado Pilot Institute en bio/stories (USD $25-50/venta) | Cuenta viva + primeros USD |
| 2 | 5-8 | + Newsletter Beehiiv + producto digital Payhip (guía o presets, USD $9-19) + brand deals (USD $100-400/post) | USD $300-800/mes |
| 3 | 9-12 | Duplicar lo que funciona, matar lo que no. Evaluar fase automotriz con datos | USD $800-1.500/mes |

## 4. Schema del calendario (JSON)

```json
{
  "month": "2026-08",
  "posts": [
    {
      "id": "2026-08-P01",
      "date": "2026-08-10",
      "time_utc": "13:00",
      "type": "reel",
      "topic": "Why the 747 cockpit sits on the second floor",
      "hook_en": "...",
      "caption_en": "...",
      "caption_es": "...",
      "hashtags": ["#aviation", "..."],
      "cta": "affiliate_pilot_institute | none | newsletter",
      "visual_prompt": "...",
      "asset_path": "assets/semana-1/p01.mp4",
      "approved": false,
      "published": false
    }
  ]
}
```

## 5. Prompt maestro de contenido (para el Módulo 1)

Pilares de contenido (rotar):
1. **Asombro técnico** (40%): datos increíbles de aviones, física de vuelo, ingeniería. Formato: carrusel educativo o reel con texto.
2. **Spotting / visual épico** (30%): fotos y videos impactantes de aviones. Formato: imagen o reel corto.
3. **Historias de aviación** (20%): incidentes famosos resueltos, historia de aerolíneas, récords. Formato: carrusel narrativo.
4. **Camino del piloto** (10%): cómo convertirse en piloto, costos, licencias. **Aquí va siempre el CTA de Pilot Institute.**

Reglas de voz: inglés nativo casual-experto, hooks de máximo 8 palabras, primera línea detiene el scroll, captions de 80-150 palabras, siempre una pregunta al final para comentarios, 8-12 hashtags mezclando volumen alto/medio/nicho.

## 6. Orden de construcción (sesiones con Claude Code)

1. **Sesión 1**: Módulo 1 completo (generador + schema + export Markdown). Probar generando el calendario del primer mes.
2. **Sesión 2**: Setup Meta API (guiar al dueño paso a paso en la creación de la app y tokens) + `publish.py` con post de prueba.
3. **Sesión 3**: Scheduler (GitHub Actions) + Módulo 3 (organización de assets).
4. **Sesión 4**: Módulo 5 (reporte de métricas) + Módulo 4 (newsletter).

## 7. Estilo de trabajo del dueño

- Prefiere delegar decisiones tácticas: Claude Code decide detalles técnicos directamente y avanza; pide validación solo en hitos.
- Iterativo y secuencial: cerrar cada módulo con un entregable funcionando antes de pasar al siguiente.
- Todo texto dirigido al dueño en español chileno; contenido para la audiencia en inglés (con versión ES).

## Estado actual

Última actualización: 2026-08-05.

### Construido y funcionando (Sesiones 1-3)

- **Módulo 1 — Generador** (`generate_content.py`): genera el calendario mensual de 20 posts vía API de Anthropic (`claude-sonnet-4-6`). Python arma el esqueleto determinístico (fechas Lun/Mar/Mié/Jue/Sáb, horarios 13:00 y 22:00 UTC, distribución de pilares 8/6/4/2, tipos, CTA afiliado en los 2 posts `pilot_path`); la IA rellena lo creativo (topic, hook, caption EN/ES, hashtags, visual_prompt). Escribe `calendar/YYYY-MM.json` + `content/YYYY-MM.md`. Comandos: `--month`, `--force`, `--export-only`, `--approve`/`--unapprove` (aceptan `P01`, `1`, id completo o `all`). Calendario de agosto 2026 generado y aprobado (20/20).
- **Módulo 2 — Publicador** (`publish.py`): Instagram Graph API (crea contenedor + `media_publish`, con polling de `status_code` hasta FINISHED). Soporta imagen/carrusel/reel. Modos: `--check` (valida sin publicar), `--post-test` (post real), `--run [--month] [--dry-run]` (publica aprobados+vencidos+no publicados, marca `published:true`). Probado con un post real en @epic.plane.
- **Módulo 3 — Assets** (`assets.py`): `prompts` (hoja de prompts visuales por post), `status`, `link` (empareja `assets/semana-N/pXX.*` → `media_url`/`media_urls` con URLs jsDelivr). Convención: imagen `pXX.jpg`, reel `pXX.mp4`, carrusel `pXX_1.jpg`…
- **Setup Meta** (`setup_meta.py`): intercambia token corto→durable y descubre IDs. Cuenta @epic.plane (IG_USER_ID 17841431987534624), token de página durable y IDs en `.env`.
- **Hosting + Scheduler**: repo público `cudster/Busca-de-la-felicidad`, assets servidos por jsDelivr. `.github/workflows/publish.yml` corre `publish.py --run` (cron 13:10/22:10 UTC + manual) y commitea de vuelta el calendario. Secrets `IG_USER_ID`/`META_PAGE_TOKEN` cargados; corrida manual verificada OK.
- `.env` protegido por `.gitignore`. `credentials.json` (Google) también en `.gitignore`.

### Capa de automatización — Google Sheets (ver `SETUP-AUTOMATIZACION.md`)

Aprobación desde el celular en una **Google Sheet** + publicación 24/7 en la nube, sobre la cuenta dedicada **epic.plane85@gmail.com**.

- **Sección 3 (Google Cloud + Sheet): ✅ lista.** Proyecto `epic-plane`, cuenta de servicio `epic-plane-bot`, `credentials.json` en la raíz (gitignored), APIs Sheets+Drive habilitadas. Hoja "Epic.plane Calendario" (pestaña `Calendar`) compartida con el bot como Editor. `SHEET_ID` en `.env`. Lectura y escritura verificadas.
- **Sección 5 (código): ✅ lista.** `sheets.py` (módulo compartido; credenciales de archivo en dev o env var `GOOGLE_CREDENTIALS` en la nube; pestaña case-insensitive). Generador: `--to-sheet` hace upsert por `id` sin pisar `approved`/`feedback`/`asset_path`, con casillas de verificación, encabezado congelado y formato condicional (verde=aprobado / amarillo=feedback sin aprobar). Publicador: `--sheet [--dry-run]` lee filas `approved=TRUE & published=FALSE & vencidas`, publica y marca `published`/`published_at`. Calendario de agosto subido a la hoja (20/20 aprobados migrados desde el JSON). Probado.
- **Sección 4 (GitHub Actions 24/7): pendiente.** Montar el publicador en la nube con Secrets `GOOGLE_CREDENTIALS`, `SHEET_ID`, `META_PAGE_TOKEN`, `IG_USER_ID`, corriendo `publish.py --sheet` por cron.

**Nota de diseño:** en la hoja, la columna `asset_path` debe contener la **URL pública** del asset (jsDelivr u otra). Felipe puede pegarla a mano, o la automatizamos con `assets.py` cuando existan los medios. El publicador lee esa URL de la hoja.

### Próximo paso

Felipe genera los medios reales (Higgsfield) → pone la URL pública en `asset_path` de la hoja (o los enlazamos con `assets.py`) → prueba de publicación real desde la hoja → montar el publicador 24/7 en GitHub Actions (sección 4, en la cuenta dedicada). Reconciliar: el hosting jsDelivr exige repo público; decidir repo del stack en la cuenta dedicada.
