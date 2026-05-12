# camclave demo video

Programmatic source for the README's demo video, built with [Remotion](https://www.remotion.dev).

## Why programmatic

The video shows camclave's UI (preview window, terminal, agent reply) using the real palette/logo from `skill/scripts/preview_daemon.py`, but the "camera content" inside the preview window is a **synthetic SVG multimeter** — no real webcam footage. That way the published video doesn't leak anything from anyone's actual room, and the demo is reproducible from scratch.

## Run / preview

```bash
cd videos/demo
npm install
npm start           # opens Remotion Studio at http://localhost:3000
```

## Render

```bash
npm run build       # renders out/demo.mp4 at 1920x1080
```

Copy the result into `../../assets/demo.mp4` to publish:

```bash
cp out/demo.mp4 ../../assets/demo.mp4
```

## Structure

```
src/
  index.ts              Remotion entry
  Root.tsx              Composition registration
  Composition.tsx       Top-level Series of scenes
  palette.ts            Shared colors (mirrors preview_daemon.py PALETTE)
  scenes/
    Title.tsx           Logo + tagline (3s)
    Demo.tsx            Terminal + preview window + agent reply (8s)
    Safety.tsx          Three audit-verified safety cards (3s)
    Outro.tsx           Install commands + GitHub URL (3s)
  components/
    PreviewWindow.tsx   Visual replica of the tkinter preview window
    Terminal.tsx        Typed-command terminal with prompt
    AgentReply.tsx      Sliding agent-reply bubble
    SyntheticMultimeter.tsx  SVG multimeter (the safe "camera content")
```

If `skill/scripts/preview_daemon.py`'s `PALETTE` changes, update `src/palette.ts` to match.
