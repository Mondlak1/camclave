import React from 'react';
import {interpolate, useCurrentFrame} from 'remotion';

/**
 * Synthetic multimeter LCD shown inside the preview window so the demo
 * video doesn't leak any of the user's actual webcam footage.
 *
 * Animated: the reading drifts slightly so it feels live.
 */
export const SyntheticMultimeter: React.FC<{value?: string; unit?: string}> = ({
  value = '4.96',
  unit = 'V DC',
}) => {
  const frame = useCurrentFrame();
  // Subtle "live" jitter on the last digit
  const jitter = Math.sin(frame / 8) * 0.005;
  const reading = (parseFloat(value) + jitter).toFixed(2);

  // Slight reading-light flicker
  const lcdGlow = interpolate(Math.sin(frame / 6), [-1, 1], [0.85, 1]);

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        background:
          'radial-gradient(ellipse at center, #181818 0%, #0a0a0a 100%)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* "Bench" texture bands */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background:
            'repeating-linear-gradient(0deg, transparent 0 4px, rgba(255,255,255,0.012) 4px 5px)',
        }}
      />
      {/* Multimeter body */}
      <div
        style={{
          width: '76%',
          background:
            'linear-gradient(180deg, #2a2a2d 0%, #1a1a1d 60%, #0e0e10 100%)',
          borderRadius: 24,
          padding: 28,
          boxShadow:
            '0 30px 60px rgba(0,0,0,0.7), inset 0 1px 0 rgba(255,255,255,0.08)',
          border: '1px solid #3a3a3d',
        }}
      >
        {/* Brand strip */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontFamily: 'Inter, sans-serif',
            color: '#c4b9b3',
            fontSize: 16,
            letterSpacing: 2,
            marginBottom: 18,
          }}
        >
          <span style={{fontWeight: 700, letterSpacing: 3}}>BENCH-DMM</span>
          <span style={{fontSize: 13, color: '#7a7a7a'}}>True RMS · 600V</span>
        </div>
        {/* LCD */}
        <div
          style={{
            background: '#b8c19a',
            borderRadius: 8,
            padding: '22px 28px',
            display: 'flex',
            alignItems: 'baseline',
            justifyContent: 'flex-end',
            boxShadow:
              'inset 0 6px 12px rgba(0,0,0,0.25), inset 0 -2px 4px rgba(255,255,255,0.25)',
            opacity: lcdGlow,
          }}
        >
          <span
            style={{
              fontFamily: '"DSEG7 Classic", "Cascadia Mono", monospace',
              fontSize: 108,
              fontWeight: 700,
              color: '#0d1f0d',
              letterSpacing: -2,
              lineHeight: 1,
              textShadow: '0 0 8px rgba(0,0,0,0.2)',
            }}
          >
            {reading}
          </span>
          <span
            style={{
              fontFamily: 'Inter, sans-serif',
              fontSize: 26,
              color: '#0d1f0d',
              marginLeft: 16,
              fontWeight: 700,
              letterSpacing: 1,
            }}
          >
            {unit}
          </span>
        </div>
        {/* Knob row */}
        <div
          style={{
            display: 'flex',
            gap: 22,
            marginTop: 22,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {['mA', 'V~', 'V=', 'Ω', 'µF'].map((label, i) => (
            <div
              key={label}
              style={{
                width: 46,
                height: 46,
                borderRadius: '50%',
                background:
                  i === 2
                    ? 'radial-gradient(circle, #d4a574 0%, #6e4c2a 100%)'
                    : 'radial-gradient(circle, #3a3a3d 0%, #1a1a1d 100%)',
                color: i === 2 ? '#0b0b10' : '#a0a0a0',
                fontFamily: 'Inter, sans-serif',
                fontSize: 14,
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                border: '1px solid rgba(255,255,255,0.08)',
                boxShadow: '0 3px 6px rgba(0,0,0,0.4)',
              }}
            >
              {label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
