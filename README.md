# QuirkCode

Windows desktop utility that generates a configurable, reversible activity workload inside an already-open **VS Code** or **Cursor** window for activity-tracker QA.

It does **not** open the IDE, create projects, save files, modify Git state, or touch tracker data.

## Requirements

- Windows 10 / Windows 11
- Python 3.11+ (for source runs)
- VS Code or Cursor already open with multiple files

> Packaging and live automation require Windows (`pywin32`). macOS/Linux can import most modules for syntax checks only; Start will refuse to run.

## Install (source)

```bat
cd AutoEvent
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Workflow

1. Open VS Code or Cursor and open several source files.
2. Launch `QuirkCode.exe` (or `python app.py`).
3. Confirm the IDE is detected (Refresh).
4. Choose duration, intensity, target, and feature flags.
5. Press **Start**.
6. Press **STOP** or wait for duration to elapse.
7. Review `logs/run_*_report.json` and the JSONL event log.

Emergency stop hotkey: **Ctrl+Shift+F12**.

PyAutoGUI failsafe: move the mouse to a screen corner to abort input.

## Configuration

`config.json` (next to the executable when frozen):

```json
{
  "duration_minutes": 30,
  "intensity": "medium",
  "target": "auto",
  "enable_mouse": true,
  "enable_keyboard": true,
  "enable_scrolling": true,
  "enable_tab_switching": true,
  "enable_terminal": false,
  "preserve_workspace": true,
  "random_seed": null
}
```

Intensity profiles: `low` / `medium` / `high` (pause ranges and sequence weights).

Terminal sequences use only `echo QA_TEST` when enabled.

## Build Windows `.exe`

**This project must be built on a Windows PC.** A Mac/Linux machine cannot produce a working `QuirkCode.exe`.

### One-click (recommended)

1. Copy this whole project folder onto a Windows 10/11 machine.
2. Double-click **`build.bat`**.
3. When it finishes, zip and share:

```text
dist\QuirkCode_Share\
  QuirkCode.exe
  config.json
  assets\quirkcode.ico
  logs\
```

Recipients only need `QuirkCode_Share` — no Python install required.

### Manual

```bat
pip install -r requirements.txt
pyinstaller build_windows.spec
```

Output: `dist\QuirkCode.exe` (uses `assets\quirkcode.ico`)

## Build installer (optional)

Requires [Inno Setup](https://jrsoftware.org/isinfo.php) after the exe is built:

```bat
ISCC installer\QuirkCode.iss
```

Output: `dist\installer\QuirkCodeSetup.exe`

Recommended install layout:

```text
QuirkCode\
  QuirkCode.exe
  config.json
  assets\quirkcode.ico
  logs\
```

## Safety / workspace integrity

- Temporary edits insert `QA_TEST_MARKER` then undo (`Ctrl+Z`).
- Save / new-file / close-window hotkeys are blocked.
- On stop or duration end: release modifiers and mouse buttons, undo flood, Escape to dismiss find/terminal UI.
- Focus loss pauses input until the IDE is foreground again (no blind typing into other apps).

## QA checklist (testing the tester)

1. Run a **2-minute** test with all features enabled (except terminal if undesired).
2. Confirm counters: keyboard, mouse, scroll, tab switches, temporary edits all **> 0**.
3. In the IDE workspace run `git diff` — expect **no** unintended file changes.
4. Stop mid-run — IDE should not have stuck Ctrl/Shift/Alt or mouse buttons.
5. Switch away from the IDE mid-run — status becomes FocusLost; return focus resumes.

## Project layout

```text
app.py
config.py
controller.py
window_manager.py
input_engine.py
mouse_engine.py
keyboard_engine.py
workload.py
actions.py
logger.py
safety.py
ui.py
config.json
assets/quirkcode.png
assets/quirkcode.ico
assets/quirkcode_256.png
build_windows.spec
installer/QuirkCode.iss
requirements.txt
logs/
```

## License / intent

Internal QA tooling only. Do not use to bypass monitoring, falsify tracker data, or alter agent logs.
