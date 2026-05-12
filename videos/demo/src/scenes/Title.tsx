import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {PALETTE} from '../palette';

export const TitleScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const enter = spring({frame, fps, config: {damping: 18}});
  const opacity = interpolate(enter, [0, 1], [0, 1]);
  const scale = interpolate(enter, [0, 1], [0.95, 1]);

  return (
    <AbsoluteFill
      style={{
        background: PALETTE.bg,
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div style={{opacity, transform: `scale(${scale})`, textAlign: 'center'}}>
        <Logo />
        <div
          style={{
            color: PALETTE.ink,
            fontFamily: 'Inter, sans-serif',
            fontSize: 36,
            fontWeight: 600,
            marginTop: 24,
          }}
        >
          Connect your camera to an AI agent.
        </div>
        <div
          style={{
            color: PALETTE.accent,
            fontFamily: 'Inter, sans-serif',
            fontSize: 22,
            fontStyle: 'italic',
            marginTop: 6,
          }}
        >
          Solve hardware in real life.
        </div>
      </div>
    </AbsoluteFill>
  );
};

const Logo: React.FC = () => {
  const frame = useCurrentFrame();
  // Subtle camera "eye" pulse — slower than the daemon's breathing dot
  const pulse = 0.5 + 0.5 * Math.sin(frame / 30);

  return (
    <svg width={420} height={140} viewBox="0 0 240 80">
      <defs>
        <linearGradient id="g" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stopColor={PALETTE.border} />
          <stop offset="100%" stopColor={PALETTE.termPrompt} />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="236" height="76" rx="14" fill={PALETTE.bg} stroke="url(#g)" strokeWidth="3" />
      <g transform="translate(20,18)">
        <circle cx="22" cy="22" r="20" fill="none" stroke={PALETTE.border} strokeWidth="3" />
        <circle cx="22" cy="22" r={6 + pulse * 3} fill={PALETTE.border} />
        <circle cx="22" cy="22" r="3" fill={PALETTE.bg} />
        <circle cx="34" cy="10" r="2.5" fill="#fff" />
      </g>
      <text
        x="76"
        y="50"
        fontFamily="Inter, Segoe UI, system-ui, sans-serif"
        fontSize="30"
        fontWeight="700"
        fill={PALETTE.ink}
      >
        camclave
      </text>
    </svg>
  );
};
