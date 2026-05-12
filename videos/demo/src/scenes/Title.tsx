import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {loadFont as loadJetBrainsMono} from '@remotion/google-fonts/JetBrainsMono';
import {loadFont as loadInter} from '@remotion/google-fonts/Inter';
import {PALETTE} from '../palette';

// Explicit font loading so the rendered glyph widths are deterministic
// across machines (system fallbacks like Courier New were too wide and
// pushed the wordmark past the 1920px composition edge).
const jbm = loadJetBrainsMono('normal', {weights: ['700']});
const inter = loadInter('normal', {weights: ['400', '600', '700']});

const ASCII_LINES = [
  ' ██████╗ █████╗ ███╗   ███╗ ██████╗██╗      █████╗ ██╗   ██╗███████╗',
  '██╔════╝██╔══██╗████╗ ████║██╔════╝██║     ██╔══██╗██║   ██║██╔════╝',
  '██║     ███████║██╔████╔██║██║     ██║     ███████║██║   ██║█████╗  ',
  '██║     ██╔══██║██║╚██╔╝██║██║     ██║     ██╔══██║╚██╗ ██╔╝██╔══╝  ',
  '╚██████╗██║  ██║██║ ╚═╝ ██║╚██████╗███████╗██║  ██║ ╚████╔╝ ███████╗',
  ' ╚═════╝╚═╝  ╚═╝╚═╝     ╚═╝ ╚═════╝╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝',
];

// 68 glyphs wide. JetBrains Mono 700 weight has an em advance of ~0.6,
// so font_size * 68 * 0.6 = pixel width. We want comfortable margin in
// the 1920px composition — target ~1500px text width = 1500 / (68*0.6) = ~37,
// so fontSize 36 leaves ~200px of margin on each side and reads big.
const FONT_SIZE = 36;

export const TitleScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const tagEnter = spring({frame: frame - 30, fps, config: {damping: 18}});
  const tagOpacity = interpolate(tagEnter, [0, 1], [0, 1]);
  const tagY = interpolate(tagEnter, [0, 1], [12, 0]);

  return (
    <AbsoluteFill
      style={{
        background: PALETTE.bg,
        alignItems: 'center',
        justifyContent: 'center',
        gap: 48,
      }}
    >
      {/* Faint background-grid noise */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background:
            'repeating-linear-gradient(0deg, transparent 0 2px, rgba(255,255,255,0.012) 2px 3px)',
          pointerEvents: 'none',
        }}
      />

      <pre
        style={{
          fontFamily: `${jbm.fontFamily}, "JetBrains Mono", "Cascadia Mono", Consolas, monospace`,
          fontSize: FONT_SIZE,
          lineHeight: 1.0,
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
            fontFamily: `${inter.fontFamily}, "Inter", "Segoe UI", sans-serif`,
            fontSize: 36,
            fontWeight: 600,
            letterSpacing: 0.3,
          }}
        >
          Connect your camera to an AI agent.
        </div>
        <div
          style={{
            color: PALETTE.accent,
            fontFamily: `${inter.fontFamily}, "Inter", "Segoe UI", sans-serif`,
            fontSize: 22,
            fontStyle: 'italic',
            marginTop: 10,
          }}
        >
          Solve hardware in real life.
        </div>
      </div>
    </AbsoluteFill>
  );
};
