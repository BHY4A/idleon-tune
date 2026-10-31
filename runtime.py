"""IdleOn Tune - builds a copy of the game that runs on a current Electron.

    python runtime.py build   [--game DIR] [--dest DIR]
    python runtime.py remove  [--dest DIR]

The Steam installation is not modified. The copy lives in --dest (default
%LOCALAPPDATA%\\IdleOnTune\\runtime) and gets a desktop shortcut. Run build
again after a game update.

What it does:
  1. downloads Electron (official GitHub release, SHA-256 checked against the
     release's SHASUMS256.txt) and steamworks.js (npm, integrity checked);
  2. lays them out as the game folder, takes the game's current app.asar and
     applies all IdleOn Tune patches with modernRuntime on;
  3. copies the stock game's browser profile once, so you stay signed in with
     the same account (see README: "Sign in with Steam" is a different account
     if yours is a Google/e-mail one).
"""
import argparse
import base64
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

import asarlib
import patcher
import patches

ELECTRON_VERSION = "44.8.0"
STEAMWORKS_VERSION = "0.4.0"
APP_ID = "1476970"

APPDATA = os.environ.get("APPDATA", "")
LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
DEFAULT_DEST = os.path.join(LOCALAPPDATA, "IdleOnTune", "runtime")
PROFILE = os.path.join(APPDATA, "legends-of-idleon")
MODERN_PROFILE = PROFILE + "-modern"
CACHE = os.path.join(LOCALAPPDATA, "IdleOnTune", "downloads")
PROFILE_SKIP = {"Cache", "Code Cache", "GPUCache", "DawnCache", "DawnGraphiteCache", "DawnWebGPUCache",
                "GrShaderCache", "ShaderCache", "Crashpad", "Service Worker", "LOCK", "idleontune-window.json"}


def fetch(url):
    with urllib.request.urlopen(url) as r:
        return r.read()


def cached(name, url):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        print("Downloading " + url)
        data = fetch(url)
        with open(path + ".part", "wb") as fh:
            fh.write(data)
        os.replace(path + ".part", path)
    with open(path, "rb") as fh:
        return fh.read()


def get_electron():
    base = "https://github.com/electron/electron/releases/download/v%s/" % ELECTRON_VERSION
    name = "electron-v%s-win32-x64.zip" % ELECTRON_VERSION
    data = cached(name, base + name)
    sums = fetch(base + "SHASUMS256.txt").decode()
    expected = next((line.split()[0] for line in sums.splitlines() if line.endswith(name)), None)
    if hashlib.sha256(data).hexdigest() != expected:
        os.remove(os.path.join(CACHE, name))
        sys.exit("Electron download failed the SHA-256 check; run build again.")
    return data


def get_steamworks():
    meta = json.loads(fetch("https://registry.npmjs.org/steamworks.js/" + STEAMWORKS_VERSION))
    url, integrity = meta["dist"]["tarball"], meta["dist"]["integrity"]
    data = cached("steamworks.js-%s.tgz" % STEAMWORKS_VERSION, url)
    algo, digest = integrity.split("-", 1)
    if base64.b64encode(hashlib.new(algo, data).digest()).decode() != digest:
        os.remove(os.path.join(CACHE, "steamworks.js-%s.tgz" % STEAMWORKS_VERSION))
        sys.exit("steamworks.js download failed the integrity check; run build again.")
    return data


def running(dest):
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq LegendsOfIdleon.exe", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    return "LegendsOfIdleon.exe" in out


def copy_profile():
    if os.path.isdir(MODERN_PROFILE):
        return
    if not os.path.isdir(PROFILE):
        print("No stock game profile found; you will sign in from scratch.")
        return
    shutil.copytree(PROFILE, MODERN_PROFILE, ignore=lambda d, names: [n for n in names if n in PROFILE_SKIP])
    print("Copied the stock game profile (sign-in) to " + MODERN_PROFILE)


def desktop_dir():
    # The Desktop may be redirected (OneDrive), so ask Windows for it.
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "[Console]::OutputEncoding=[Text.Encoding]::UTF8;[Environment]::GetFolderPath('Desktop')"],
                         capture_output=True, text=True, encoding="utf-8").stdout.strip()
    return out if os.path.isdir(out) else None


