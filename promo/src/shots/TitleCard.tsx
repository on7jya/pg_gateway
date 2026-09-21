import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, Easing} from 'remotion';

/** Default interstitial title length (~2.8s). Override via `duration`. */
export const TITLE_DURATION = 84;

export const TitleCard: React.FC<{
  line1: string;
  line2?: string;
  accent?: string;
  duration?: number;
}> = ({line1, line2, accent = '#5eead4', duration = TITLE_DURATION}) => {
  const frame = useCurrentFrame();
  const inT = interpolate(frame, [0, 14], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0, 0, 0.2, 1),
  });
  const hold = interpolate(frame, [duration - 10, duration], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const opacity = inT * hold;
  const y = (1 - inT) * 18;
  const long = line1.length > 42;
  const fontSize = long ? 48 : 56;

  return (
    <AbsoluteFill
      style={{
        background: 'radial-gradient(1200px 700px at 50% 40%, #152238 0%, #0b1220 70%)',
        justifyContent: 'center',
        alignItems: 'center',
        fontFamily: '"IBM Plex Sans", sans-serif',
      }}
    >
      <div style={{opacity, transform: `translateY(${y}px)`, textAlign: 'center', maxWidth: 1500}}>
        <div
          style={{
            fontFamily: '"IBM Plex Mono", monospace',
            color: accent,
            fontSize: 16,
            letterSpacing: '0.18em',
            textTransform: 'uppercase',
            marginBottom: 18,
            fontWeight: 600,
          }}
        >
          pg_gateway
        </div>
        <div
          style={{
            color: '#f8fafc',
            fontSize,
            fontWeight: 700,
            letterSpacing: '-0.03em',
            lineHeight: 1.15,
          }}
        >
          {line1}
        </div>
        {line2 ? (
          <div
            style={{
              marginTop: 18,
              color: '#94a3b8',
              fontSize: 26,
              fontWeight: 500,
              lineHeight: 1.35,
              maxWidth: 1100,
              marginLeft: 'auto',
              marginRight: 'auto',
            }}
          >
            {line2}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
