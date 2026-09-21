import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, Easing} from 'remotion';
import snippets from '../fixtures/config_snippets.json';

/** Config-first reveal: accounts users-admin grant, then users resource ops. */
export const CONFIG_REVEAL_DURATION = 420;

const MONO = '"IBM Plex Mono", ui-monospace, monospace';
const SANS = '"IBM Plex Sans", "Segoe UI", sans-serif';

const PHASE_SWAP = 200; // switch from accounts → resource

function visibleLines(text: string, frame: number, start: number, linesPerFrame = 0.35) {
  const lines = text.replace(/\n$/, '').split('\n');
  const n = Math.min(lines.length, Math.max(0, Math.floor((frame - start) * linesPerFrame)));
  return lines.slice(0, n).join('\n');
}

function highlightLine(line: string): React.ReactNode {
  const isKey = /^\s{0,2}(accounts|authz|grants|users|resources|operations|soft_delete|fields|filterable|upsert_keys):/.test(line)
    || /CN=users-admin/.test(line)
    || /^\s+(list|get|create|update|patch|delete|upsert|batch_create):/.test(line);
  const isComment = line.trimStart().startsWith('#');
  const isAccent = /users-admin|operations:|enabled: true/.test(line);
  let color = '#cbd5e1';
  if (isComment) color = '#64748b';
  else if (isAccent) color = '#5eead4';
  else if (isKey) color = '#99f6e4';
  return <span style={{color}}>{line || ' '}</span>;
}

export const ConfigReveal: React.FC = () => {
  const frame = useCurrentFrame();
  const panelIn = interpolate(frame, [0, 16], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0, 0, 0.2, 1),
  });

  const showResource = frame >= PHASE_SWAP;
  const swapT = interpolate(frame, [PHASE_SWAP, PHASE_SWAP + 14], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0, 0, 0.2, 1),
  });

  const accountsText = visibleLines(snippets.accounts, frame, 18, 0.42);
  const resourceText = visibleLines(snippets.resource, frame, PHASE_SWAP + 18, 0.42);
  const activeTitle = showResource ? snippets.title_resource : snippets.title_accounts;
  const activeText = showResource ? resourceText : accountsText;
  const badge = showResource ? 'resource' : 'cert_dn · ТУЗ';

  return (
    <AbsoluteFill
      style={{
        background: 'radial-gradient(1400px 800px at 50% 18%, #152238 0%, #0b1220 65%)',
        fontFamily: SANS,
        color: '#e2e8f0',
        padding: 64,
      }}
    >
      <div style={{opacity: panelIn, transform: `translateY(${(1 - panelIn) * 16}px)`}}>
        <div
          style={{
            fontFamily: MONO,
            fontSize: 14,
            letterSpacing: '0.16em',
            textTransform: 'uppercase',
            color: '#5eead4',
            fontWeight: 600,
            marginBottom: 14,
          }}
        >
          сначала конфиг · {badge}
        </div>
        <div style={{fontSize: 40, fontWeight: 700, letterSpacing: '-0.02em', color: '#f8fafc'}}>
          YAML задаёт права и операции
        </div>
        <div style={{marginTop: 10, fontSize: 22, color: '#94a3b8', fontWeight: 500, maxWidth: 1100}}>
          users-admin получает users: list · get · create · patch · delete — без кастомного бэкенда.
        </div>

        <div
          style={{
            marginTop: 28,
            display: 'flex',
            gap: 12,
            marginBottom: 14,
          }}
        >
          {[snippets.title_accounts, snippets.title_resource].map((t, i) => {
            const active = (!showResource && i === 0) || (showResource && i === 1);
            return (
              <div
                key={t}
                style={{
                  fontFamily: MONO,
                  fontSize: 13,
                  padding: '8px 14px',
                  borderRadius: 10,
                  background: active ? '#134e4a' : 'rgba(148,163,184,0.12)',
                  color: active ? '#99f6e4' : '#94a3b8',
                  border: active ? '1px solid #2dd4bf' : '1px solid transparent',
                  opacity: i === 1 ? 0.55 + 0.45 * swapT : 1,
                }}
              >
                {t}
              </div>
            );
          })}
        </div>

        <div
          style={{
            background: '#0f172a',
            border: '1px solid rgba(148,163,184,0.22)',
            borderRadius: 18,
            padding: '22px 28px 28px',
            minHeight: 520,
            boxShadow: '0 30px 60px rgba(2,6,23,0.45)',
            opacity: showResource ? 0.55 + 0.45 * swapT : 1,
          }}
        >
          <div style={{fontFamily: MONO, fontSize: 13, color: '#64748b', marginBottom: 14}}>
            {activeTitle}
          </div>
          <pre
            style={{
              fontFamily: MONO,
              fontSize: 20,
              lineHeight: 1.45,
              whiteSpace: 'pre-wrap',
              margin: 0,
            }}
          >
            {activeText.split('\n').map((line, i) => (
              <div key={i}>{highlightLine(line)}</div>
            ))}
            <span style={{opacity: frame % 20 < 12 ? 1 : 0, color: '#5eead4'}}>▌</span>
          </pre>
        </div>
      </div>
    </AbsoluteFill>
  );
};
