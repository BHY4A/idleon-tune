@echo off
setlocal
cd /d "%~dp0"
title IdleOn Tune

rem ===========================================================================
rem  IdleOn Tune - one file for everything.
rem  Edit the settings below, save, and run this file again to apply them.
rem  Close the game before running it.
rem ===========================================================================

rem ---- Engine ---------------------------------------------------------------

rem Electron version for the fast copy (option 1). Any release from
rem github.com/electron/electron/releases works; the download is checked
rem against that release's official SHA-256 list. See README for the choice.
set IT_electronVersion=44.10.1

rem ---- Performance ----------------------------------------------------------

rem Frame cap. 100 matches the game's logic rate (it runs 100 steps a second),
rem so every frame shows exactly one step: the smoothest motion. 60 uses less
rem CPU. 0 = no cap (stock behaviour: redraws at your monitor's refresh rate).
set IT_fpsLimit=100

rem How frames are paced. vsync = draw on every N-th monitor refresh (even
rem frame intervals). timer = the engine's own time-based cap.
set IT_framePacing=vsync

rem Cache colour-filtered animation frames instead of recomputing them on the
rem CPU over and over. Big win in busy fights.
set IT_filterCache=true

rem Stop drawing while the window is minimized. The game keeps playing.
set IT_skipHiddenRendering=true

rem Young-generation size for the JavaScript engine, in MB. Bigger = fewer
rem small garbage collections = fewer micro-stutters. 0 = engine default.
set IT_v8SemiSpaceMB=64

rem Renderer: canvas (default, measured best) or webgl (experimental).
set IT_renderer=canvas

rem WebGL only: skip re-sending shader parameters that did not change.
set IT_glUniformCache=true

rem ---- Picture --------------------------------------------------------------

rem Draw the game at screen resolution instead of stretching 960x540.
set IT_sharpRendering=true

rem Render scale: auto (matches your screen) or a number such as 2.
set IT_renderScale=auto

rem Upper limit for the auto render scale (4K screens: 4 looks best, costs more).
set IT_maxRenderScale=3

rem ---- Window and hotkeys ---------------------------------------------------

rem F11 / Alt+Enter: fullscreen without the title bar.
set IT_fullscreenHotkey=true

rem F12: full-resolution screenshot to Pictures\IdleOn.
set IT_screenshotHotkey=true

rem F3: FPS, render scale, engine timers and memory.
set IT_fpsOverlayHotkey=true

rem Remember window size, position and fullscreen.
set IT_rememberWindow=true

rem ---- Other ----------------------------------------------------------------

rem Fix the custom cursor and sign-in fonts that never load in the stock game.
set IT_fixBrokenAssets=true

rem Do not load Google Analytics (the game never sends it events anyway).
set IT_disableAnalytics=false

rem The game's own Steam overlay switches (--in-process-gpu).
set IT_steamOverlayFix=true

rem Extra Chromium switches, comma separated. Leave empty if unsure.
set IT_extraChromiumFlags=

rem ===========================================================================
rem  Nothing to edit below this line.
rem ===========================================================================

set PY=
where py >nul 2>nul && set PY=py -3
if not defined PY where python >nul 2>nul && set PY=python
if not defined PY (
  echo Python 3 is needed and was not found.
  choice /c YN /m "Install Python now with winget"
  if errorlevel 2 goto :end
  winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
  echo Python installed. Close this window and run IdleOnTune.bat again.
  goto :end
)

echo.
echo  IdleOn Tune
echo  -----------
echo  1  Install / update  (recommended: fast Electron 44 copy + desktop shortcut)
echo  2  Patch the Steam game in place instead (stock engine, slower)
echo  3  Uninstall everything (remove the copy, restore the Steam game)
echo  4  Status
echo.
choice /c 1234 /n /m "Choose 1-4: "
if errorlevel 4 goto :status
if errorlevel 3 goto :uninstall
if errorlevel 2 goto :steam

:install
%PY% runtime.py build %*
goto :end

:steam
%PY% patcher.py install %*
goto :end

:uninstall
%PY% runtime.py remove
%PY% patcher.py restore
goto :end

:status
%PY% patcher.py status
if exist "%LOCALAPPDATA%\IdleOnTune\runtime\LegendsOfIdleon.exe" (
  echo Electron 44 copy: installed in %LOCALAPPDATA%\IdleOnTune\runtime
) else (
  echo Electron 44 copy: not installed
)

:end
echo.
pause
