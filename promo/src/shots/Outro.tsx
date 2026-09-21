import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, Easing} from 'remotion';

export const OUTRO_DURATION = 270;

export const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const slam = interpolate(frame, [10, 24], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.2, 1.1, 0.3, 1),
  });
  const subIn = interpolate(frame, [28, 44], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0, 0, 0.2, 1),
  });
  const ctaIn = interpolate(frame, [56, 74], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0, 0, 0.2, 1),
  });
  const hold = interpolate(frame, [OUTRO_DURATION - 8, OUTRO_DURATION], [1, 0.92], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill
      style={{
        background: 'radial-gradient(1100px 700px at 50% 38%, #152238 0%, #0b1220 68%)',
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
          maxWidth: 1400,
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
        <div
          style={{
            marginTop: 22,
            color: '#e2e8f0',
            fontSize: 30,
            fontWeight: 600,
            letterSpacing: '-0.02em',
            opacity: subIn,
          }}
        >
          API к PostgreSQL без кастомного бэкенда
        </div>
        <div
          style={{
            marginTop: 26,
            fontFamily: '"IBM Plex Mono", monospace',
            fontSize: 18,
            color: '#5eead4',
            opacity: subIn,
          }}
        >
          cert_dn · гранты по ТУЗ · X-Client-Cert-DN
        </div>
        <div
          style={{
            marginTop: 36,
            display: 'inline-block',
            padding: '14px 28px',
            borderRadius: 14,
            border: '1px solid rgba(45,212,191,0.45)',
            background: 'rgba(19,78,74,0.35)',
            color: '#99f6e4',
            fontSize: 24,
            fontWeight: 600,
            opacity: ctaIn,
            transform: `translateY(${(1 - ctaIn) * 12}px)`,
          }}
        >
          Подключите ТУЗ за часы — не за недели
        </div>
      </div>
    </AbsoluteFill>
  );
};
