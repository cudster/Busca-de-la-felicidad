# Epic.Plane — Sistema de monetización automatizado

Reactivación de la cuenta de Instagram **Epic.Plane** (nicho aviación, ~90k
seguidores) como fuente de ingreso, automatizando ~80% con IA. Contexto completo
y hoja de ruta en [`CLAUDE.md`](CLAUDE.md).

## Estado

| Módulo | Qué hace | Estado |
|--------|----------|--------|
| **1. Generador de contenido** | Arma el calendario mensual (20 posts) con la API de Anthropic | ✅ **Listo** |
| 2. Publicador automático | Publica a Instagram vía Graph API | Pendiente (Sesión 2) |
| 3. Pipeline de visuales | Organiza assets y prompts de imagen/video | Pendiente (Sesión 3) |
| 4. Newsletter (Beehiiv) | Draft semanal de newsletter | Pendiente (Sesión 4) |
| 5. Reporte de métricas | Revisión semanal desde la Graph API | Pendiente (Sesión 4) |

---

## Módulo 1 — Generador de contenido

Genera el calendario mensual de posts (hook, caption en inglés y español,
hashtags, tipo de post, CTA de afiliado y prompt visual), respetando las reglas
de voz, la distribución de pilares (40% asombro técnico / 30% spotting / 20%
historias / 10% camino del piloto) y horarios optimizados para audiencia US/UK.

### Instalación (una sola vez)

```bash
pip install -r requirements.txt
cp .env.example .env      # y pega tu API key real en .env
```

Tu API key la sacas en <https://console.anthropic.com/> → Settings → API Keys.
(Alternativa: `export ANTHROPIC_API_KEY=sk-ant-...` en tu terminal).

### Uso

```bash
python3 generate_content.py                 # genera el mes actual
python3 generate_content.py --month 2026-09 # genera un mes específico
python3 generate_content.py --force         # regenera aunque el mes ya exista
python3 generate_content.py --month 2026-08 --export-only  # re-exporta el .md desde el .json
```

### Qué produce

- `calendar/YYYY-MM.json` — el calendario en formato estructurado (schema del
  CLAUDE.md). **Este es el archivo fuente que editas.**
- `content/YYYY-MM.md` — versión legible para revisar rápido en el celular.

### Flujo de revisión y aprobación

1. Corre el generador.
2. Abre `content/YYYY-MM.md` y revisa los 20 posts.
3. Edita lo que quieras directo en `calendar/YYYY-MM.json`.
4. Marca `"approved": true` en cada post que apruebes.
5. (Opcional) Corre con `--export-only` para actualizar el `.md` con tus cambios.

Los posts con `"approved": true` quedan listos para que el Módulo 2 (publicador)
los tome. Por eso el generador **no sobrescribe** un mes ya existente salvo que
uses `--force`: así no pierdes tus ediciones ni aprobaciones.

### Nota de costo

Usa `claude-sonnet-4-6` (definido en el CLAUDE.md), la opción costo-eficiente
para este volumen. Generar un mes completo (20 posts) cuesta centavos de dólar.
