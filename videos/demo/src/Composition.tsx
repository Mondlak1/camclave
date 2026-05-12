import React from 'react';
import {AbsoluteFill, Series} from 'remotion';
import {TitleScene} from './scenes/Title';
import {DemoScene} from './scenes/Demo';
import {SafetyScene} from './scenes/Safety';
import {OutroScene} from './scenes/Outro';

// Scene durations in frames at 30 fps.
// Total = 90 + 240 + 90 + 90 = 510 frames = 17s
// Demo is the long beat because the typing has to land before the capture.
const TITLE_FRAMES = 90;
const DEMO_FRAMES = 240;
const SAFETY_FRAMES = 90;
const OUTRO_FRAMES = 90;

export const Demo: React.FC = () => {
  return (
    <AbsoluteFill>
      <Series>
        <Series.Sequence durationInFrames={TITLE_FRAMES}>
          <TitleScene />
        </Series.Sequence>
        <Series.Sequence durationInFrames={DEMO_FRAMES}>
          <DemoScene />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SAFETY_FRAMES}>
          <SafetyScene />
        </Series.Sequence>
        <Series.Sequence durationInFrames={OUTRO_FRAMES}>
          <OutroScene />
        </Series.Sequence>
      </Series>
    </AbsoluteFill>
  );
};

export const TOTAL_FRAMES = TITLE_FRAMES + DEMO_FRAMES + SAFETY_FRAMES + OUTRO_FRAMES;
