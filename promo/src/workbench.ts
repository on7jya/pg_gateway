/**
 * Workbench manifest — shot boundaries from SHOTS (single source of truth).
 * Open with: node ~/.cursor/skills/video-shotcraft/workbench/scripts/open.mjs promo
 */
import {SHOT_TABLE, TOTAL_FRAMES, FPS, WIDTH, HEIGHT} from './Main';

export const workbench = {
  compositionId: 'PgGatewayPromo',
  durationInFrames: TOTAL_FRAMES,
  fps: FPS,
  width: WIDTH,
  height: HEIGHT,
  shots: SHOT_TABLE,
};
