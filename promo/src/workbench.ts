/**
 * Minimal workbench manifest so `node workbench/scripts/open.mjs` can import the film.
 * Full schema-driven editing can be expanded later; this documents shot boundaries.
 */
import {SHOT_TABLE, TOTAL_FRAMES} from './Main';

export const workbench = {
  compositionId: 'PgGatewayPromo',
  durationInFrames: TOTAL_FRAMES,
  fps: 30,
  width: 1920,
  height: 1080,
  shots: SHOT_TABLE,
};
