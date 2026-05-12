import React from 'react';
import {interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {PALETTE} from '../palette';

/**
 * A macOS-style terminal window that types commands progressively.
 *
 * Each line is either:
 *   { kind: "cmd",    text: "camclave start" }                         // typed
 *   { kind: "output", text: "preview started — pid 9999" }             // appears whole
 *   { kind: "path",   text: "C:/Users/.../frame-...png" }              // colored
 *
 * Lines appear in order; `typeAt` is the frame offset when each line begins.
 */
export type TermLine =
  | {kind: 'cmd'; text: string; typeAt: number; typeOverFrames?: number}
  | {kind: 'output'; text: string; typeAt: number; color?: string}
  | {kind: 'path'; text: string; typeAt: number};

export const Terminal: React.FC<{lines: TermLine[]; title?: string; width?: number}> = ({
  lines,
  title = 'jack@desk — camclave',
  width = 720,
}) => {
  const frame = useCurrentFrame();

  return (
    <div
      style={{
        width,
        background: PALETTE.termBg,
        borderRadius: 10,
        overflow: 'hidden',
        boxShadow: '0 24px 56px rgba(0, 0, 0, 0.45)',
        border: '1px solid #1f1f24',
      }}
    >
      {/* Title bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '10px 14px',
          background: '#1a1a1f',
          borderBottom: '1px solid #2a2a30',
          gap: 8,
        }}
      >
        <Dot color="#ff5f56" />
        <Dot color="#ffbd2e" />
        <Dot color="#27c93f" />
        <span
          style={{
            color: '#8a8a90',
            fontFamily: 'Inter, sans-serif',
            fontSize: 12,
            marginLeft: 14,
            flex: 1,
            textAlign: 'center',
          }}
        >
          {title}
        </span>
      </div>
      {/* Body */}
      <div
        style={{
          padding: '18px 22px',
          fontFamily: '"Cascadia Mono", Consolas, "Courier New", monospace',
          fontSize: 16,
          lineHeight: 1.5,
          color: PALETTE.termInk,
          minHeight: 260,
        }}
      >
        {lines.map((line, idx) => {
          if (frame < line.typeAt) return null;
          return (
            <div key={idx} style={{whiteSpace: 'pre-wrap'}}>
              {line.kind === 'cmd' && (
                <CommandLine line={line} frame={frame} />
              )}
              {line.kind === 'output' && (
                <span style={{color: line.color ?? PALETTE.termInk}}>
                  {line.text}
                </span>
              )}
              {line.kind === 'path' && (
                <span style={{color: PALETTE.termPath}}>{line.text}</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const CommandLine: React.FC<{
  line: Extract<TermLine, {kind: 'cmd'}>;
  frame: number;
}> = ({line, frame}) => {
  const elapsed = frame - line.typeAt;
  const typeOver = line.typeOverFrames ?? Math.max(12, line.text.length * 2);
  const charsShown = Math.min(
    line.text.length,
    Math.floor(interpolate(elapsed, [0, typeOver], [0, line.text.length], {extrapolateRight: 'clamp'})),
  );
  const text = line.text.slice(0, charsShown);
  const showCursor = elapsed < typeOver || Math.floor(frame / 15) % 2 === 0;
  return (
    <>
      <span style={{color: PALETTE.termPrompt, fontWeight: 700}}>$ </span>
      <span>{text}</span>
      {showCursor && (
        <span style={{background: PALETTE.termInk, color: PALETTE.termBg, padding: '0 1px'}}>
          {' '}
        </span>
      )}
    </>
  );
};

const Dot: React.FC<{color: string}> = ({color}) => (
  <div
    style={{
      width: 12,
      height: 12,
      borderRadius: '50%',
      background: color,
      border: '1px solid rgba(0,0,0,0.25)',
    }}
  />
);
