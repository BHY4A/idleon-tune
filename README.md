# IdleOn Tune

Unofficial performance and quality-of-life mod for the Steam version of **Legends of Idleon** (Windows).

It does not touch game logic, saves or networking (Firebase, other players). Every change targets the engine layer (Lime/OpenFL/Stencyl) or the Electron shell around the game.

> **Use at your own risk.** This modifies the game client. Lavaflame2's terms may not allow that. The mod gives no gameplay advantage, but a ban cannot be ruled out. Not affiliated with Lavaflame2.

## Results

Same account, same map (W2 pirates), AUTO on, RTX 3060 Ti, 1920×1080 at 300 Hz:

| | Stock game | Mod, stock Electron 11 | Mod + Electron 44 |
|---|---|---|---|
| FPS | 33.7 | 35–47 | **61–62** (at the 60 FPS cap) |
| Median frame time | 25.5 ms | 18–24 ms | **7–8 ms** |
| 99th percentile | 97 ms | 49–80 ms | **31–33 ms** |
| Frames over 50 ms per 20 s | 50 | 9–40 | **0–1** |
| CPU, all game processes | 225–245 % of a core | 145 % | 155 % |

Fullscreen is sharp instead of blurry: the game is drawn at screen resolution instead of being stretched from 960×540.

## Two ways to use it

