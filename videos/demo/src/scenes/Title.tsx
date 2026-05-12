import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {PALETTE} from '../palette';

// ANSI-shadow figlet font for "camclave". Each glyph uses Unicode block
// characters so it reads as a heavy, modern wordmark at video scale —
// not the spindly look you get from old-school standard figlet.
const ASCII_LINES = [
  ' ██████╗ █████╗ ███╗   ███╗ ██████╗██╗      █████╗ ██╗   ██╗███████╗',
  '██╔════╝██╔══██╗████╗ ████║██╔════╝██║     ██╔══██╗██║   ██║██╔════╝',
  '██║     ███████║██╔████╔██║██║     ██║     ███████║██║   ██║█████╗  ',
  '██║     ██╔══██║██║╚██╔╝██║██║     ██║     ██╔══██║╚██╗ ██╔╝██╔══╝  ',
  '╚██████╗██║  ██║██║ ╚═╝ ██║╚██████╗███████╗██║  ██║ ╚████╔╝ ███████╗',
  ' ╚═════╝╚═╝  ╚═╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝',
];

export const TitleScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  // Tagline appears after the ASCII art is fully revealed
  const tagEnter = spring({
    frame: frame - 30,
    fps,
    config: {damping: 18},
  });
  const tagOpacity = interpolate(tagEnter, [0, 1], [0, 1]);
  const tagY = interpolate(tagEnter, [0, 1], [12, 0]);

  return (
    <AbsoluteFill
      style={{
        background: PALETTE.bg,
        alignItems: 'center',
        justifyContent: 'center',
        gap: 40,
      }}
    >
      {/* Faint background-grid noise so the title doesn't sit on dead black */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background:
            'repeating-linear-gradient(0deg, transparent 0 2px, rgba(255,255,255,0.012) 2px 3px)',
          pointerEvents: 'none',
        }}
      />

      {/* ASCII wordmark — reveals line by line with a slight horizontal
          shift for kinetic flavor. Each line gets a gradient fill via
          background-clip:text so the title doesn't read as flat. */}
      <pre
        style={{
          fontFamily: '"Cascadia Mono", Consolas, "Courier New", monospace',
          fontSize: 30,
          lineHeight: 1.05,
          margin: 0,
          letterSpacing: 0,
          fontWeight: 700,
          whiteSpace: 'pre',
        }}
      >
        {ASCII_LINES.map((line, i) => {
          const enter = spring({
            frame: frame - i * 3,
            fps,
            config: {damping: 20},
            durationInFrames: 22,
          });
          const opacity = interpolate(enter, [0, 1], [0, 1]);
          const translateX = interpolate(enter, [0, 1], [-18, 0]);
          // Two-stop gradient — same crimson→purple as the original logo.
          return (
            <div
              key={i}
              style={{
                opacity,
                transform: `translateX(${translateX}px)`,
                background: `linear-gradient(90deg, ${PALETTE.border} 0%, ${PALETTE.termPrompt} 100%)`,
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
                color: 'transparent',
              }}
            >
              {line}
            </div>
          );
        })}
      </pre>

      {/* Tagline */}
      <div
        style={{
          opacity: tagOpacity,
          transform: `translateY(${tagY}px)`,
          textAlign: 'center',
        }}
      >
        <div
          style={{
            color: PALETTE.ink,
            fontFamily: 'Inter, "Segoe UI", sans-serif',
            fontSize: 32,
            fontWeight: 600,
            letterSpacing: 0.3,
          }}
        >
          Connect your camera to an AI agent.
        </div>
        <div
          style={{
            color: PALETTE.accent,
            fontFamily: 'Inter, "Segoe UI", sans-serif',
            fontSize: 20,
            fontStyle: 'italic',
            marginTop: 8,
          }}
        >
          Solve hardware in real life.
        </div>
      </div>
    </AbsoluteFill>
  );
};
