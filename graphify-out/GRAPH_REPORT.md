# Graph Report - Busca de la felicidad  (2026-09-08)

> **Nota:** se purgaron 10 nodos alucinados (contenido médico/paliativo inexistente en el repo,
> generados al extraer `review_deck.html`). Ese archivo queda excluido de futuras corridas.

## Corpus Check
- 57 files · ~79,161 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 354 nodes · 499 edges · 53 communities (31 shown, 19 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 18 edges (avg confidence: 0.83)
- Token cost: 835,799 input · 19,699 output

## Community Hubs (Navigation)
- CEO Dashboard
- Content Generation Engine
- Instagram Publishing
- Media Curation Pipeline
- Google Sheets Layer
- YouTube Script Generation
- Fan Expert Engine (Soul)
- Assets Pipeline
- GitHub Actions Workflows
- YouTube Video Production
- News Curation (RSS)
- Daily Email Report
- Weekly Metrics Report
- Aviation Content & Plans
- Meta API Setup
- YouTube Upload (OAuth)
- Community Repost Engine
- Jet Engines & Airframes
- Review Deck (Tinder)
- Aerodynamics & Atmosphere
- C-17 Antarctica Mission
- Aviation History Facts
- Jumbo & Supersonic Jets
- Gimli Glider Incident
- Airbus A220
- Emirates A380
- Pilot Certification
- Flight Aerodynamics
- POV Car Channel
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51

## God Nodes (most connected - your core abstractions)
1. `main()` - 13 edges
2. `publish_post()` - 10 edges
3. `main()` - 9 edges
4. `main()` - 9 edges
5. `get_worksheet()` - 8 edges
6. `cmd_link()` - 7 edges
7. `media_for_post()` - 7 edges
8. `produce_video()` - 7 edges
9. `main()` - 6 edges
10. `build_decisions()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `upload()` --calls--> `build()`  [INFERRED]
  youtube_upload.py → daily_email.py
- `test_load_clients_missing_returns_empty()` --calls--> `load_clients()`  [EXTRACTED]
  tests/test_dashboard.py → dashboard.py
- `test_load_clients_reads_configs()` --calls--> `load_clients()`  [EXTRACTED]
  tests/test_dashboard.py → dashboard.py
- `test_build_decisions_declining_reach_alerts()` --calls--> `build_decisions()`  [EXTRACTED]
  tests/test_dashboard.py → dashboard.py
- `test_build_decisions_has_four_sections()` --calls--> `build_decisions()`  [EXTRACTED]
  tests/test_dashboard.py → dashboard.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Aviation Content Series** — review_deck_2026_09_p02, review_deck_2026_09_p03, review_deck_2026_09_p04 [EXTRACTED 0.90]
- **Aviation Technical History and Regulation** — review_deck_concorde_fuselage, review_deck_atp_requirement, review_deck_colgan_air_accident [INFERRED 0.80]
- **Antarctic Mission Interruption** — review_deck_html_c17_globemaster, review_deck_html_winfly, review_deck_html_russian_missile_alert [EXTRACTED 0.90]
- **Semantic Extraction Protocol** — review_deck_html_actor, review_deck_html_acted_upon, review_deck_html_graph_rules [EXTRACTED 0.90]
- **Aviation Design History** — review_deck_boeing_747, review_deck_sst, review_deck_cockpit_placement [EXTRACTED 0.90]
- **Aviation Knowledge Deck** — review_deck_html_2026_09_p08, review_deck_html_2026_09_p09, review_deck_html_aviation_science [EXTRACTED 0.85]
- **Happiness Search Framework** — review_deck_happiness_concept, review_deck_social_dynamics, review_deck_emotional_intelligence, review_deck_behavioral_patterns [INFERRED 0.80]
- **Aviation Engineering Context** — review_deck_html_ge90_115b, review_deck_html_boeing_777, review_deck_html_boeing_737, review_deck_html_fan_blades [EXTRACTED 0.95]
- **Aviation Social Media Deck** — review_deck_2026_09_p11, review_deck_2026_09_p12, review_deck_2026_09_p13 [EXTRACTED 0.90]
- **Social Media Content Structure** — review_deck_jetblue_incident, review_deck_aviation_security [EXTRACTED 0.90]
- **Aviation Technical & Engineering Concepts** — review_deck_ground_effect, review_deck_wing_flex, review_deck_flare [EXTRACTED 0.90]
- **Content Automation Pipeline** — github_workflows_publish_yml, github_workflows_daily_report_yml, github_workflows_dashboard_yml, google_sheet [EXTRACTED 0.90]
- **Community Manager Automatizado Flow** — docs_motor_fan_experto_plan, persona_epic_plane, knowledge_epic_plane_facts, content_2026_09_p01 [EXTRACTED 0.95]
- **Agency Cockpit System** — docs_ceo_dashboard_plan, docs_motor_fan_experto_plan, youtube_autos_pov_persona [EXTRACTED 0.90]

## Communities (53 total, 19 thin omitted)

### Community 0 - "CEO Dashboard"
Cohesion: 0.11
Nodes (31): build_decisions(), _client_card(), compute_health(), content_status(), _fmt(), _graph(), instagram_snapshot(), load_clients() (+23 more)

### Community 1 - "Content Generation Engine"
Cohesion: 0.10
Nodes (31): Exception, build_schedule(), build_user_prompt(), _explain_api_error(), _extension_for_type(), generate_creative(), _load_dotenv(), load_occasions() (+23 more)

### Community 2 - "Instagram Publishing"
Cohesion: 0.14
Nodes (25): build_caption(), build_caption_row(), cmd_check(), cmd_post_test(), cmd_run(), cmd_run_sheet(), create_carousel_container(), create_image_container() (+17 more)

### Community 3 - "Media Curation Pipeline"
Cohesion: 0.17
Nodes (18): commons_photo(), crop_45(), derive_query(), derive_wiki(), _get(), is_aviation(), load_key(), main() (+10 more)

### Community 4 - "Google Sheets Layer"
Cohesion: 0.15
Nodes (19): _apply_formatting(), batch_set_media(), _bool_str(), _credentials(), _env(), get_worksheet(), _is_true(), mark_published() (+11 more)

### Community 5 - "YouTube Script Generation"
Cohesion: 0.20
Nodes (17): test_build_month_mix_and_ids(), test_load_channel_missing_raises(), test_load_channel_reads_config(), test_merge_keeps_skeleton_and_creative(), build_month(), build_prompt(), generate(), load_channel() (+9 more)

### Community 6 - "Fan Expert Engine (Soul)"
Cohesion: 0.20
Nodes (15): assign_sources(), load_facts(), load_news(), load_persona(), Path, Motor Fan Experto: carga la persona, los hechos y las noticias del nicho, y…, test_assign_sources_exhausted_facts_gives_none(), test_assign_sources_uses_fact_and_news() (+7 more)

### Community 7 - "Assets Pipeline"
Cohesion: 0.32
Nodes (13): cmd_link(), cmd_prompts(), cmd_status(), expected_names(), find_assets(), load_calendar(), load_env(), main() (+5 more)

### Community 8 - "GitHub Actions Workflows"
- **11 nodes**
- Members: Aviation Security and Operations, CEO Dashboard Workflow, Content Google Sheet, Dashboard Generation Script, Instagram Publish Workflow, JetBlue Stowaway Incident, Medical and Clinical Knowledge, Post P20: Miracle on the Hudson, Publishing Script, Review Deck: Busca de la felicidad, Symptom Management

### Community 9 - "YouTube Video Production"
Cohesion: 0.35
Nodes (11): assemble(), audio_duration(), _env(), load_plan(), main(), pexels_clips(), produce_video(), Path (+3 more)

### Community 10 - "News Curation (RSS)"
Cohesion: 0.29
Nodes (9): fetch_source(), main(), parse_rss(), Path, Trae noticias del nicho por RSS y guarda una lista corta 'reaccionable' para…, select_reactionable(), write_news(), test_parse_rss_extracts_items() (+1 more)

### Community 11 - "Daily Email Report"
Cohesion: 0.33
Nodes (10): build(), cfg(), g(), insights(), main(), Epic.Plane — Correo diario con el resultado del último post + feedback. Trae de…, Elige una foto vertical de aviación distinta cada día (Pexels) + una frase para…, send() (+2 more)

### Community 12 - "Weekly Metrics Report"
Cohesion: 0.33
Nodes (9): env(), g(), load_pillar_map(), main(), media_insights(), Epic.Plane — Módulo 5: Reporte de métricas semanal. Baja los insights de la…, Alcance/guardados/compartidos de un post. Devuelve dict, o None si falta el…, Mapea el inicio del caption -> pilar, usando el calendario local. (+1 more)

### Community 13 - "Aviation Content & Plans"
Cohesion: 0.25
Nodes (9): Antonov An-225 — The One & Only, SR-71 Built With Enemy Metal, Concorde: The Jet That Grew Mid-Flight, GE90-115B — The Engine Bigger Than a 737, Gimli Glider — Fuel, Physics & a Drag Strip, CEO Dashboard Implementation Plan, Motor Fan Experto Implementation Plan, Aviation Knowledge Base (+1 more)

### Community 14 - "Meta API Setup"
Cohesion: 0.39
Nodes (7): graph_get(), load_env(), main(), mask(), Epic.Plane — Fase C: obtención de token de larga duración + IDs de Instagram.…, Actualiza o agrega claves en el .env, preservando el resto., upsert_env()

### Community 15 - "YouTube Upload (OAuth)"
Cohesion: 0.57
Nodes (7): _credentials(), do_auth(), load_meta(), main(), _need(), Fase 2c: sube un video a YouTube (Data API v3), con los metadatos del plan.…, upload()

### Community 16 - "Community Repost Engine"
Cohesion: 0.48
Nodes (6): add_repost(), build_caption(), dm_template(), main(), _next_repost_id(), repost.py — Motor de repost con crédito (Epic.Plane / Al Día) La cuenta creció…

### Community 17 - "Jet Engines & Airframes"
- **5 nodes**
- Members: Boeing 737, Boeing 777, Busca de la felicidad, Fan Blades, GE90-115B Jet Engine

### Community 18 - "Review Deck (Tinder)"
Cohesion: 0.60
Nodes (4): fetch_posts(), main(), Epic.Plane — Generador del deck de revisión (estilo Tinder) para el celular.…, to_data_uri()

### Community 19 - "Aerodynamics & Atmosphere"
Cohesion: 0.40
Nodes (5): Contrails: Real Ice-Crystal Clouds, McDonnell Douglas MD-11 Aerodynamics, Aviation & Atmospheric Science, Contrails (Condensation Trails), McDonnell Douglas MD-11

### Community 20 - "C-17 Antarctica Mission"
Cohesion: 0.40
Nodes (5): Antarctica, C-17 Globemaster, Russian Missile Alert, United States Air Force (USAF), WINFLY

### Community 21 - "Aviation History Facts"
Cohesion: 0.50
Nodes (4): CIA Soviet Titanium & SR-71 Blackbird, Premium Economy Hidden Perks, Concorde Mach 2 Thermal Expansion, Aviation History and Facts

### Community 22 - "Jumbo & Supersonic Jets"
Cohesion: 0.50
Nodes (4): Airbus A380, Boeing 747, 747 Cockpit Placement, Supersonic Transport (SST)

### Community 23 - "Gimli Glider Incident"
Cohesion: 0.50
Nodes (4): Air Canada, Boeing 767, Gimli Glider, Metric Conversion Error

### Community 24 - "Airbus A220"
Cohesion: 0.67
Nodes (3): Airbus A220, Airbus Belfast Wing Facility, Airbus A220 Production Image (P12)

### Community 25 - "Emirates A380"
Cohesion: 0.67
Nodes (3): Airbus A380, Emirates Airline, Emirates A380 Fleet Image (P13)

### Community 27 - "Pilot Certification"
Cohesion: 0.67
Nodes (3): US Airline ATP 1,500 Hour Rule, Colgan Air Accident, Pilot Training and Certification

### Community 29 - "Flight Aerodynamics"
Cohesion: 0.67
Nodes (3): Flare, Ground Effect, Wing Flex

### Community 30 - "POV Car Channel"
Cohesion: 0.67
Nodes (3): Porsche Taycan Turbo S POV Long, Persona — POV Manejando, Porsche 911 POV Short

## Knowledge Gaps
- **65 isolated node(s):** `CIA Soviet Titanium & SR-71 Blackbird`, `Premium Economy Hidden Perks`, `Concorde Mach 2 Thermal Expansion`, `Concorde Fuselage Thermal Expansion`, `Colgan Air Accident` (+60 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 124 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `build()` connect `Daily Email Report` to `YouTube Upload (OAuth)`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Why does `upload()` connect `YouTube Upload (OAuth)` to `Daily Email Report`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **What connects `CIA Soviet Titanium & SR-71 Blackbird`, `Premium Economy Hidden Perks`, `Concorde Mach 2 Thermal Expansion` to the rest of the system?**
  _65 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `CEO Dashboard` be split into smaller, more focused modules?**
  _Cohesion score 0.11174242424242424 - nodes in this community are weakly interconnected._
- **Should `Content Generation Engine` be split into smaller, more focused modules?**
  _Cohesion score 0.10416666666666667 - nodes in this community are weakly interconnected._
- **Should `Instagram Publishing` be split into smaller, more focused modules?**
  _Cohesion score 0.14153846153846153 - nodes in this community are weakly interconnected._
