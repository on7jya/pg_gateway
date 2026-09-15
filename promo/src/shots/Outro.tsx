import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, Easing} from 'remotion';

export const OUTRO_DURATION = 54;

export const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const slam = interpolate(frame, [8, 18], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.2, 1.1, 0.3, 1),
  });
  const hold = interpolate(frame, [OUTRO_DURATION - 6, OUTRO_DURATION], [1, 0.92], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill
      style={{
        background: '#0b1220',
        justifyContent: 'center',
        alignItems: 'center',
        fontFamily: '"IBM Plex Sans", sans-serif',
      }}
    >
      <div
        style={{
          opacity: slam * hold,
          transform: `scale(${0.92 + 0.08 * slam})`,
          textAlign: 'center',
        }}
      >
        <div
          style={{
            fontFamily: '"IBM Plex Mono", monospace',
            fontSize: 72,
            fontWeight: 700,
            color: '#5eead4',
            letterSpacing: '-0.02em',
          }}
        >
          pg_gateway
        </div>
        <div style={{marginTop: 18, color: '#cbd5e1', fontSize: 28, fontWeight: 500}}>
          Config-driven API Gateway for PostgreSQL
        </div>
        <div
          style={{
            marginTop: 28,
            fontFamily: '"IBM Plex Mono", monospace',
            fontSize: 16,
            color: '#64748b',
          }}
        >
          YAML · FastAPI · ACL · OpenAPI · docker-compose
        </div>
      </div>
    </AbsoluteFill>
  );
};