You need [Python 3](https://www.python.org/downloads/) on Windows. Close the game first.

### 1. Patch the Steam game (stable)

- `install.bat` installs (run it again after editing `config.json`).
- `restore.bat` puts the original back.
- `python patcher.py status` shows the current state.

The original archive is kept as `resources\app.asar.vanilla`, and every install starts from it. A Steam update replaces the archive and removes the mod; run `install.bat` again and the update is picked up automatically. If the game is not in the default Steam folder:

```
install.bat --game "D:\SteamLibrary\steamapps\common\Legends of Idleon"
```

### 2. Run the game on Electron 44 (experimental, much faster)

`build-electron44.bat` builds a separate copy of the game on a current Electron and puts an **IdleOn (Tune)** shortcut on the desktop. The Steam installation is not modified.

- Electron 44.8.0 comes from the official GitHub release; its SHA-256 is checked against the release's `SHASUMS256.txt`.
- [steamworks.js](https://github.com/ceifa/steamworks.js) 0.4.0 comes from npm and is checked against its integrity hash. It replaces the game's old `greenworks` Steam module: Steam sign-in, rich presence, achievements, Steam purchases, Steam Deck keyboard.
- The copy is built in `%LOCALAPPDATA%\IdleOnTune\runtime` and uses its own browser profile, `legends-of-idleon-modern`. A newer Chromium upgrades a profile in place, so the stock game must not share one.
- On the first build, the stock game's profile is copied over so you stay signed in with the same account.
- Run `build-electron44.bat` again after a game update. Remove the copy with `python runtime.py remove`.

**About signing in:** "Sign in with Steam" logs into the account `steam_<SteamID>`. If your account is a Google or e-mail one, that is a *different, empty* account. Use the copied profile, or sign in the same way you normally do.

Do not run the stock game and the Electron 44 copy at the same time on one account.

**Steam overlay and playtime:** the Steam overlay is only injected into processes Steam starts itself, so the desktop shortcut gets no overlay. To launch the Electron 44 copy from Steam instead, set the game's launch options (Steam → Legends of Idleon → Properties → Launch Options) to:

```
"C:\Users\<you>\AppData\Local\IdleOnTune\runtime\LegendsOfIdleon.exe" %command%
```

`build-electron44.bat` prints this line with your real path at the end. The copy ignores the extra argument Steam appends (tested).

## What the patches do

| Patch (`config.json` key) | What and why |
|---|---|
| FPS cap (`fpsLimit`, default 60) | The game asks for 65 FPS, but Lime treats 60 and above as uncapped, so the game redraws at the monitor's refresh rate. Stencyl runs game logic in fixed 10 ms steps of real time, so the cap only changes how often the same state is redrawn. `0` keeps the stock behaviour; `100` matches the logic rate. |
| Animation filter cache (`filterCache`) | Stencyl colour-filters animation frames on the CPU (`getImageData` plus a per-pixel loop) and keeps the result per animation instance, dropping it on every animation switch. A shared cache keyed by source frame and colour matrix removes the repeated work. On a real account this took `applyFilters` from about 4 % of frame time to nothing. |
| WebGL renderer (`renderer`: `"canvas"` default, or `"webgl"`, experimental) | The game was built with OpenFL's `canvas` define, which cut the WebGL branch out of `Stage.__createRenderer`, but OpenFL 9.2.0's `OpenGLRenderer`, `Context3D` and all `Context3D*` renderers are still in N.js. This puts the branch back as in OpenFL's source. OpenGLRenderer also smooths every texture whenever the stage is scaled, which blurred the pixel art at high-DPI scale; that is turned off so sprites stay as sharp as on Canvas. Measured on a real account, uncapped: WebGL 118–120 FPS, median 7.1–7.7 ms, 215–220 % CPU; Canvas 102–119 FPS, median 8.2–8.7 ms, better 99th percentile, 153 % CPU. Canvas stays the default. |
| WebGL uniform cache (`glUniformCache`, WebGL only) | OpenFL re-sends every shader parameter before every object. Uniforms keep their value until set, so identical re-sends are skipped. Not measured yet. |
| Sharp fullscreen (`sharpRendering`, `renderScale`, `maxRenderScale`) | Turns on Lime's high-DPI mode with a scale that matches the screen. Mouse coordinates are unaffected. |
| Skip drawing while minimized (`skipHiddenRendering`) | A minimized game keeps playing (combat, AFK) but stops drawing. Idle time of the render process went from 17 % to 60 %. |
| Game loop while hidden | A hidden page gets no animation frames. Stock Electron 11 works around this with `incrementCapturerCount`, which current Electron removed. While hidden, the loop runs on a timer instead. |
| F3 (`fpsOverlayHotkey`) | Shows the frames the game actually draws (not browser repaints), the number of engine timers and the JS heap size. |
| F11 / Alt+Enter (`fullscreenHotkey`) | Fullscreen. The game's 32 px title bar is hidden in fullscreen, so the game fills the whole screen instead of being letterboxed. |
| F12 (`screenshotHotkey`) | Full-resolution screenshot to `Pictures\IdleOn`. |
| Remember window (`rememberWindow`) | Size, position, maximized and fullscreen state. |
| Broken assets (`fixBrokenAssets`) | The CSS points at `/static/...`, which resolves to `C:\static\...` under `file://`, so the custom cursor and the sign-in fonts never load. |
| No analytics (`disableAnalytics`, off by default) | Skips loading Google Analytics, which the game initialises but never sends events to. Tested: the Google Tag Manager request is gone and sign-in is restored exactly as without it. |
| Steam overlay (`steamOverlayFix`) | The game's own flags for the Steam overlay (`--in-process-gpu`). |
| `extraChromiumFlags` | Extra Chromium switches, for example `["ignore-gpu-blocklist"]`. |

Each patch is tied to an exact piece of the shipped code. If a game update changes that code, the installer skips the patch and says so instead of guessing.

## What was tested

- On the Steam game and on the Electron 44 copy, with a real account: FPS, frame times and CPU in combat, sign-in, fullscreen screenshots.
- On a copy of the game without signing in: each patch on its own, F11/Alt+Enter/F12, window memory, minimize and restore.
- Electron 44 copy: launched with Steam's extra launch argument, fullscreen without title bar, `disableAnalytics`, the WebGL renderer on a real account.
- Not tested: the Steam overlay itself (needs the launch option above, then Shift+Tab), Steam purchases on Electron 44 (needs a real purchase; the purchase callback is registered the same way, but a real purchase has not been made), `glUniformCache`.

## What did not work

- **Faster engine timer list**: Stencyl walks thousands of timers 100 times a second and removes finished ones with `indexOf` + `splice`. Two versions of a one-pass replacement passed synthetic tests but broke the real game during sign-in (frozen game loop). Removed.
- **Deferred local save**: moving Stencyl's local save write (~40 ms) to idle time made the game request saves over and over and froze it. The game relies on the save finishing immediately. Removed.
- The save itself (about every 10 s) and Stencyl's per-actor timers remain the main sources of occasional long frames; they are game code.

## How it works

`asarlib.py` reads and writes Electron `.asar` archives. `patches.py` holds the text patches. `patcher.py` installs them into the Steam game. `runtime.py` builds the Electron 44 copy. The `mod/` folder has the code injected into the game page and the main process, plus the `greenworks` shim.

## License

MIT for the code in this repository; see `LICENSE`. Legends of Idleon is © Lavaflame2. This repository contains no game files or assets; patches only carry short anchor snippets used to locate code.
