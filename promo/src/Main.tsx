import React from 'react';
import {AbsoluteFill, Audio, Sequence, staticFile} from 'remotion';
import {SpotlightHeroCard, SPOTLIGHT_HERO_CARD_DURATION} from './shots/SpotlightHeroCard';
import {DeckDealFlyin, DECK_DEAL_FLYIN_DURATION} from './shots/DeckDealFlyin';
import {RowEmbed, ROW_EMBED_DURATION} from './shots/RowEmbed';
import {TitleCard} from './shots/TitleCard';
import {ConfigReveal, CONFIG_REVEAL_DURATION} from './shots/ConfigReveal';
import {CurlProof, CURL_PROOF_DURATION, CURL_BEAT_LEN} from './shots/CurlProof';
import {Outro, OUTRO_DURATION} from './shots/Outro';

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

/**
 * Expanded demo @ 30fps (~154s / 4614f):
 * problem → solution → DN spotlight → deck/ACL → config YAML first →
 * live CRUD curls (list/get/create/patch/filter/upsert/delete/404/deny) → CTA
 */
const D = {
  problem: 90,
  solution: 84,
  spotlight: SPOTLIGHT_HERO_CARD_DURATION,
  titleDn: 84,
  deck: DECK_DEAL_FLYIN_DURATION,
  titleAcl: 84,
  rows: ROW_EMBED_DURATION,
  titleNoRoles: 84,
  titleConfigFirst: 90,
  configReveal: CONFIG_REVEAL_DURATION,
  titleThenCurls: 90,
  curlProof: CURL_PROOF_DURATION,
  titleClose: 90,
  outro: OUTRO_DURATION,
} as const;

function buildShots() {
  let from = 0;
  const shots: Record<string, {from: number; duration: number}> = {};
  for (const [k, duration] of Object.entries(D)) {
    shots[k] = {from, duration};
    from += duration;
  }
  return shots as {[K in keyof typeof D]: {from: number; duration: number}};
}

export const SHOTS = buildShots();
export const TOTAL_FRAMES = SHOTS.outro.from + SHOTS.outro.duration;

type Sfx = {from: number; src: string; volume?: number; durationInFrames?: number};

const curlBeat = (i: number) => SHOTS.curlProof.from + i * CURL_BEAT_LEN;

const SFX: Sfx[] = [
  {from: SHOTS.problem.from, src: 'audio/transition-soft.mp3', volume: 0.38},
  {from: SHOTS.solution.from, src: 'audio/transition-soft.mp3', volume: 0.4},
  {from: SHOTS.spotlight.from + 48, src: 'audio/whoosh-big.mp3', volume: 0.55},
  {from: SHOTS.spotlight.from + 60, src: 'audio/sparkle.mp3', volume: 0.45},
  {from: SHOTS.spotlight.from + 112, src: 'audio/transition-snap.mp3', volume: 0.5},
  {from: SHOTS.titleDn.from, src: 'audio/transition-soft.mp3', volume: 0.4},
  {from: SHOTS.deck.from + 34, src: 'audio/whoosh-big.mp3', volume: 0.5},
  {from: SHOTS.deck.from + 50, src: 'audio/whoosh-fast.mp3', volume: 0.35},
  {from: SHOTS.deck.from + 70, src: 'audio/whoosh-fast.mp3', volume: 0.28},
  {from: SHOTS.titleAcl.from, src: 'audio/transition-soft.mp3', volume: 0.4},
  {from: SHOTS.rows.from + 8, src: 'audio/transition-soft.mp3', volume: 0.35},
  {from: SHOTS.titleNoRoles.from, src: 'audio/transition-soft.mp3', volume: 0.4},
  {from: SHOTS.titleConfigFirst.from, src: 'audio/transition-soft.mp3', volume: 0.42},
  {from: SHOTS.configReveal.from + 18, src: 'audio/keyboard.mp3', volume: 0.28, durationInFrames: 100},
  {from: SHOTS.configReveal.from + 210, src: 'audio/transition-snap.mp3', volume: 0.4},
  {from: SHOTS.titleThenCurls.from, src: 'audio/transition-soft.mp3', volume: 0.42},
  ...[0, 1, 2, 3, 4, 5, 6, 7, 8].flatMap((i) => [
    {from: curlBeat(i) + 14, src: 'audio/keyboard.mp3', volume: 0.3, durationInFrames: 90} as Sfx,
    {
      from: curlBeat(i) + 108,
      src: i === 8 ? 'audio/transition-snap.mp3' : 'audio/pop.mp3',
      volume: 0.42,
    } as Sfx,
  ]),
  {from: SHOTS.titleClose.from, src: 'audio/transition-soft.mp3', volume: 0.42},
  {from: SHOTS.outro.from + 10, src: 'audio/riser-cine.mp3', volume: 0.45, durationInFrames: 40},
  {from: SHOTS.outro.from + 28, src: 'audio/impact-cine.mp3', volume: 0.55},
  {from: SHOTS.outro.from + 48, src: 'audio/sparkle.mp3', volume: 0.4},
];

