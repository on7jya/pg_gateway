import {chromium} from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const outDir = path.join(root, 'public/textures/live');
const pagesDir = path.join(root, 'capture-pages');

async function shotFull(page, file, height) {
  await page.setViewportSize({width: 1920, height: 1080});
  await page.evaluate((h) => {
    document.documentElement.style.height = h + 'px';
    document.body.style.height = h + 'px';
  }, height);
  await page.waitForTimeout(400);
  await page.screenshot({
    path: path.join(outDir, file),
    fullPage: true,
    type: 'png',
  });
}

async function main() {
  fs.mkdirSync(outDir, {recursive: true});
  const browser = await chromium.launch();
  const page = await browser.newPage({deviceScaleFactor: 2});

  // Resources grid
  await page.goto('file://' + path.join(pagesDir, 'resources.html'));
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(600);
  await shotFull(page, 'projects-full.png', 1746);

  // Empty backplate: hide cards
  await page.evaluate(() => {
    document.querySelectorAll('.card').forEach((el) => {
      el.style.visibility = 'hidden';
    });
  });
  await shotFull(page, 'projects-empty.png', 1746);

  // Restore and cut cards
  await page.goto('file://' + path.join(pagesDir, 'resources.html'));
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(400);
  const cards = await page.$$('.card');
  for (let i = 0; i < cards.length; i++) {
    await cards[i].screenshot({
      path: path.join(outDir, `card${i + 1}.png`),
      type: 'png',
    });
  }
  // hires hero = card 4 (ACL) — center-ish for spotlight
  await cards[3].screenshot({
    path: path.join(outDir, 'card4-hires.png'),
    type: 'png',
  });

  // Detail page
  await page.goto('file://' + path.join(pagesDir, 'detail.html'));
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(600);
  await shotFull(page, 'detail-full.png', 1400);

  // Build layout.json matching shot demos expectations
  const resourcesLayout = await page.goto('file://' + path.join(pagesDir, 'resources.html')).then(async () => {
    await page.waitForTimeout(200);
    return page.evaluate(() => {
      const cards = [...document.querySelectorAll('.card')].map((el, idx) => {
        const r = el.getBoundingClientRect();
        return {
          file: `card${idx + 1}.png`,
          x: r.left,
          y: r.top,
          w: r.width,
          h: r.height,
          title: el.querySelector('h3')?.textContent?.trim() || '',
        };
      });
      return {
        pageW: 1920,
        projects: {
          pageH: 1746,
          header: {x: 0, y: 0, w: 1920, h: 61},
          cards,
        },
      };
    });
  });

  await page.goto('file://' + path.join(pagesDir, 'detail.html'));
  await page.waitForTimeout(200);
  const detail = await page.evaluate(() => {
    const rows = [...document.querySelectorAll('.row')].map((el) => {
      const r = el.getBoundingClientRect();
      return {x: r.left, y: r.top, w: r.width, h: r.height};
    });
    return {pageH: 1400, rows};
  });

  const layout = {...resourcesLayout, detail};
  fs.writeFileSync(path.join(outDir, 'live-layout.json'), JSON.stringify(layout, null, 1));
  fs.writeFileSync(path.join(root, 'src/lib/live-layout.json'), JSON.stringify(layout, null, 1));
  console.log('Captured textures + layout', {cards: layout.projects.cards.length, rows: detail.rows.length});
  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
