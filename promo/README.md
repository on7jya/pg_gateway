# pg_gateway promo (video-shotcraft)

15-секундный кинематографичный промо-ролик, собранный скиллом **video-shotcraft**.

## Кадры
| Кадр | Card |
|------|------|
| Крупный план продукта | `spotlight-hero-card` |
| Приток сетки ресурсов | `deck-deal-flyin` |
| Встраивание строк полей | `row-embed` |

Дизайн-заметки: `docs/design-spec.md`

## Просмотр
```bash
open out/promo.mp4
# или
npx remotion studio src/index.ts
```

## Перерендер
```bash
npm run capture   # Playwright-текстуры из capture-pages/
npm run render    # → out/promo.mp4
```

## QA-кадры
- `out/qa/spotlight-f90.png`
- `out/qa/deck-f70.png`
- `out/qa/rows-f50.png`
