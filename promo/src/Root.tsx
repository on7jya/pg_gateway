import React from 'react';
import {Composition} from 'remotion';
import {PgGatewayPromo, TOTAL_FRAMES, FPS, WIDTH, HEIGHT} from './Main';

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="PgGatewayPromo"
        component={PgGatewayPromo}
        durationInFrames={TOTAL_FRAMES}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
      />
    </>
  );
};
