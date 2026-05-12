import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {PALETTE} from '../palette';

const POINTS = [
  {label: 'No video. Ever.', detail: 'cv2.VideoWriter never instantiated'},
  {label: 'No upload.', detail: 'zero network code — verified in CI'},
  {label: 'You consented.', detail: 'capture refuses without an active session'},
];

export const SafetyScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  return (
    <AbsoluteFill
      style={{
        background: PALETTE.bg,
        alignItems: 'center',
        justifyContent: 'center',
        gap: 24,
      }}
    >
      <div
        style={{
          color: PALETTE.inkDim,
          fontFamily: 'Inter, sans-serif',
          fontSize: 16,
          letterSpacing: 4,
          textTransform: 'uppercase',
          marginBottom: 12,
        }}
      >
        Audit-verified safety
      </div>
      <div style={{display: 'flex', gap: 28, marginTop: 6}}>
        {POINTS.map((p, i) => {
          const enter = spring({
            frame: frame - i * 8,
            fps,
            config: {damping: 18},
          });
          const opacity = interpolate(enter, [0, 1], [0, 1]);
          const y = interpolate(enter, [0, 1], [24, 0]);
          return (
            <div
              key={p.label}
              style={{
                opacity,
                transform: `translateY(${y}px)`,
                background: PALETTE.panel,
                border: `1px solid ${PALETTE.borderInner}`,
                borderRadius: 14,
                padding: '24px 28px',
                width: 320,
                textAlign: 'center',
                boxShadow: '0 18px 36px rgba(0,0,0,0.4)',
              }}
            >
              <div
                style={{
                  color: PALETTE.border,
                  fontFamily: 'Inter, sans-serif',
                  fontSize: 24,
                  fontWeight: 800,
                  marginBottom: 8,
                }}
              >
                {p.label}
              </div>
              <div
                style={{
                  color: PALETTE.inkDim,
                  fontFamily: '"Cascadia Mono", Consolas, monospace',
                  fontSize: 13,
                }}
              >
                {p.detail}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
