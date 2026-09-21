# pg_gateway promo (video-shotcraft)

~**155s** cinematic promo: **config first → live CRUD curls**, Russian selling copy,
built with **video-shotcraft**.

## Shot list
| # | Beat (RU) | Card / style |
|---|-----------|----------------|
| 1 | Недели на бэкенд — ради одного API? | title |
| 2 | Быстрый API к PostgreSQL из YAML | title |
| 3 | DN — это грант ТУЗ | `spotlight-hero-card` |
| 4 | Каждому ТУЗ — только свои эндпоинты | title |
| 5 | Request / grant grid | `deck-deal-flyin` |
| 6 | Меньше утечек лишних данных | title |
| 7 | Response ledger | `row-embed` |
| 8 | Без X-Roles и X-Tenant-Id | title |
| 9 | Сначала конфиг — потом API | title |
| 10 | YAML users-admin + resources.users | config-reveal |
| 11 | Тот же YAML. Живые curl. | title |
| 12 | list→get→create→patch→filter→upsert→delete→404→403 | curl-proof |
| 13 | Конфиг вместо недель разработки | title |
| 14 | Подключите ТУЗ за часы — не за недели | outro |

## Config + curls
- **Config**: `accounts.example.yaml` (`CN=users-admin` → users CRUD grants) then `config.yaml` users ops / soft_delete / upsert_keys
- **Curls**: 200 list, 200 get, 201 create, 200 patch, 200 filter, 200 upsert, 200 delete, 404 after soft-delete, 403 deny (`orders-reader`)

Design: `docs/design-spec.md`  
Fixtures: `fixtures/users_crud_responses.json`, `fixtures/config_snippets.json`  
Output: `out/promo.mp4` (4656f @ 30fps ≈ 155s)

## Preview
```bash
cd promo
open out/promo.mp4
npx remotion studio src/index.ts
```

## Capture + render
```bash
cd promo
npm run capture   # Playwright textures
npm run render    # → out/promo.mp4
```
