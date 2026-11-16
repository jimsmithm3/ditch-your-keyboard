# Ditch Your Keyboard

Hands-free voice commands for GSPro. This is the desktop skeleton only: a PySide6 window loaded from a Qt Designer `.ui` file, plus a windowed PyInstaller exe.

> **Unofficial.** Ditch Your Keyboard is not made by, endorsed by, or affiliated with GSPro or its makers. GSPro is their product; this app only sends clicks and keys to it.

Runtime Qt binding is `PySide6_Essentials` (widgets and `QUiLoader`). The full `PySide6` metapackage also pulls Qt WebEngine, which this app does not use.

## Setup

Requires Python 3.14. On this machine that is:

`%LOCALAPPDATA%\Programs\Python\Python314\python.exe`

```powershell
cd C:\dev\ditch-your-keyboard
& "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe" -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

Working directory must be the project root (so `app` imports and `ui/` resolve).

```powershell
.\.venv\Scripts\python.exe main.py
```

Logs go to `logs\ditch-your-keyboard.log` (next to `ditch-your-keyboard.exe` when frozen).

The **Test wiring** button sets the status label to `Wiring OK`.

## PyCharm

1. Interpreter: `C:\dev\ditch-your-keyboard\.venv`
2. Run configuration: Script path `C:\dev\ditch-your-keyboard\main.py`, working directory `C:\dev\ditch-your-keyboard`
3. Edit layout in Qt Designer: `ui\main_window.ui`. The app loads it at runtime with `QUiLoader`. Do not compile `.ui` to `.py`.

## Build

Windowed onefile (`console=False`). No code signing.

```powershell
.\scripts\build_exe.ps1
```

Output: `dist\ditch-your-keyboard.exe`. The `.ui` file is bundled via `datas` in `ditch-your-keyboard.spec`.

## License

GNU General Public License v3.0 (GPL-3.0). See [LICENSE](LICENSE). Anyone who distributes this app, changed or not, must also give its source under the same license.
