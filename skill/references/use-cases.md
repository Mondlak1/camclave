# Use-case patterns

Patterns for common tasks. The user-facing examples sit in the top-level `README.md`; this file is the agent's playbook.

## Single-frame inspection

User: "Is the LED on pin D5 lit?"

```
camclave status                # confirm session
camclave capture               # -> /path/to/frame.png
# Read the PNG with your image tool, then answer.
```

Frame the question before capturing: "I'll grab one frame, please point the camera at the breadboard near D5."

## Hardware troubleshooting with multiple angles

Ask the user to move/rotate between captures. Don't burst-capture — wait for confirmation between angles.

## Periodic monitoring (3D prints, plants, posture)

```
camclave snapshots --every 30s --duration 4h --out /tmp/print.png
```

Read `/tmp/print.png` whenever you want a fresh look — typically when the user pings you ("how is it going?") or on your own when you're actively babysitting the task. Don't read more often than the snapshot interval — the file won't have changed.

When done:

```
camclave snapshots-stop
```

## Reading instruments / displays / handwriting

Single capture is usually enough. Ask the user to hold the camera steady and remove glare before you call `capture`. If the first frame is unreadable, ask them to adjust — don't burst.

## What to say to the user

- Before capture: name what you're looking for.
- After capture: describe what you saw, even briefly. This confirms to the user that the flash they saw was the agent and not something else.
- Before snapshot mode: confirm the interval and duration, and that the file path is fine.
