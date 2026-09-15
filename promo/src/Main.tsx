import React from 'react';
import {AbsoluteFill, Audio, Sequence, staticFile} from 'remotion';
import {SpotlightHeroCard, SPOTLIGHT_HERO_CARD_DURATION} from './shots/SpotlightHeroCard';
import {DeckDealFlyin, DECK_DEAL_FLYIN_DURATION} from './shots/DeckDealFlyin';
import {RowEmbed, ROW_EMBED_DURATION} from './shots/RowEmbed';
import {TitleCard, TITLE_DURATION} from './shots/TitleCard';
import {Outro, OUTRO_DURATION} from './shots/Outro';

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

const S = {
  spotlight: 0,
  title1: SPOTLIGHT_HERO_CARD_DURATION,
  deck: SPOTLIGHT_HERO_CARD_DURATION + TITLE_DURATION,
  title2: SPOTLIGHT_HERO_CARD_DURATION + TITLE_DURATION + DECK_DEAL_FLYIN_DURATION,
  rows: SPOTLIGHT_HERO_CARD_DURATION + TITLE_DURATION + DECK_DEAL_FLYIN_DURATION + TITLE_DURATION,
  outro:
    SPOTLIGHT_HERO_CARD_DURATION +
    TITLE_DURATION +
    DECK_DEAL_FLYIN_DURATION +
    TITLE_DURATION +
    ROW_EMBED_DURATION,
} as const;

export const TOTAL_FRAMES = S.outro + OUTRO_DURATION;

type Sfx = {from: number; src: string; volume?: number};

const SFX: Sfx[] = [
  {from: S.spotlight + 48, src: 'audio/whoosh-big.mp3', volume: 0.55},
  {from: S.spotlight + 60, src: 'audio/sparkle.mp3', volume: 0.45},
  {from: S.spotlight + 112, src: 'audio/transition-snap.mp3', volume: 0.5},
  {from: S.title1, src: 'audio/transition-soft.mp3', volume: 0.4},
  {from: S.deck + 34, src: 'audio/whoosh-big.mp3', volume: 0.5},
  {from: S.deck + 50, src: 'audio/whoosh-fast.mp3', volume: 0.35},
  {from: S.deck + 70, src: 'audio/whoosh-fast.mp3', volume: 0.28},
  {from: S.title2, src: 'audio/transition-soft.mp3', volume: 0.4},
  {from: S.rows + 8, src: 'audio/transition-soft.mp3', volume: 0.35},
  {from: S.outro + 4, src: 'audio/riser-cine.mp3', volume: 0.45},
  {from: S.outro + 16, src: 'audio/impact-cine.mp3', volume: 0.55},
  {from: S.outro + 22, src: 'audio/sparkle.mp3', volume: 0.4},
];

export const PgGatewayPromo: React.FC = () => {
  return (
    <AbsoluteFill style={{backgroundColor: '#0b1220'}}>
      <Sequence from={S.spotlight} durationInFrames={SPOTLIGHT_HERO_CARD_DURATION}>
        <SpotlightHeroCard />
      </Sequence>
      <Sequence from={S.title1} durationInFrames={TITLE_DURATION}>
        <TitleCard line1="YAML in. Routes out." line2="No hardcoded schema — config is the contract." />
      </Sequence>
      <Sequence from={S.deck} durationInFrames={DECK_DEAL_FLYIN_DURATION}>
        <DeckDealFlyin />
      </Sequence>
      <Sequence from={S.title2} durationInFrames={TITLE_DURATION}>
        <TitleCard line1="Fields land in the API." line2="Whitelist → Pydantic → OpenAPI." />
      </Sequence>
      <Sequence from={S.rows} durationInFrames={ROW_EMBED_DURATION}>
        <RowEmbed />
      </Sequence>
      <Sequence from={S.outro} durationInFrames={OUTRO_DURATION}>
        <Outro />
      </Sequence>

      {SFX.map((s, i) => (
        <Sequence key={i} from={s.from}>
          <Audio src={staticFile(s.src)} volume={s.volume ?? 0.5} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

export const SHOT_TABLE = [
  {shot: 'spotlight-hero-card', from: S.spotlight, duration: SPOTLIGHT_HERO_CARD_DURATION},
  {shot: 'title-1', from: S.title1, duration: TITLE_DURATION},
  {shot: 'deck-deal-flyin', from: S.deck, duration: DECK_DEAL_FLYIN_DURATION},
  {shot: 'title-2', from: S.title2, duration: TITLE_DURATION},
  {shot: 'row-embed', from: S.rows, duration: ROW_EMBED_DURATION},
  {shot: 'outro', from: S.outro, duration: OUTRO_DURATION},
];
