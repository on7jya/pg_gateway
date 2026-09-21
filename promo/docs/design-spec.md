# pg_gateway promo — design spec (autonomous free creation)

## Mode
Autonomous free creation with user-fixed shot constraints:
`deck-deal-flyin`, `row-embed`, `spotlight-hero-card`, plus handcrafted
`config-reveal` and expanded `curl-proof` (CRUD theater).

## Product brief
- **Product**: pg_gateway — config-driven REST API in front of PostgreSQL
- **Audience**: backend / platform / security-minded engineering leads (RU market)
- **Core offer**: per-ТУЗ endpoint grants via certificate DN (`authz.mode: cert_dn`); field/operation ACL; config-first CRUD without custom backends
- **Demo arc**: show YAML **first** (`accounts.example.yaml` users-admin + `config.yaml` users ops) → then live curls for that grant shape
- **Data**: live Postgres via gateway (`promo/fixtures/users_crud_responses.json`); demo CRM names only; deny body from cert_dn ASGI (`orders-reader` → `/users` 403)
- **Format**: 1920×1080 @ 30fps, **~155s (4656f)** — quality over length
- **On-screen language**: **Russian** business/sales copy; product tokens / DN / HTTP codes kept literal

## Config shown on screen
1. **`accounts.example.yaml`** (from cert_dn overlay) — `CN=users-admin` grants on `users`:
   `list, get, create, update, patch, delete` + field ACL
2. **`config.yaml` · `resources.users`** — soft_delete, operations (incl. upsert/batch), filterable, upsert_keys

## Curl sequence (statuses)
| Beat | Method | Path | Status |
|------|--------|------|--------|
| list | GET | `/api/v1/users?limit=5` | **200** (alice, bob) |
| get | GET | `/api/v1/users/{alice}` | **200** |
| create | POST | `/api/v1/users` | **201** (Anna Promo) |
| patch | PATCH | `/api/v1/users/{id}` | **200** (name/status updated) |
| filter | GET | `/users?filter[email][eq]=…` | **200** |
| upsert | POST | `/api/v1/users/upsert` | **200** |
| delete | DELETE | `/api/v1/users/{id}` | **200** (soft-delete) |
| get_after_delete | GET | same id | **404** |
| deny | GET | `/api/v1/users` as `orders-reader` | **403** AUTHZ_DENIED |

Curl commands on screen use `X-Client-Cert-DN: CN=users-admin,…` to match the YAML grant story.
Success bodies recorded against live Postgres (gateway); deny captured from cert_dn overlay.

## Visual direction
- **Preset**: professional / enterprise with engineering energy
- **Tokens**: bg `#0b1220`, accent `#0d9488` (teal), ok `#10b981`, deny `#f43f5e`, warn `#f59e0b`
- **Fonts**: IBM Plex Sans / Mono

## Feature → shot map
| Feature | Shot |
|---------|------|
| Pain / solution | title cards |
| DN grant atom | spotlight-hero-card |
| Request density | deck-deal-flyin |
| Structured responses | row-embed |
| Config-first story | ConfigReveal (YAML theater) |
| CRUD proof | CurlProof (9 beats) |
| Close CTA | outro |

## Storyboard (@30fps · 4656f / 155.2s)
| # | from | dur | Beat | card |
|---|------|-----|------|------|
| 1 | 0 | 90 | Недели на бэкенд — ради одного API? | title |
| 2 | 90 | 84 | Быстрый API к PostgreSQL из YAML | title |
| 3 | 174 | 160 | DN — это грант ТУЗ | spotlight-hero-card |
| 4 | 334 | 84 | Каждому ТУЗ — только свои эндпоинты | title |
| 5 | 418 | 130 | Deck-deal grid | deck-deal-flyin |
| 6 | 548 | 84 | Меньше утечек лишних данных | title |
| 7 | 632 | 100 | Row-embed ledger | row-embed |
| 8 | 732 | 84 | Без X-Roles и X-Tenant-Id | title |
| 9 | 816 | 90 | Сначала конфиг — потом API | title |
| 10 | 906 | 420 | YAML: accounts users-admin → resources.users | config-reveal |
| 11 | 1326 | 90 | Тот же YAML. Живые curl. | title |
| 12 | 1416 | 2880 | CRUD theater (9×320f) | curl-proof |
| 13 | 4296 | 90 | Конфиг вместо недель разработки | title |
| 14 | 4386 | 270 | Outro CTA | outro |
| **Total** | | **4656f / 155.2s** | | |

## Fixtures
- `fixtures/accounts.example.yaml` — cert_dn overlay source
- `fixtures/config_snippets.json` — on-screen YAML excerpts
- `fixtures/users_crud_responses.json` — live CRUD + deny
- `fixtures/cert_dn_responses.json` — earlier cert_dn smoke (kept)

## Acceptance frames (absolute)
- Spotlight: 210, 300
- Config reveal: 950, 1150
- Curl create/patch/deny: 2100, 2700, 4000
- Outro: 4450
