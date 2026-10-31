// IdleOn Tune runtime. Runs in the game page before N.js.
(function () {
  "use strict";
  var tune = window.IDLEON_TUNE;
  var cfg = tune.config;

  // Render resolution: the game is 960x540; draw it at the size it is shown
  // fullscreen so the browser no longer stretches a small image.
  if (cfg.sharpRendering) {
    var scale = cfg.renderScale;
    if (scale === "auto") {
      var dpr = window.devicePixelRatio || 1;
      scale = Math.max(screen.width * dpr / 960, screen.height * dpr / 540);
    }
    window.__itScale = Math.max(1, Math.min(cfg.maxRenderScale, Number(scale) || 1));
  }

  if (cfg.fpsLimit > 0) window.__itFps = cfg.fpsLimit;

  // Game loop scheduler: animation frames normally, a timer while the page is
  // hidden (hidden pages get no animation frames and the game would freeze).
  var hiddenStep = 1000 / (cfg.fpsLimit > 0 ? cfg.fpsLimit : 60);
  window.__itRaf = function (cb) {
    if (document.hidden) {
      return setTimeout(function () { cb(performance.now()); }, hiddenStep);
    }
    return window.requestAnimationFrame(cb);
  };

  // Shared cache for colour-filtered animation frames (see p_filter_cache).
  // Key: the colour matrices of the filter list; only ColorMatrixFilter exists.
  var FILTERS_PER_FRAME = 16;
  window.__itFilterCache = new WeakMap();
  window.__itFilterKey = function (filters) {
    if (!cfg.filterCache || !filters) return null;
    var key = "";
    for (var i = 0; i < filters.length; i++) {
      var m = filters[i] && filters[i].__matrix;
      if (!m) return null;
      key += (i ? "|" : "") + Array.prototype.join.call(m, ",");
    }
    return key;
  };
  window.__itFilterStore = function (source, key, bitmap) {
    var byKey = window.__itFilterCache.get(source);
    if (!byKey) {
      byKey = new Map();
      window.__itFilterCache.set(source, byKey);
    } else if (byKey.size >= FILTERS_PER_FRAME) {
      byKey.delete(byKey.keys().next().value);
    }
    byKey.set(key, bitmap);
  };

  // Small notice in the corner (screenshots etc.).
  var toastTimer = null;
  function toast(text) {
    var el = document.getElementById("idleontune-toast");
    if (!el) {
      el = document.createElement("div");
      el.id = "idleontune-toast";
      el.style.cssText = "position:fixed;right:12px;bottom:12px;z-index:99999;padding:8px 14px;" +
        "border-radius:8px;background:rgba(0,0,0,.75);color:#fff;font:600 13px sans-serif;" +
        "pointer-events:none;transition:opacity .3s;opacity:0";
      document.body.appendChild(el);
    }
    el.textContent = text;
    el.style.opacity = "1";
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.style.opacity = "0"; }, 2500);
  }

  // F3: frames the game drew in the last second (not browser repaints).
  if (cfg.fpsOverlayHotkey) {
    var fpsEl = null, fpsTimer = null, lastFrames = 0, lastAt = 0;
    var tick = function () {
      var now = performance.now(), frames = window.__itFrames || 0;
      var fps = Math.round((frames - lastFrames) * 1000 / (now - lastAt));
      lastFrames = frames;
      lastAt = now;
      var engine = window.__itEngine, mem = performance.memory;
      fpsEl.textContent = window.__itHidden ? "FPS: paused (minimized)" :
        "FPS " + fps + " · render x" + (window.__itScale || 1).toFixed(2) +
        (engine ? " · timers " + engine.tasks.length : "") +
        (mem ? " · heap " + Math.round(mem.usedJSHeapSize / 1048576) + " MB" : "");
    };
    window.addEventListener("keydown", function (e) {
      if (e.key !== "F3") return;
      e.preventDefault();
      if (fpsEl) {
        clearInterval(fpsTimer);
        fpsEl.remove();
        fpsEl = null;
        return;
      }
      fpsEl = document.createElement("div");
      fpsEl.style.cssText = "position:fixed;left:8px;top:8px;z-index:99999;padding:3px 8px;border-radius:6px;" +
        "background:rgba(0,0,0,.6);color:#7f7;font:600 12px monospace;pointer-events:none";
      document.body.appendChild(fpsEl);
      lastFrames = window.__itFrames || 0;
      lastAt = performance.now();
      fpsEl.textContent = "FPS ...";
      fpsTimer = setInterval(tick, 1000);
    }, true);
  }

  // Messages from the main process (see idleontune-main.js).
  var api = window.parent && window.parent.electronApi;
  if (api) {
    api.on("myRenderChannel", function (msg) {
      if (!msg || msg[0] !== "ITUNE") return;
      if (msg[1] === "hidden") window.__itHidden = !!msg[2];
      else if (msg[1] === "toast") toast(msg[2]);
    });
  }
})();
