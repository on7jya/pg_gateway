# pg_gateway promo — design spec (autonomous free creation)

## Mode
Autonomous free creation with locked shot constraints from the user:
`deck-deal-flyin`, `row-embed`, product close-up inspired by `spotlight-hero-card`.

## Product brief
- **Product**: pg_gateway — config-driven FastAPI API Gateway for PostgreSQL
- **Audience**: backend / platform engineers
- **Core sell**: YAML config → dynamic routes + ACL + OpenAPI; no hardcoded DB schema
- **Data**: fictional demo CRM (users/orders/products); no secrets
- **Format**: 1920×1080 @ 30fps, SFX-only (no BGM)
- **Language**: English

## Visual direction
- **Preset**: professional / enterprise (“专业信赖”) with crisp engineer energy
- **Tokens**
  - bg: `#0b1220` / surface: `#121a2b` / paper panel: `#f4f7fb`
  - ink: `#0f172a` / muted: `#64748b`
  - accent: `#0d9488` (teal) — not purple
  - font UI: `"IBM Plex Sans", "Segoe UI", sans-serif`
  - font mono: `"IBM Plex Mono", ui-monospace, monospace`
- **Motion tokens**: main duration ~21f, ease `bezier(0,0,0.2,1)`; landings may overshoot when metaphor requires bounce (shot-card jurisprudence wins)

## Feature → shot map
| Feature | Shot | Why |
|---------|------|-----|
| Resource as atomic unit | spotlight-hero-card | Single-hero product close-up |
| Config expands into many routes | deck-deal-flyin | Density / continuous inflow |
| Schema fields embed into API surface | row-embed | Structured data growing into page |

## Storyboard (frames @30fps)
| # | from | dur | content | card |
|---|------|-----|---------|------|
| 1 | 0 | 139 | Hero resource card spotlight + float + beam | spotlight-hero-card |
| 2 | 139 | 40 | Title breath: “YAML in. Routes out.” | title |
| 3 | 179 | 113 | Deck deal into resource grid | deck-deal-flyin |
| 4 | 292 | 36 | Title: “Fields land in the API.” | title |
| 5 | 328 | 68 | Row embed on resource detail | row-embed |
| 6 | 396 | 54 | Brand lockup hold | outro |
| **Total** | | **450f / 15.0s** | | |

## Acceptance frames
- Spotlight: 48, 90, 130
- Deck: 20, 70, 110
- Rows: 24, 50, 66
