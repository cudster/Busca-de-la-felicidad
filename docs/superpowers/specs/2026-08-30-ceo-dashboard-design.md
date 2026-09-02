# Diseño — CEO Dashboard (Agencia, Fase 1)

**Fecha:** 2026-08-30
**Estado:** Aprobado para escribir plan de implementación
**Proyecto padre:** convertir el sistema en una **agencia de marketing multi-cliente y multi-canal**, con un cockpit de decisiones para el CEO. Este spec cubre **solo la Fase 1: el CEO Dashboard**.

---

## 1. Contexto y visión

Estamos evolucionando el sistema (Epic.Plane + Al Día) hacia un **sistema operativo de agencia**: gestionar varias marcas a la vez, en varios canales (Instagram, YouTube, LinkedIn, TikTok), con un **cockpit web** donde el CEO ve todo y toma decisiones.

**Descomposición en fases** (cada una con su propio spec→plan→build):

| Fase | Pieza | Estado |
|---|---|---|
| **1** | **CEO Dashboard** (cockpit multi-cliente) | **Este spec** |
| 2 | Motor YouTube (guión → producción IA → subida) | Futuro |
| 3 | LinkedIn + TikTok (formatos/guiones + publicación según API) | Futuro |
| 4 | Multi-cliente completo (onboarding, roles, briefs por cliente) | Futuro |

**Realidad de alcance (honesta):** LinkedIn/TikTok tienen APIs restringidas; la subida automática a YouTube requiere OAuth+cuotas+revisión; el video IA cuesta. Esas son las fases 2-3, no la 1. La Fase 1 da valor y decisiones YA con lo que existe (Instagram) y deja la estructura para enchufar el resto.

**Objetivo Fase 1:** una página web privada, multi-cliente, que se regenera sola cada semana y le dice al CEO, por cliente: qué pasó, cómo van las métricas, y **qué decisiones tomar** (contenido, estrategia por canal, presupuesto, clientes).

**Criterio de éxito:** el CEO abre un link, entiende el estado de todos sus clientes en <30 segundos, y ve una lista clara de decisiones pendientes de la semana. Empieza cubriendo Epic.Plane (IG) y se puede sumar un cliente nuevo creando un archivo de config.

---

## 2. Alcance

**Dentro (Fase 1):**
- Modelo de datos multi-cliente: `clients/<slug>/config.json`.
- `dashboard.py`: por cada cliente, junta métricas de sus canales (IG por Graph API), calcula tendencia + alertas + salud, y genera `dashboard.html`.
- Reglas de decisión/alertas (las 4 categorías del CEO).
- Plantilla HTML del cockpit (oscuro, escaneable, lenguaje "Al Día").
- Workflow de refresco (GitHub Actions, semanal) + entrega en link privado.
- Semilla: cliente `epic-plane` (Instagram real). Placeholders "próximamente" para YouTube/LinkedIn/TikTok.

**Fuera (fases siguientes):**
- Motores de contenido de YouTube/LinkedIn/TikTok.
- Subida automática a cualquier canal.
- Video con IA.
- Autenticación/login real del dashboard (Fase 1 usa link privado por URL no-adivinable; auth es hardening posterior).
- Onboarding automático de clientes.

**No tocar:** `generate_content.py`, `media.py`, `publish.py`, `sheets.py`, `daily_email.py`, `curate.py` ni sus workflows (el dashboard **lee** datos; no cambia el pipeline).

---

## 3. Arquitectura

```
clients/<slug>/config.json   ← cada cuenta gestionada (multi-cliente)
        │
        ▼
   dashboard.py
     ├── por cliente y canal, junta métricas (IG: Graph API; otros: "próximamente")
     ├── calcula tendencia (vs período anterior), salud 🟢🟡🔴, y alertas
     ├── arma las 4 secciones de decisiones
     └── renderiza dashboard.html (estático, autocontenido)
        │
        ▼
  GitHub Actions (lunes) → publica dashboard.html en link privado
```

Sin backend ni base de datos: script + HTML estático + hosting, refrescado por cron (mismo patrón que `daily_email.py`).

---

## 4. Componentes (detalle)

### 4.1 Config de clientes — `clients/<slug>/config.json`
Un archivo por cuenta gestionada. Esquema:
```json
{
  "slug": "epic-plane",
  "name": "Epic.Plane",
  "niche": "aviación",
  "channels": {
    "instagram": { "enabled": true, "handle": "epic.plane", "ig_user_id_env": "IG_USER_ID", "token_env": "META_PAGE_TOKEN" },
    "youtube":  { "enabled": false },
    "linkedin": { "enabled": false },
    "tiktok":   { "enabled": false }
  },
  "goals": { "primary": "reactivar alcance y engagement" },
  "budget_notes": "sin pauta por ahora"
}
```
Para Epic.Plane las credenciales de IG se referencian desde `.env` (ya existen). Multi-cliente futuro: cada cliente puede apuntar a sus propias variables/credenciales.