def shortcut(dest, game):
    desktop = desktop_dir()
    if not desktop:
        return
    link = os.path.join(desktop, "IdleOn (Tune).lnk")
    exe = os.path.join(dest, "LegendsOfIdleon.exe")
    icon = os.path.join(game, "LegendsOfIdleon.exe")
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:IT_LINK);$s.TargetPath=$env:IT_EXE;"
          "$s.WorkingDirectory=$env:IT_DEST;$s.IconLocation=$env:IT_ICON+',0';$s.Save()")
    env = dict(os.environ, IT_LINK=link, IT_EXE=exe, IT_DEST=dest, IT_ICON=icon)
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False, env=env)
    print("Desktop shortcut: " + link)


def build(game, dest, make_shortcut=True):
    src_asar = os.path.join(game, "resources", "app.asar")
    if not os.path.exists(src_asar):
        sys.exit("Game not found in " + game)
    vanilla = src_asar + ".vanilla"
    if os.path.exists(vanilla):
        src_asar = vanilla  # the Steam copy is modded by install.bat; start from the original
    elif patcher.is_modded(src_asar):
        sys.exit("The Steam game is modded but has no backup; verify the game files in Steam first.")
    if running(dest):
        sys.exit("Close the game first.")
    electron = get_electron()
    steamworks = get_steamworks()

    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)
    with zipfile.ZipFile(io.BytesIO(electron)) as z:
        z.extractall(dest)
    os.remove(os.path.join(dest, "resources", "default_app.asar"))
    os.replace(os.path.join(dest, "electron.exe"), os.path.join(dest, "LegendsOfIdleon.exe"))
    with open(os.path.join(dest, "steam_appid.txt"), "w") as fh:
        fh.write(APP_ID)
    modules = os.path.join(dest, "resources", "app.asar.unpacked", "node_modules")
    os.makedirs(modules)
    with tarfile.open(fileobj=io.BytesIO(steamworks)) as t:
        t.extractall(modules, filter="data")
    os.rename(os.path.join(modules, "package"), os.path.join(modules, "steamworks.js"))

    cfg = patcher.load_config()
    cfg["modernRuntime"] = True
    work = tempfile.mkdtemp(prefix="idleontune_")
    try:
        asarlib.extract(src_asar, work)
        for name, ok, note in patches.apply_all(work, cfg, patcher.VERSION):
            print(("  ok   " if ok else "  SKIP ") + name + (" - " + note if note else ""))
        asarlib.pack(work, os.path.join(dest, "resources", "app.asar"))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    copy_profile()
    if make_shortcut:
        shortcut(dest, game)
    print("Built IdleOn Tune %s on Electron %s in %s" % (patcher.VERSION, ELECTRON_VERSION, dest))
    print("To start it from Steam (overlay, playtime), set the game's launch options to:")
    print('    "%s" %%command%%' % os.path.join(os.path.abspath(dest), "LegendsOfIdleon.exe"))


def remove(dest):
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    desktop = desktop_dir()
    link = os.path.join(desktop, "IdleOn (Tune).lnk") if desktop else None
    if link and os.path.exists(link):
        os.remove(link)
    print("Removed " + dest + " (the copied profile stays in " + MODERN_PROFILE + ")")


def main():
    ap = argparse.ArgumentParser(description="IdleOn Tune: game copy on a current Electron")
    ap.add_argument("command", choices=["build", "remove"])
    ap.add_argument("--game", default=patcher.DEFAULT_GAME)
    ap.add_argument("--dest", default=DEFAULT_DEST)
    ap.add_argument("--config", help="alternative config.json")
    ap.add_argument("--no-shortcut", action="store_true")
    args = ap.parse_args()
    if args.config:
        patcher.CONFIG_PATH = args.config
    if args.command == "build":
        build(args.game, args.dest, not args.no_shortcut)
    else:
        remove(args.dest)


if __name__ == "__main__":
    main()
