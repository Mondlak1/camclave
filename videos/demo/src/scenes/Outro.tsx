import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {PALETTE} from '../palette';

export const OutroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const enter = spring({frame, fps, config: {damping: 18}});
  const opacity = interpolate(enter, [0, 1], [0, 1]);
  const y = interpolate(enter, [0, 1], [20, 0]);

  return (
    <AbsoluteFill
      style={{
        background: PALETTE.bg,
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div style={{opacity, transform: `translateY(${y}px)`, textAlign: 'center'}}>
        <div
          style={{
            color: PALETTE.ink,
            fontFamily: 'Inter, sans-serif',
            fontSize: 30,
            fontWeight: 600,
            marginBottom: 30,
          }}
        >
          Install:
        </div>
        <div
          style={{
            display: 'inline-block',
            background: PALETTE.termBg,
            borderRadius: 12,
            padding: '20px 28px',
            border: '1px solid #2a2a30',
            boxShadow: '0 20px 40px rgba(0,0,0,0.4)',
          }}
        >
          <div
            style={{
              fontFamily: '"Cascadia Mono", Consolas, monospace',
              fontSize: 24,
              color: PALETTE.termInk,
              whiteSpace: 'pre',
            }}
          >
            <span style={{color: PALETTE.termPrompt}}>$ </span>
            git clone https://github.com/Mondlak1/camclave
          </div>
          <div
            style={{
              fontFamily: '"Cascadia Mono", Consolas, monospace',
              fontSize: 24,
              color: PALETTE.termInk,
              whiteSpace: 'pre',
              marginTop: 6,
            }}
          >
            <span style={{color: PALETTE.termPrompt}}>$ </span>
            pwsh ./install.ps1
          </div>
        </div>
        <div
          style={{
            color: PALETTE.accent,
            fontFamily: 'Inter, sans-serif',
            fontSize: 18,
            marginTop: 36,
            fontStyle: 'italic',
          }}
        >
          github.com/Mondlak1/camclave
        </div>
      </div>
    </AbsoluteFill>
  );
};