export const PgGatewayPromo: React.FC = () => {
  return (
    <AbsoluteFill style={{backgroundColor: '#0b1220'}}>
      <Sequence from={SHOTS.problem.from} durationInFrames={SHOTS.problem.duration}>
        <TitleCard
          duration={SHOTS.problem.duration}
          line1="Недели на бэкенд — ради одного API?"
          line2="Каждая интеграция снова пишет свой слой к PostgreSQL."
        />
      </Sequence>
      <Sequence from={SHOTS.solution.from} durationInFrames={SHOTS.solution.duration}>
        <TitleCard
          duration={SHOTS.solution.duration}
          line1="Быстрый API к PostgreSQL из YAML"
          line2="Без кастомного бэкенда на каждую систему."
        />
      </Sequence>
      <Sequence from={SHOTS.spotlight.from} durationInFrames={SHOTS.spotlight.duration}>
        <SpotlightHeroCard />
      </Sequence>
      <Sequence from={SHOTS.titleDn.from} durationInFrames={SHOTS.titleDn.duration}>
        <TitleCard
          duration={SHOTS.titleDn.duration}
          line1="Каждому ТУЗ — только свои эндпоинты"
          line2="Права из DN сертификата, не из заголовков клиента."
        />
      </Sequence>
      <Sequence from={SHOTS.deck.from} durationInFrames={SHOTS.deck.duration}>
        <DeckDealFlyin />
      </Sequence>
      <Sequence from={SHOTS.titleAcl.from} durationInFrames={SHOTS.titleAcl.duration}>
        <TitleCard
          duration={SHOTS.titleAcl.duration}
          line1="Меньше утечек лишних данных"
          line2="Field-level ACL: только разрешённые поля и операции."
        />
      </Sequence>
      <Sequence from={SHOTS.rows.from} durationInFrames={SHOTS.rows.duration}>
        <RowEmbed />
      </Sequence>
      <Sequence from={SHOTS.titleNoRoles.from} durationInFrames={SHOTS.titleNoRoles.duration}>
        <TitleCard
          duration={SHOTS.titleNoRoles.duration}
          line1="Без X-Roles и X-Tenant-Id"
          line2="В cert_dn права задаёт ConfigMap — клиент не решает."
        />
      </Sequence>
      <Sequence from={SHOTS.titleConfigFirst.from} durationInFrames={SHOTS.titleConfigFirst.duration}>
        <TitleCard
          duration={SHOTS.titleConfigFirst.duration}
          line1="Сначала конфиг — потом API"
          line2="Покажем YAML users-admin, затем живые curl по этим правам."
        />
      </Sequence>
      <Sequence from={SHOTS.configReveal.from} durationInFrames={SHOTS.configReveal.duration}>
        <ConfigReveal />
      </Sequence>
      <Sequence from={SHOTS.titleThenCurls.from} durationInFrames={SHOTS.titleThenCurls.duration}>
        <TitleCard
          duration={SHOTS.titleThenCurls.duration}
          line1="Тот же YAML. Живые curl."
          line2="list · get · create · patch · filter · upsert · delete · deny"
        />
      </Sequence>
      <Sequence from={SHOTS.curlProof.from} durationInFrames={SHOTS.curlProof.duration}>
        <CurlProof />
      </Sequence>
      <Sequence from={SHOTS.titleClose.from} durationInFrames={SHOTS.titleClose.duration}>
        <TitleCard
          duration={SHOTS.titleClose.duration}
          line1="Конфиг вместо недель разработки"
          line2="Ресурсы, ACL и OpenAPI — за часы, не за спринты."
        />
      </Sequence>
      <Sequence from={SHOTS.outro.from} durationInFrames={SHOTS.outro.duration}>
        <Outro />
      </Sequence>

      {SFX.map((s, i) => (
        <Sequence key={i} from={s.from} durationInFrames={s.durationInFrames}>
          <Audio src={staticFile(s.src)} volume={s.volume ?? 0.5} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

export const SHOT_TABLE = Object.entries(SHOTS).map(([shot, v]) => ({
  shot,
  from: v.from,
  duration: v.duration,
}));
