# Desktop Tidy Master

A prank desktop tidying tool. Click a button to pretend to "tidy" your desktop — after a progress bar animation, it hides all your desktop icons beneath the window.

## Features

- **Rainbow Title** — Title text rendered with rainbow gradient colors (red to violet) in IDLE state
- **Progress Bar Animation** — 4-step status rotation with randomized duration (4-7 seconds), faking real work
- **Icon Hiding** — After the progress bar completes, all desktop icons are neatly arranged and hidden beneath the window
- **Always-on-Top & Anti-Minimize** — Window stays on top after completion; minimization is blocked and auto-restored
- **Drag Follow** — After dragging the window, icons automatically re-align beneath it
- **Language Switching (Chinese/English)** — Real-time UI language toggle via menu bar
- **Auto-Arrange Detection** — On startup, detects if "Auto arrange icons" is enabled on the desktop and shows a warning dialog

## Usage

```bash
python desktop_tidy.py
```

## Requirements

- Windows 10 / Windows 11
- Python 3.10+

## Dependencies

Zero third-party dependencies. Uses only the Python standard library:

| Module | Purpose |
|--------|---------|
| `tkinter` / `tkinter.ttk` | GUI |
| `ctypes` | Windows API calls |
| `random` | Randomized progress bar duration |
| `math` | Icon grid layout calculation |
| `locale` | System language detection |
| `winreg` | Registry access (auto-arrange detection) |

## Warning

**This software moves your desktop icons and does NOT restore them!** Before closing the window, make sure you have manually dragged the icons back to their original positions, or be aware of where they are. The program does not restore icon positions on exit.

## License

MIT License. Copyright (c) 2026 OrangeNeko.
