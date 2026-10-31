"""Text patches applied to the extracted game archive.

Each patch names an exact anchor in the shipped code and how many times it must
occur. If an anchor is missing (a game update changed the code), that patch is
skipped and reported instead of guessing.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_DIR = "distBuild/static/game"


class Skip(Exception):
    pass


def replace(text, old, new, count=1):
    found = text.count(old)
    if count is None:
        count = max(found, 1)  # any number of occurrences, at least one
    if found != count:
        raise Skip("anchor found %d times, expected %d: %s" % (found, count, old[:60]))
    return text.replace(old, new)


class Files:
    def __init__(self, root):
        self.root = root
        self.cache = {}

    def get(self, rel):
        if rel not in self.cache:
            with open(os.path.join(self.root, *rel.split("/")), encoding="utf-8") as fh:
                self.cache[rel] = fh.read()
        return self.cache[rel]

    def set(self, rel, text):
        self.cache[rel] = text

    def save(self):
        for rel, text in self.cache.items():
            with open(os.path.join(self.root, *rel.split("/")), "w", encoding="utf-8", newline="") as fh:
                fh.write(text)


N_JS = GAME_DIR + "/N.js"
INDEX = GAME_DIR + "/index.html"
MAIN = "src/main/index.js"


def p_renderer_script(f, cfg, version):
    """Loads idleontune.js (config + runtime helpers) before the game."""
    with open(os.path.join(HERE, "mod", "idleontune.js"), encoding="utf-8") as fh:
        script = fh.read()
    head = "window.IDLEON_TUNE=" + json.dumps({"version": version, "config": cfg}) + ";\n"
    f.set(GAME_DIR + "/idleontune.js", head + script)
    f.set(INDEX, replace(f.get(INDEX),
        '<script type="text/javascript" src="./N.js"></script>',
        '<script type="text/javascript" src="./idleontune.js"></script>\n'
        '    <script type="text/javascript" src="./N.js"></script>'))


def p_sharp_rendering(f, cfg, version):
    """Renders the 960x540 game at screen resolution instead of stretching it."""
    if not cfg["sharpRendering"]:
        raise Skip("disabled in config")
    text = f.get(N_JS)
    text = replace(text, 'allowHighDPI:!1,alwaysOnTop:!1', 'allowHighDPI:!0,alwaysOnTop:!1')
    text = replace(text, '&&(this.scale=window.devicePixelRatio),e.__scale=this.scale',
                   '&&(this.scale=window.__itScale||window.devicePixelRatio),e.__scale=this.scale')
    f.set(N_JS, text)


def p_skip_hidden_render(f, cfg, version):
    """While minimized the game still updates every frame but stops drawing."""
    if not cfg["skipHiddenRendering"]:
        raise Skip("disabled in config")
    f.set(N_JS, replace(f.get(N_JS),
        'e=null!=this.__renderer&&(this.__renderDirty||this.__forceRender),this.__invalidated&&e',
        'e=null!=this.__renderer&&!(window.__itHidden||document.hidden)&&(this.__renderDirty||this.__forceRender),this.__invalidated&&e'))


def p_fps_limit(f, cfg, version):
    """The game asks for 65 FPS, which Lime treats as "uncapped": it redraws at
    the monitor rate (300 Hz here). Game logic runs in fixed 10 ms steps from
    real time, so a cap changes only how often the same state is redrawn."""
    if not cfg["fpsLimit"]:
        raise Skip("fpsLimit is 0 (game default)")
    # Lime starts with framePeriod=-1 (every animation frame) and the game
    # never calls setFrameRate, so the cap goes into the constructor. The
    # period is 5% shorter so a cap equal to the monitor rate never drops frames.
    period = "950/window.__itFps"
    text = f.get(N_JS)
    text = replace(text, 'this.nextUpdate=this.lastUpdate=this.currentUpdate=0,this.framePeriod=-1,',
                   'this.nextUpdate=this.lastUpdate=this.currentUpdate=0,this.framePeriod=window.__itFps?' + period + ':-1,')
    text = replace(text,
        '(60<=e?this.parent==this.parent.application.__window&&(this.parent.application.__backend.framePeriod=-1)',
        '(!window.__itFps&&60<=e?this.parent==this.parent.application.__window&&(this.parent.application.__backend.framePeriod=-1)')
    text = replace(text, 'framePeriod=1e3/e', 'framePeriod=window.__itFps?' + period + ':1e3/e')
    f.set(N_JS, text)


def p_webgl_renderer(f, cfg, version):
    """The game was built with OpenFL's `canvas` define: Stage.__createRenderer
    lost its WebGL branch, but OpenGLRenderer, Context3D and all Context3D*
    renderers are still in N.js (Stencyl's shaders use them). This puts the
    branch back exactly as in OpenFL 9.2.0 and asks Lime for a WebGL context."""
    if cfg["renderer"] != "webgl":
        raise Skip("renderer is " + cfg["renderer"])
    text = f.get(N_JS)
    text = replace(text,
        'depth:!0,hardware:!0,stencil:!0,type:null,vsync:!0}',
        'depth:!0,hardware:!0,stencil:!0,type:"webgl",vsync:!0}')
    text = replace(text,
        'switch(this.window.context.type){case"canvas":this.__renderer=new Vh(this.window.context.canvas2D);break;case"dom":',
        'switch(this.window.context.type){case"opengl":case"opengles":case"webgl":'
        'this.context3D=new A["openfl.display3D.Context3D"](this),'
        'this.context3D.configureBackBuffer(this.stageWidth,this.stageHeight,0,!0,!0,!0),'
        'this.context3D.present(),this.__renderer=new A["openfl.display.OpenGLRenderer"](this.context3D);break;'
        'case"canvas":this.__renderer=new Vh(this.window.context.canvas2D);break;case"dom":')
    # OpenGLRenderer smooths every texture whenever the stage is scaled
    # (smoothing || __upscaled); at our high-DPI scale that blurred all pixel-art
    # sprites. Smooth only what the game marks as smooth, like the Canvas renderer.
    text = replace(text, 'this.__upscaled=1!=this.__worldTransform.a||1!=this.__worldTransform.d',
                   'this.__upscaled=!1')
    f.set(N_JS, text)


def p_hidden_loop(f, cfg, version):
    """A hidden page gets no animation frames, which would stop the game loop.
    Stock Electron 11 avoids that with incrementCapturerCount (removed in newer
    Electron); this keeps the loop going on a timer while the page is hidden."""
    f.set(N_JS, replace(f.get(N_JS),
        'window.requestAnimationFrame(w(this,this.handleApplicationEvent))',
        '(window.__itRaf||window.requestAnimationFrame)(w(this,this.handleApplicationEvent))'))


def p_filter_cache(f, cfg, version):
    """Stencyl's BitmapAnimation colour-filters every frame on the CPU
    (getImageData + per-pixel loop) and keeps the result per animation
    instance, dropped on every animation switch. The same monster frames with
    the same tint were redone over and over. Shared cache: source frame +
    colour matrix -> filtered frame. Nothing disposes filtered frames, so
    sharing them is safe; the WeakMap lets them go with their source asset."""
    if not cfg["filterCache"]:
        raise Skip("disabled in config")
    f.set(N_JS, replace(f.get(N_JS),
        'applyFilters:function(e,t,i){null==e&&(e=new kb(t.width,t.height));for(var n=0;n<i.length;){var a=i[n];++n,t=a.__applyFilter(e,t,t.rect,D.zero)}return e}',
        'applyFilters:function(e,t,i){var K=window.__itFilterKey(i),C,s=t;if(null!=K&&(C=window.__itFilterCache.get(s))&&C.has(K))return C.get(K);'
        'null==e&&(e=new kb(t.width,t.height));for(var n=0;n<i.length;){var a=i[n];++n,t=a.__applyFilter(e,t,t.rect,D.zero)}'
        'null!=K&&window.__itFilterStore(s,K,e);return e}'))


def p_engine_handle(f, cfg, version):
    """window.__itEngine = the Stencyl engine (for the F3 overlay and tests)."""
    f.set(N_JS, replace(f.get(N_JS), 'addTask:function(e){this.tasks.push(e)}',
                        'addTask:function(e){window.__itEngine=this,this.tasks.push(e)}'))


def p_frame_counter(f, cfg, version):
    """Counts frames the game actually draws, for the F3 overlay."""
    if not cfg["fpsOverlayHotkey"]:
        raise Skip("disabled in config")
    f.set(N_JS, replace(f.get(N_JS),
        '__onLimeRender:function(e){if(!this.__rendering){',
        '__onLimeRender:function(e){if(!this.__rendering){window.__itFrames=(window.__itFrames||0)+1;'))


def p_no_analytics(f, cfg, version):
    """Google Analytics is only initialised, never fed events; skip loading it."""
    if not cfg["disableAnalytics"]:
        raise Skip("disabled in config")
    f.set(INDEX, replace(f.get(INDEX),
        '<script src="https://www.gstatic.com/firebasejs/8.2.10/firebase-analytics.js"></script>',
        '<script>firebase.analytics=function(){return{logEvent:function(){},setUserId:function(){},'
        'setUserProperties:function(){},setCurrentScreen:function(){}}};</script>'))


def p_main_process(f, cfg, version):
    """Window: fullscreen hotkey, remembered size/position, screenshots, flags."""
    with open(os.path.join(HERE, "mod", "idleontune-main.js"), encoding="utf-8") as fh:
        script = fh.read()
    f.set("src/main/idleontune-main.js", "const TUNE_CONFIG = " + json.dumps(cfg) + ";\n" + script)
    text = f.get(MAIN)
    text = replace(text,
        'const { isDevelopment, OVERLAY_FIX } = require("./config"); // process.env.NODE_ENV !== \'production\'\n\nif (OVERLAY_FIX) {',
        'const { isDevelopment, OVERLAY_FIX } = require("./config"); // process.env.NODE_ENV !== \'production\'\n'
        'const tune = require("./idleontune-main");\ntune.applySwitches(app);\n\n'
        'if (OVERLAY_FIX && tune.config.steamOverlayFix) {')
    text = replace(text,
        '  const window = new BrowserWindow({\n    width,\n    height,\n',
        '  const window = new BrowserWindow({\n    ...tune.windowOptions(width, height),\n')
    text = replace(text,
        '  window.webContents.incrementCapturerCount();\n',
        '  window.webContents.incrementCapturerCount();\n  tune.attach(window);\n')
    # The game quits silently on any startup error; leave a trace in the log.
    text = replace(text, '  } catch (e) {\n    app.quit();\n  }',
                   '  } catch (e) {\n    console.error("Startup error:", e);\n    app.quit();\n  }', 2)
    f.set(MAIN, text)
    # In fullscreen the 32 px title bar is hidden so the game fills the screen.
    if cfg["fullscreenHotkey"]:
        css = "distBuild/main.css"
        f.set(css, f.get(css) + "\nhtml.it-fs #menuBar{display:none}html.it-fs .container{height:100vh}\n")


def p_modern_runtime(f, cfg, version):
    """Code changes the game needs to run on a current Electron (see runtime.py)."""
    if not cfg.get("modernRuntime"):
        raise Skip("modernRuntime is off")
    with open(os.path.join(HERE, "mod", "greenworks-shim.js"), encoding="utf-8") as fh:
        f.set("src/main/greenworks-shim.js", fh.read())
    steam = "src/main/steam.js"
    f.set(steam, replace(f.get(steam),
        '      greenworks = require("greenworks");',
        '      greenworks = require("./greenworks-shim");'))
    text = f.get(MAIN)
    # Removed from Electron; the hidden-window game loop replaces it (p_hidden_loop).
    text = replace(text, '  window.webContents.incrementCapturerCount();\n',
                   '  if (window.webContents.incrementCapturerCount) window.webContents.incrementCapturerCount();\n')
    text = replace(text, '          tempWindow.webContents.decrementCapturerCount();\n',
                   '          if (tempWindow.webContents.decrementCapturerCount) tempWindow.webContents.decrementCapturerCount();\n')
    # Separate profile: a newer Chromium upgrades the profile in place and the
    # stock Electron 11 build could no longer read it.
    text = replace(text,
        'const { app, BrowserWindow, ipcMain } = require("electron");\n',
        'const { app, BrowserWindow, ipcMain } = require("electron");\n'
        'app.setPath("userData", app.getPath("userData") + "-modern");\n'
        'app.commandLine.appendSwitch("disable-background-timer-throttling");\n'
        'app.commandLine.appendSwitch("disable-backgrounding-occluded-windows");\n')
    # The stock Electron binary carries the Electron icon; give the window the game's.
    text = replace(text, '    resizable: true,\n    minimizable: false,\n',
                   '    resizable: true,\n    minimizable: false,\n'
                   '    icon: path.join(__dirname, "../../assets/icon.png"),\n')
    # "new-window" no longer exists; route window.open through the game's own allowlist.
    text = replace(text,
        '  tune.attach(window);\n',
        '  tune.attach(window);\n'
        '  window.webContents.setWindowOpenHandler(({ url }) => {\n'
        '    window.webContents.emit("new-window", { preventDefault() {} }, url);\n'
        '    return { action: "deny" };\n'
        '  });\n')
    f.set(MAIN, text)
    # Current Chromium lays the frame out 4px taller and shows a scrollbar.
    css = "distBuild/main.css"
    f.set(css, f.get(css) + "\nhtml,body{overflow:hidden}\n")


def p_broken_assets(f, cfg, version):
    """CSS points at /static/..., which resolves to C:/static under file:// -
    the custom cursor and the sign-in fonts never load."""
    if not cfg["fixBrokenAssets"]:
        raise Skip("disabled in config")
    css = GAME_DIR + "/game.css"
    text = f.get(css)
    text = replace(text, 'url("/static/cursor3.png")', 'url("../cursor3.png")')
    text = replace(text, "url(/static/fonts/", "url(../fonts/", 3)
    f.set(css, text)
    f.set("distBuild/main.css", replace(f.get("distBuild/main.css"),
        'url("/cursor3.png")', 'url("static/cursor3.png")', None))


PATCHES = [
    ("renderer script", p_renderer_script),
    ("sharp fullscreen rendering", p_sharp_rendering),
    ("WebGL renderer", p_webgl_renderer),
    ("skip drawing while minimized", p_skip_hidden_render),
    ("FPS limit", p_fps_limit),
    ("game loop while hidden", p_hidden_loop),
    ("shared animation filter cache", p_filter_cache),
    ("engine handle", p_engine_handle),
    ("F3 FPS counter", p_frame_counter),
    ("disable analytics", p_no_analytics),
    ("window: fullscreen/screenshot/remember", p_main_process),
    ("fix broken cursor and fonts", p_broken_assets),
    ("modern Electron support", p_modern_runtime),
]


def apply_all(root, cfg, version):
    f = Files(root)
    results = []
    for name, fn in PATCHES:
        try:
            fn(f, cfg, version)
            results.append((name, True, ""))
        except Skip as e:
            results.append((name, False, str(e)))
    f.save()
    return results
