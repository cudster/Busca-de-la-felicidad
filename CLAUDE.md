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
