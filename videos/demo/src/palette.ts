// Mirrors PALETTE in skill/scripts/preview_daemon.py so the video matches
// the actual app exactly. If the app's palette changes, change this too.
export const PALETTE = {
  border: '#b11226',      // deep crimson safety border
  borderInner: '#7a0c1a', // thin bevel
  panel: '#1c1418',       // warm near-black interior
  panelAlt: '#251a1f',    // raised footer band
  ink: '#f5e8e3',         // primary cream text
  inkDim: '#c4b9b3',      // muted warm-grey text
  accent: '#d4a574',      // warm gold/rose wordmark + TTL
  dotLo: '#ff6b6b',
  dotHi: '#ffd1d1',
  bg: '#0b0b10',          // page background (matches logo.svg)
  termBg: '#101015',
  termInk: '#e8e0d8',
  termPrompt: '#7c3aed',  // purple prompt (Claude-coded)
  termOk: '#10a37f',      // green ok messages
  termPath: '#d4a574',
};
