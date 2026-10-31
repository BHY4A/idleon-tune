// Drop-in replacement for the parts of greenworks that src/main/steam.js uses,
// built on steamworks.js (N-API, works with current Electron).
"use strict";

const path = require("path");

const SW_DIR = path.join(process.resourcesPath, "app.asar.unpacked", "node_modules", "steamworks.js");

let sw = null;
let client = null;
const listeners = {};

function init() {
  try {
    sw = require(SW_DIR);
    client = sw.init(1476970);
  } catch (e) {
    console.error("steamworks.js init failed:", e);
    return false;
  }
  client.callback.register(sw.SteamCallback.MicroTxnAuthorizationResponse, (r) => {
    for (const fn of listeners["micro-txn-authorization-response"] || []) {
      fn(r.app_id, typeof r.order_id === "bigint" ? r.order_id.toString() : r.order_id, r.authorized ? 1 : 0);
    }
  });
  return true;
}

function on(event, fn) {
  (listeners[event] = listeners[event] || []).push(fn);
}

function getSteamId() {
  const id = client.localplayer.getSteamId();
  return { steamId: id.steamId64.toString(), accountId: id.accountId };
}

function getCurrentGameLanguage() {
  return client.apps.currentGameLanguage();
}

function isSteamRunningOnSteamDeck() {
  return client.utils.isSteamRunningOnSteamDeck();
}

function setRichPresence(key, value) {
  client.localplayer.setRichPresence(key, value);
}

function activateAchievement(name, ok, fail) {
  try {
    if (client.achievement.activate(name)) ok && ok();
    else fail && fail("activate returned false");
  } catch (e) {
    fail && fail(String(e));
  }
}

function storeStats(ok, fail) {
  try {
    if (client.stats.store()) ok && ok(1476970);
    else fail && fail("store returned false");
  } catch (e) {
    fail && fail(String(e));
  }
}

// greenworks calls back with { ticket: Buffer, handle }.
function getAuthSessionTicket(ok, fail) {
  const self = client.localplayer.getSteamId().steamId64;
  client.auth.getSessionTicketWithSteamId(self).then(
    (t) => ok({ ticket: t.getBytes(), handle: 0 }),
    (e) => fail && fail(String(e))
  );
}

const FloatingGamepadTextInputMode = { SingleLine: 0, MultipleLines: 1, Email: 2, Numeric: 3 };

function showFloatingGamepadTextInput(mode, x, y, w, h) {
  client.utils.showFloatingGamepadTextInput(mode, x, y, w, h).catch(() => {});
}

module.exports = {
  init,
  on,
  getSteamId,
  getCurrentGameLanguage,
  isSteamRunningOnSteamDeck,
  setRichPresence,
  activateAchievement,
  storeStats,
  getAuthSessionTicket,
  FloatingGamepadTextInputMode,
  showFloatingGamepadTextInput,
};
