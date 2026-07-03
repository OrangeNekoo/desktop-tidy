# Desktop Tidy Master

A prank app. Click a button, watch a progress bar for a few seconds, and all your desktop icons disappear — neatly tucked under the window where you can't find them.

## What it does

Open it up, you get a rainbow-colored "Click the button to start tidying" label. Click, and a progress bar runs for 4–7 seconds, cycling through "Preparing to tidy...", "Analyzing desktop...", "Invoking Homo Silver Dream LLM...", "Tidying complete!". Then the window shrinks to exactly cover the icons, and they're gone.

The window stays on top, won't minimize (it bounces right back), and closing the app does not restore your icons. You figure it out.

If "Auto arrange icons" is turned on, it warns you to disable it first.

Menu bar has Chinese/English switching.

## Running it

```bash
python desktop_tidy.py
```

Windows 10 / 11, Python 3.10+. Zero third-party deps — just tkinter, ctypes, winreg, all standard library.

## Disclaimer

This app really moves your desktop icons and does not put them back on exit. Don't open it on your work machine unless you know what you're doing.

## License

MIT
