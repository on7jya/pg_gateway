# pg_gateway promo (video-shotcraft)

15s cinematic promo built with the **video-shotcraft** skill.

## Shots
| Shot | Card |
|------|------|
| Product close-up | `spotlight-hero-card` |
| Resource grid inflow | `deck-deal-flyin` |
| Field rows embed | `row-embed` |

Design notes: `docs/design-spec.md`

## Play the film
```bash
open out/promo.mp4
# or
npx remotion studio src/index.ts
```

## Re-render
```bash
npm run capture   # Playwright textures from capture-pages/
npm run render    # → out/promo.mp4
```

## QA stills
- `out/qa/spotlight-f90.png`
- `out/qa/deck-f70.png`
- `out/qa/rows-f50.png`
