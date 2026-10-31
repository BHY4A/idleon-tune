// IdleOn Tune, Electron main process side. Required from src/main/index.js.
// The patcher prepends `const TUNE_CONFIG = {...};` to this file.
"use strict";

const { app, screen } = require("electron");
const fs = require("fs");
const path = require("path");

const config = TUNE_CONFIG;
const stateFile = path.join(app.getPath("userData"), "idleontune-window.json");
const CHANNEL = "myRenderChannel";

function readState() {
  try {
    return JSON.parse(fs.readFileSync(stateFile, "utf8"));
  } catch (e) {
    return null;
  }
}

function writeState(state) {
  try {
    fs.writeFileSync(stateFile, JSON.stringify(state));
  } catch (e) {
    console.error(e);
  }
}

function onSomeDisplay(b) {
  return screen.getAllDisplays().some((d) => {
    const a = d.workArea;
    return b.x + 100 > a.x && b.y + 30 > a.y && b.x + 100 < a.x + a.width && b.y < a.y + a.height - 30;
  });
}

function applySwitches(app) {
  for (const flag of config.extraChromiumFlags || []) {
    app.commandLine.appendSwitch(flag);
  }
}

// Size/position for the BrowserWindow constructor.
function windowOptions(width, height) {
  const saved = config.rememberWindow ? readState() : null;
  if (saved && saved.bounds && onSomeDisplay(saved.bounds)) {
    return saved.bounds;
  }
  return { width, height };
}

function send(window, ...args) {
  if (!window.isDestroyed()) {
    window.webContents.send(CHANNEL, ["ITUNE", ...args]);
  }
}

function stamp() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}_${p(d.getHours())}-${p(d.getMinutes())}-${p(d.getSeconds())}`;
}

function screenshot(window) {
  window.webContents.capturePage().then((image) => {
    const dir = path.join(app.getPath("pictures"), "IdleOn");
    fs.mkdirSync(dir, { recursive: true });
    const file = path.join(dir, `IdleOn_${stamp()}.png`);
    fs.writeFileSync(file, image.toPNG());
    send(window, "toast", "Screenshot saved: Pictures\\IdleOn");
  }).catch((e) => console.error(e));
}

function attach(window) {
  const saved = config.rememberWindow ? readState() : null;
  if (saved) {
    if (saved.fullscreen) window.setFullScreen(true);
    else if (saved.maximized) window.maximize();
  }

  let saveTimer = null;
  const save = () => {
    if (!config.rememberWindow || window.isDestroyed()) return;
    writeState({
      bounds: window.getNormalBounds(),
      maximized: window.isMaximized(),
      fullscreen: window.isFullScreen(),
    });
  };
  const saveSoon = () => {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(save, 500);
  };
  for (const ev of ["resize", "move", "maximize", "unmaximize", "enter-full-screen", "leave-full-screen"]) {
    window.on(ev, saveSoon);
  }
  window.on("close", save);

  // Drawing is skipped while nobody can see the window; the game keeps running.
  // Polled: Windows does not always emit "restore" for a fullscreen window.
  if (config.skipHiddenRendering) {
    let hidden = false;
    const check = () => {
      if (window.isDestroyed()) return clearInterval(timer);
      const now = window.isMinimized() || !window.isVisible();
      if (now !== hidden) {
        hidden = now;
        send(window, "hidden", now);
      }
    };
    const timer = setInterval(check, 1000);
    for (const ev of ["minimize", "restore", "hide", "show"]) {
      window.on(ev, () => setTimeout(check, 50));
    }
  }

  window.webContents.on("before-input-event", (event, input) => {
    if (input.type !== "keyDown") return;
    const fullscreenKey = input.key === "F11" || (input.alt && input.key === "Enter");
    if (config.fullscreenHotkey && fullscreenKey) {
      event.preventDefault();
      window.setFullScreen(!window.isFullScreen());
    } else if (config.screenshotHotkey && input.key === "F12") {
      event.preventDefault();
      screenshot(window);
    }
  });
}

module.exports = { config, applySwitches, windowOptions, attach };
