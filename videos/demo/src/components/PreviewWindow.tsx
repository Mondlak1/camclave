import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {PALETTE} from '../palette';

/**
 * Visual replica of preview_daemon.py's tkinter window — same palette,
 * same chrome (deep crimson border, breathing dot, "CAMERA ACTIVE",
 * gold wordmark, raised footer band with mode + TTL). The inner content
 * is supplied as children (in the demo: SyntheticMultimeter).
 *
 * Props:
 *   flashAt: frame number to flash white on (e.g. when capture fires)
 *   mode:    "live" | "capturing" | "snapshot"
 *   reason:  optional caption shown next to "capturing" mode for ~4s
 *   ttl:     "MM:SS" string for the right side of the footer
 */
export const PreviewWindow: React.FC<{
  flashAt?: number;
  mode?: 'live' | 'capturing' | 'snapshot';
  reason?: string;
  ttl?: string;
  capturesCount?: number;
  children: React.ReactNode;
}> = ({flashAt, mode = 'live', reason, ttl = '14:36', capturesCount = 0, children}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  // Breathing dot — sinusoidal pulse on ~1.6s period (matches daemon)
  const breath = 0.5 * (1 + Math.sin((frame / fps) * (2 * Math.PI / 1.6)));
  const dotColor = lerpHex(PALETTE.dotLo, PALETTE.dotHi, breath);

  // Soft cream flash over ~0.35s, ease-out
  let flashAlpha = 0;
  if (flashAt !== undefined && frame >= flashAt) {
    const t = (frame - flashAt) / (fps * 0.35);
    if (t < 1) {
      const remaining = 1 - t;
      flashAlpha = Math.min(0.8, remaining ** 1.5 * 0.8);
    }
  }

  // Footer mode text + color
  let modeText = `● live  (${capturesCount} captured)`;
  let modeFg = PALETTE.inkDim;
  if (mode === 'capturing') {
    modeText = reason ? `● capturing — ${reason}` : `● capturing  (${capturesCount})`;
    modeFg = PALETTE.dotLo;
  } else if (mode === 'snapshot') {
    modeText = `● snapshot mode  every 30s  (${capturesCount})`;
    modeFg = PALETTE.accent;
  }

  return (
    <div
      style={{
        width: 720,
        background: PALETTE.border,
        padding: 5,
        borderRadius: 6,
        boxShadow: '0 24px 56px rgba(177, 18, 38, 0.35), 0 0 0 1px rgba(0,0,0,0.4)',
      }}
    >
      {/* Bevel */}
      <div style={{background: PALETTE.borderInner, padding: 1}}>
        {/* Panel */}
        <div style={{background: PALETTE.panel}}>
          {/* Header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              padding: '12px 18px 8px 18px',
              gap: 10,
            }}
          >
            <div
              style={{
                width: 14,
                height: 14,
                borderRadius: '50%',
                background: dotColor,
                boxShadow: `0 0 ${8 + breath * 6}px ${dotColor}`,
              }}
            />
            <span
              style={{
                color: PALETTE.ink,
                fontFamily: 'Inter, "Segoe UI", sans-serif',
                fontSize: 16,
                fontWeight: 700,
                letterSpacing: 0.3,
                flex: 1,
              }}
            >
              CAMERA ACTIVE
            </span>
            <span
              style={{
                color: PALETTE.accent,
                fontFamily: 'Inter, "Segoe UI", sans-serif',
                fontSize: 14,
                fontStyle: 'italic',
              }}
            >
              camclave
            </span>
          </div>

          {/* Frame area */}
          <div
            style={{
              position: 'relative',
              margin: '0 18px',
              background: PALETTE.panel,
              aspectRatio: '16/9',
              overflow: 'hidden',
            }}
          >
            {children}
            {/* Capture flash overlay */}
            <div
              style={{
                position: 'absolute',
                inset: 0,
                background: 'rgb(245, 232, 227)',
                opacity: flashAlpha,
                pointerEvents: 'none',
              }}
            />
          </div>

          {/* Footer */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              margin: '10px 18px 12px 18px',
              padding: '8px 12px',
              background: PALETTE.panelAlt,
            }}
          >
            <span
              style={{
                color: modeFg,
                fontFamily: 'Inter, "Segoe UI", sans-serif',
                fontSize: 13,
                fontWeight: 700,
              }}
            >
              {modeText}
            </span>
            <span
              style={{
                color: PALETTE.ink,
                fontFamily: '"Cascadia Mono", Consolas, monospace',
                fontSize: 14,
              }}
            >
              ttl  {ttl}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

function lerpHex(c1: string, c2: string, t: number): string {
  const r1 = parseInt(c1.slice(1, 3), 16);
  const g1 = parseInt(c1.slice(3, 5), 16);
  const b1 = parseInt(c1.slice(5, 7), 16);
  const r2 = parseInt(c2.slice(1, 3), 16);
  const g2 = parseInt(c2.slice(3, 5), 16);
  const b2 = parseInt(c2.slice(5, 7), 16);
  const r = Math.round(r1 + (r2 - r1) * t);
  const g = Math.round(g1 + (g2 - g1) * t);
  const b = Math.round(b1 + (b2 - b1) * t);
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}
