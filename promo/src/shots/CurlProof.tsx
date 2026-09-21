import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, Easing} from 'remotion';
import fixtures from '../fixtures/users_crud_responses.json';

/** Config → live CRUD curl theater (quality over speed). */
export const CURL_BEAT_LEN = 320;
const BEAT_KEYS = [
  'list',
  'get',
  'create',
  'patch',
  'filter',
  'upsert',
  'delete',
  'get_after_delete',
  'deny',
] as const;

export const CURL_PROOF_DURATION = CURL_BEAT_LEN * BEAT_KEYS.length; // 2880

const MONO = '"IBM Plex Mono", ui-monospace, monospace';
const SANS = '"IBM Plex Sans", "Segoe UI", sans-serif';

type BeatKey = (typeof BEAT_KEYS)[number];

type FixtureBeat = {
  status: number;
  label: string;
  headline: string;
  cmd: string;
  body: unknown;
  request?: unknown;
};

function statusTone(status: number) {
  if (status >= 200 && status < 300) return '#10b981';
  if (status === 403) return '#f43f5e';
  if (status === 404 || status === 401) return '#f59e0b';
  return '#94a3b8';
}

function typeLen(frame: number, start: number, full: number, charsPerFrame = 1.8) {
  const local = Math.max(0, frame - start);
  return Math.min(full, Math.floor(local * charsPerFrame));
}

function pretty(body: unknown) {
  return JSON.stringify(body, null, 2);
}

export const CurlProof: React.FC = () => {
  const frame = useCurrentFrame();
  const beatIndex = Math.min(BEAT_KEYS.length - 1, Math.floor(frame / CURL_BEAT_LEN));
  const key = BEAT_KEYS[beatIndex] as BeatKey;
  const beat = fixtures[key] as FixtureBeat;
  const local = frame - beatIndex * CURL_BEAT_LEN;
  const tone = statusTone(beat.status);

  const panelIn = interpolate(local, [0, 12], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0, 0, 0.2, 1),
  });
  const statusPop = interpolate(local, [100, 116], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.2, 1.15, 0.3, 1),
  });
  const bodyIn = interpolate(local, [124, 148], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0, 0, 0.2, 1),
  });

  const bodyText = pretty(beat.body);
  const cmdShown = beat.cmd.slice(0, typeLen(frame, beatIndex * CURL_BEAT_LEN + 14, beat.cmd.length, 1.9));
  const bodyShown = bodyText.slice(0, typeLen(frame, beatIndex * CURL_BEAT_LEN + 130, bodyText.length, 2.4));

  return (
    <AbsoluteFill
      style={{
        background: 'radial-gradient(1400px 800px at 50% 20%, #152238 0%, #0b1220 65%)',
        fontFamily: SANS,
        color: '#e2e8f0',
        padding: 64,
      }}
    >
      <div style={{opacity: panelIn, transform: `translateY(${(1 - panelIn) * 18}px)`}}>
        <div
          style={{
            fontFamily: MONO,
            fontSize: 14,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            color: '#5eead4',
            fontWeight: 600,
            marginBottom: 12,
          }}
        >
          users-admin · live fixture · {beat.label}
        </div>
        <div style={{fontSize: 36, fontWeight: 700, letterSpacing: '-0.02em', color: '#f8fafc'}}>
          {beat.headline}
        </div>
        <div style={{marginTop: 8, fontSize: 20, color: '#94a3b8'}}>
          Тот же YAML. Реальный ответ PostgreSQL.
        </div>

        <div
          style={{
            marginTop: 26,
            display: 'grid',
            gridTemplateColumns: '1.12fr 0.88fr',
            gap: 24,
          }}
        >
          <div
            style={{
              background: '#0f172a',
              border: '1px solid rgba(148,163,184,0.22)',
              borderRadius: 18,
              padding: '24px 26px',
              minHeight: 460,
              boxShadow: '0 30px 60px rgba(2,6,23,0.45)',
            }}
          >
            <div style={{fontFamily: MONO, fontSize: 13, color: '#64748b', marginBottom: 12}}>$ terminal</div>
            <pre
              style={{
                fontFamily: MONO,
                fontSize: 17,
                lineHeight: 1.5,
                color: '#cbd5e1',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                margin: 0,
              }}
            >
              {cmdShown}
              <span style={{opacity: local % 20 < 12 ? 1 : 0, color: '#5eead4'}}>▌</span>
            </pre>
          </div>

          <div
            style={{
              background: '#f4f7fb',
              color: '#0f172a',
              borderRadius: 18,
              padding: '24px 26px',
              minHeight: 460,
              boxShadow: '0 30px 60px rgba(2,6,23,0.35)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                opacity: statusPop,
                transform: `scale(${0.92 + 0.08 * statusPop})`,
              }}
            >
              <div
                style={{
                  fontFamily: MONO,
                  fontSize: 26,
                  fontWeight: 700,
                  color: tone,
                  background: '#0b1220',
                  padding: '8px 14px',
                  borderRadius: 12,
                }}
              >
                {beat.status}
              </div>
              <div style={{fontSize: 20, fontWeight: 600}}>HTTP-ответ</div>
            </div>
            <pre
              style={{
                marginTop: 18,
                fontFamily: MONO,
                fontSize: 15,
                lineHeight: 1.45,
                color: '#1e293b',
                opacity: bodyIn,
                whiteSpace: 'pre-wrap',
                maxHeight: 360,
                overflow: 'hidden',
              }}
            >
              {bodyShown}
            </pre>
          </div>
        </div>

        <div style={{marginTop: 22, display: 'flex', flexWrap: 'wrap', gap: 8}}>
          {BEAT_KEYS.map((k, i) => {
            const b = fixtures[k] as FixtureBeat;
            const active = i === beatIndex;
            return (
              <div
                key={k}
                style={{
                  fontFamily: MONO,
                  fontSize: 12,
                  padding: '6px 10px',
                  borderRadius: 999,
                  background: active ? '#134e4a' : 'rgba(148,163,184,0.12)',
                  color: active ? '#99f6e4' : '#94a3b8',
                  border: active ? '1px solid #2dd4bf' : '1px solid transparent',
                }}
              >
                {b.status} · {b.label}
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
