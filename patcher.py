"""IdleOn Tune - installs/removes the mod into Legends of Idleon (Steam, Windows).

    python patcher.py install [--game DIR]
    python patcher.py restore [--game DIR]
    python patcher.py status  [--game DIR]

The untouched game archive is kept as resources/app.asar.vanilla. Every install
rebuilds from that copy, so installs never stack. After a Steam update the new
archive is detected and becomes the new vanilla copy.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile

import asarlib
import patches

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Legends of Idleon"
VERSION = "1.1.0"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def paths(game):
    res = os.path.join(game, "resources")
    return {
        "asar": os.path.join(res, "app.asar"),
        "vanilla": os.path.join(res, "app.asar.vanilla"),
        "state": os.path.join(res, "idleontune.json"),
    }


def load_state(p):
    try:
        with open(p["state"]) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


CONFIG_PATH = os.path.join(HERE, "config.json")


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def is_modded(asar_path):
    header, _, fh = asarlib.read(asar_path)
    fh.close()
    return any(path.endswith("idleontune.js") for path, _ in asarlib.walk(header))


def ensure_vanilla(p, state):
    """Makes sure app.asar.vanilla is the current unmodded game."""
    current = sha256(p["asar"])
    if not os.path.exists(p["vanilla"]):
        if is_modded(p["asar"]):
            sys.exit("app.asar already contains the mod but there is no backup. "
                     "Use Steam > Verify integrity of game files, then install again.")
        shutil.copy2(p["asar"], p["vanilla"])
        print("Backed up the original archive to app.asar.vanilla")
    elif current != state.get("patched_sha256") and current != sha256(p["vanilla"]):
        if is_modded(p["asar"]):
            print("app.asar was modified by hand; rebuilding from app.asar.vanilla")
        else:
            # The game was updated by Steam after the last install.
            shutil.copy2(p["asar"], p["vanilla"])
            print("Game update detected: the new archive is now the vanilla copy")


def install(game):
    p = paths(game)
    if not os.path.exists(p["asar"]):
        sys.exit("app.asar not found in " + game)
    state = load_state(p)
    ensure_vanilla(p, state)
    config = load_config()
    work = tempfile.mkdtemp(prefix="idleontune_")
    try:
        asarlib.extract(p["vanilla"], work)
        results = patches.apply_all(work, config, VERSION)
        failed = [r for r in results if not r[1]]
        for name, ok, note in results:
            print(("  ok   " if ok else "  SKIP ") + name + (" - " + note if note else ""))
        try:
            asarlib.pack(work, p["asar"])
        except PermissionError:
            if os.path.exists(p["asar"] + ".tmp"):
                os.remove(p["asar"] + ".tmp")
            sys.exit("app.asar is in use: close the game and run install again.")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    state = {
        "version": VERSION,
        "patched_sha256": sha256(p["asar"]),
        "vanilla_sha256": sha256(p["vanilla"]),
        "skipped": [r[0] for r in failed],
    }
    with open(p["state"], "w") as fh:
        json.dump(state, fh, indent=1)
    print("Installed IdleOn Tune " + VERSION + (" (some patches skipped, see above)" if failed else ""))


def restore(game):
    p = paths(game)
    if not os.path.exists(p["vanilla"]):
        sys.exit("No app.asar.vanilla backup: the game is not modded (or Steam already restored it).")
    shutil.copy2(p["vanilla"], p["asar"])
    os.remove(p["vanilla"])
    if os.path.exists(p["state"]):
        os.remove(p["state"])
    print("Original game restored.")


def status(game):
    p = paths(game)
    state = load_state(p)
    if not os.path.exists(p["vanilla"]):
        print("Not installed.")
    elif sha256(p["asar"]) == state.get("patched_sha256"):
        print("Installed, version " + state.get("version", "?"))
        if state.get("skipped"):
            print("Skipped patches: " + ", ".join(state["skipped"]))
    else:
        print("Backup exists but the archive changed (Steam update?). Run install again.")


def main():
    ap = argparse.ArgumentParser(description="IdleOn Tune installer")
    ap.add_argument("command", choices=["install", "restore", "status"])
    ap.add_argument("--game", default=DEFAULT_GAME)
    ap.add_argument("--config", help="alternative config.json")
    args = ap.parse_args()
    if args.config:
        global CONFIG_PATH
        CONFIG_PATH = args.config
    {"install": install, "restore": restore, "status": status}[args.command](args.game)


if __name__ == "__main__":
    main()
