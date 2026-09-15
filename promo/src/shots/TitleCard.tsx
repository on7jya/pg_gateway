import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, Easing} from 'remotion';

export const TITLE_DURATION = 40;

export const TitleCard: React.FC<{line1: string; line2?: string; accent?: string}> = ({
  line1,
  line2,
  accent = '#5eead4',
}) => {
  const frame = useCurrentFrame();
  const inT = interpolate(frame, [0, 12], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0, 0, 0.2, 1),
  });
  const hold = interpolate(frame, [TITLE_DURATION - 8, TITLE_DURATION], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const opacity = inT * hold;
  const y = (1 - inT) * 18;

  return (
    <AbsoluteFill
      style={{
        background: 'radial-gradient(1200px 700px at 50% 40%, #152238 0%, #0b1220 70%)',
        justifyContent: 'center',
        alignItems: 'center',
        fontFamily: '"IBM Plex Sans", sans-serif',
      }}
    >
      <div style={{opacity, transform: `translateY(${y}px)`, textAlign: 'center', maxWidth: 1400}}>
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
            fontSize: 64,
            fontWeight: 700,
            letterSpacing: '-0.03em',
            lineHeight: 1.1,
          }}
        >
          {line1}
        </div>
        {line2 ? (
          <div style={{marginTop: 16, color: '#94a3b8', fontSize: 28, fontWeight: 500}}>{line2}</div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
