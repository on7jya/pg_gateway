# pg_gateway promo — дизайн-спека (автономное свободное создание)

## Режим
Автономное свободное создание с зафиксированными пользователем ограничениями по кадрам:
`deck-deal-flyin`, `row-embed`, крупный план продукта в духе `spotlight-hero-card`.

## Бриф продукта
- **Продукт**: pg_gateway — конфигурируемый FastAPI API Gateway для PostgreSQL
- **Аудитория**: backend / platform-инженеры
- **Ключевое предложение**: YAML-конфиг → динамические маршруты + ACL + OpenAPI; без жёстко заданной схемы БД
- **Данные**: вымышленное демо-CRM (users/orders/products); без секретов
- **Формат**: 1920×1080 @ 30fps, только SFX (без BGM)
- **Язык онскрина**: English

## Визуальное направление
- **Пресет**: professional / enterprise («专业信赖») с чёткой инженерной энергией
- **Токены**
  - bg: `#0b1220` / surface: `#121a2b` / paper panel: `#f4f7fb`
  - ink: `#0f172a` / muted: `#64748b`
  - accent: `#0d9488` (teal) — не purple
  - font UI: `"IBM Plex Sans", "Segoe UI", sans-serif`
  - font mono: `"IBM Plex Mono", ui-monospace, monospace`
- **Motion-токены**: основная длительность ~21f, ease `bezier(0,0,0.2,1)`; приземления могут overshoot, если метафора требует bounce (побеждает юриспруденция shot-card)

## Карта feature → shot
| Фича | Кадр | Почему |
|------|------|--------|
| Ресурс как атомарная единица | spotlight-hero-card | Одиночный hero, крупный план продукта |
| Конфиг разворачивается в множество маршрутов | deck-deal-flyin | Плотность / непрерывный приток |
| Поля схемы встраиваются в API-поверхность | row-embed | Структурированные данные вырастают в страницу |

## Раскадровка (кадры @30fps)
| # | from | dur | content | card |
|---|------|-----|---------|------|
| 1 | 0 | 139 | Spotlight карточки ресурса + float + beam | spotlight-hero-card |
| 2 | 139 | 40 | Title breath: “YAML in. Routes out.” | title |
| 3 | 179 | 113 | Раздача колоды в сетку ресурсов | deck-deal-flyin |
| 4 | 292 | 36 | Title: “Fields land in the API.” | title |
| 5 | 328 | 68 | Row embed на detail ресурса | row-embed |
| 6 | 396 | 54 | Brand lockup hold | outro |
| **Итого** | | **450f / 15.0s** | | |

## Acceptance-кадры
- Spotlight: 48, 90, 130
- Deck: 20, 70, 110
- Rows: 24, 50, 66