### 4.2 Motor de datos — `dashboard.py`
- Descubre clientes leyendo `clients/*/config.json`.
- Para cada canal `enabled`, junta métricas. **Instagram (Fase 1):** reutiliza la lógica de la Graph API ya usada en `daily_email.py`/`metrics.py` — followers, y de los posts recientes: likes, comentarios, alcance, guardados. Calcula promedios del período (últimos 7 días) y del período anterior (7 días previos) para la **tendencia**.
- Canales no habilitados → tarjeta "próximamente".
- Lee estado de contenido desde la Google Sheet vía `sheets.py` (posts sin aprobar, próximos a publicar, publicados esta semana) — para la sección de decisiones de contenido.
- Devuelve una estructura por cliente lista para renderizar.

Firmas clave:
- `load_clients(base=ROOT) -> list[dict]` — lee `clients/*/config.json`.
- `instagram_snapshot(cfg, env) -> dict` — followers, métricas del período y del anterior, top post. `None`/vacío si falta permiso o datos.
- `content_status(slug) -> dict` — de la Sheet: pendientes de aprobar, próximos, publicados esta semana. (Solo para el cliente cuyo pipeline vive en la Sheet; otros → vacío.)
- `compute_health(snapshot) -> str` — `"green" | "yellow" | "red"`.
- `build_decisions(cfg, snapshot, content) -> dict` — arma las 4 secciones.
- `render_html(clients_data) -> str` — genera el dashboard.
- `main()` — junta todo y escribe `dashboard.html`.

### 4.3 Reglas de salud y decisiones
**Salud (semáforo):**
- 🟢 verde: alcance sube vs período anterior **y** hay comentarios.
- 🟡 amarillo: alcance plano (±10%) o comentarios en 0.
- 🔴 rojo: alcance baja **o** seguidores bajan de forma sostenida.

**Las 4 secciones de decisión (por cliente):**
1. **Contenido:** de la Sheet → "N posts sin aprobar", "próximo publica el <fecha>", "publicados esta semana: N". Acción sugerida si hay pendientes.
2. **Estrategia por canal:** texto-recomendación derivado de métricas (ej. alcance plano ≥3 semanas → "prioriza reels + audio en tendencia"; 0 comentarios → "gancho más directo").
3. **Presupuesto:** si hay un post que rindió muy por sobre el promedio → "candidato a boost"; si no hay datos/pauta → "sin acción".
4. **Cliente:** salud + una nota de riesgo (ej. "🔴 alcance plano 3 semanas — conversar rumbo").

Las reglas son deterministas y simples (умbrales), no IA — confiables y explicables.

### 4.4 Plantilla HTML — cockpit
- Oscuro, legible, lenguaje visual "Al Día" (mismos tokens de color/tipografía).
- **Arriba:** barra de resumen — cada cliente como chip con su semáforo, y un contador de "decisiones pendientes" total.
- **Por cliente:** tarjeta con nombre + salud; fila de canales (IG con métricas + tendencia con flecha ↑/↓/→; otros "próximamente"); y el bloque **Decisiones de la semana** con las 4 secciones.
- Números redondeados; tendencia con signo y %. Responsive (se ve en el celular).
- Autocontenido (sin llamadas externas salvo Google Fonts).

### 4.5 Refresco y entrega
- Workflow `.github/workflows/dashboard.yml`: cron semanal (lunes 12:00 UTC) + manual. Instala deps, corre `dashboard.py`, publica `dashboard.html`.
- **Entrega en link privado (MVP):** desplegar `dashboard.html` en un host estático con **URL no-adivinable** (ej. Netlify). Además, `daily_email.py`/un correo semanal puede enlazarlo. Autenticación real = hardening de fase posterior.

---

## 5. Flujo de datos (una corrida)
1. `dashboard.py` lee `clients/*/config.json`.
2. Por cliente: `instagram_snapshot` (Graph API) + `content_status` (Sheet).
3. `compute_health` + `build_decisions`.
4. `render_html` → `dashboard.html`.
5. Workflow publica el HTML en el link privado.

---

## 6. Riesgos y mitigaciones
| Riesgo | Mitigación |
|---|---|
| "Privado" real es difícil en hosting estático gratis | MVP: URL no-adivinable; auth (Cloudflare Access / password) en fase posterior |
| Permiso de insights falla para un cliente | El snapshot degrada a N/D (como ya hace daily_email); la tarjeta lo indica |
| Multi-cliente con credenciales por cliente | Fase 1 usa `.env` para Epic.Plane; el esquema ya prevé refs por cliente para escalar |
| Reglas de decisión demasiado simples | Son explícitas y ajustables; se refinan con uso; mejor simple y confiable que IA opaca |

---

## 7. Entregables Fase 1
1. `clients/epic-plane/config.json` (+ esquema documentado).
2. `dashboard.py` (carga clientes, snapshot IG, estado de contenido, salud, decisiones, render).
3. Plantilla HTML del cockpit.
4. `.github/workflows/dashboard.yml` (refresco semanal + manual).
5. `dashboard.html` generado y desplegado en link privado.
6. Tests de las funciones puras (salud, decisiones, carga de clientes).
