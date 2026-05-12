import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {PALETTE} from '../palette';

/**
 * Agent-reply bubble that slides up and fades in. Used after a capture
 * to show what the AI agent "saw" in the frame.
 */
export const AgentReply: React.FC<{
  text: string;
  startAt: number;
  agent?: string;
}> = ({text, startAt, agent = 'Claude'}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const local = frame - startAt;
  if (local < 0) return null;

  const enter = spring({frame: local, fps, config: {damping: 18}});
  const opacity = interpolate(enter, [0, 1], [0, 1]);
  const translate = interpolate(enter, [0, 1], [16, 0]);

  return (
    <div
      style={{
        opacity,
        transform: `translateY(${translate}px)`,
        background: '#11111a',
        border: '1px solid #2a2a35',
        borderRadius: 12,
        padding: '14px 18px',
        boxShadow: '0 20px 40px rgba(0, 0, 0, 0.4)',
        maxWidth: 540,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginBottom: 6,
        }}
      >
        <div
          style={{
            width: 18,
            height: 18,
            borderRadius: 4,
            background: PALETTE.termPrompt,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontFamily: 'Inter, sans-serif',
            fontWeight: 800,
            color: '#fff',
            fontSize: 11,
          }}
        >
          C
        </div>
        <span
          style={{
            color: PALETTE.inkDim,
            fontFamily: 'Inter, sans-serif',
            fontSize: 11,
            letterSpacing: 1,
            fontWeight: 700,
            textTransform: 'uppercase',
          }}
        >
          {agent}
        </span>
      </div>
      <div
        style={{
          color: PALETTE.ink,
          fontFamily: 'Inter, sans-serif',
          fontSize: 17,
          lineHeight: 1.45,
        }}
      >
        {text}
      </div>
    </div>
  );
};
