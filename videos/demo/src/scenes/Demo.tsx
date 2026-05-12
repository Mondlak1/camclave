import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  Sequence,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {PreviewWindow} from '../components/PreviewWindow';
import {SyntheticMultimeter} from '../components/SyntheticMultimeter';
import {Terminal, TermLine} from '../components/Terminal';
import {AgentReply} from '../components/AgentReply';
import {PALETTE} from '../palette';

// All offsets in frames (30 fps -> 1s = 30 frames).
// Scene timing legend:
//   0   : terminal slides in
//   12  : user types `camclave start`
//   54  : preview window slides in (camera turns on)
//   90  : user types `camclave capture --reason "..."`
//   168 : capture fires → flash + PNG path appears
//   192 : agent reply slides up
export const DemoScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  // Lines for the terminal — paced so each command finishes typing
  // BEFORE the next event fires.
  const lines: TermLine[] = [
    {kind: 'cmd', text: 'camclave start --device 0 --ttl 15m', typeAt: 12, typeOverFrames: 32},
    {
      kind: 'output',
      text: 'camclave: preview started — device 0, ttl 900s, pid 9942',
      typeAt: 50,
      color: PALETTE.termOk,
    },
    {
      kind: 'cmd',
      text: 'camclave capture --reason "read the multimeter LCD"',
      typeAt: 90,
      typeOverFrames: 70,
    },
    {
      kind: 'path',
      text: 'C:/Users/jack/.camclave/captures/frame-20260512T134207.png',
      typeAt: 168,
    },
  ];

  // Preview window slides in around frame 54
  const previewEnter = spring({
    frame: frame - 54,
    fps,
    config: {damping: 22},
    durationInFrames: 24,
  });
  const previewOpacity = interpolate(previewEnter, [0, 1], [0, 1]);
  const previewY = interpolate(previewEnter, [0, 1], [40, 0]);

  // Capture happens at frame 168 (when the path appears in the terminal)
  const FLASH_AT = 168;
  const capturing = frame >= FLASH_AT && frame < FLASH_AT + 30;
  const ttlRemaining = Math.max(0, 15 * 60 - Math.floor(frame / fps));
  const ttlStr = `${String(Math.floor(ttlRemaining / 60)).padStart(2, '0')}:${String(ttlRemaining % 60).padStart(2, '0')}`;

  return (
    <AbsoluteFill style={{background: PALETTE.bg}}>
      {/* Subtle vignette */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background:
            'radial-gradient(ellipse at center, transparent 0%, rgba(0,0,0,0.5) 100%)',
        }}
      />
      {/* Two-column layout: terminal left, preview right */}
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 60,
          padding: '0 60px',
        }}
      >
        {/* Terminal */}
        <div>
          <Terminal lines={lines} width={760} />
        </div>

        {/* Preview window + agent reply column */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 28,
            alignItems: 'flex-start',
          }}
        >
          <div
            style={{
              opacity: previewOpacity,
              transform: `translateY(${previewY}px)`,
            }}
          >
            <PreviewWindow
              flashAt={FLASH_AT}
              mode={capturing ? 'capturing' : 'live'}
              reason={capturing ? 'read the multimeter LCD' : undefined}
              ttl={ttlStr}
              capturesCount={frame >= FLASH_AT + 10 ? 1 : 0}
            >
              <SyntheticMultimeter />
            </PreviewWindow>
          </div>
          <AgentReply
            startAt={192}
            text="Multimeter reads 4.96 V DC. Within ±2% of the 5 V you expected — bus voltage looks good."
          />
        </div>
      </div>
    </AbsoluteFill>
  );
};
