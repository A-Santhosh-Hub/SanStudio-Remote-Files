// SanStudio Link Backend — Google Apps Script (bound to a Google Sheet)
//
// POST JSON (send as text/plain so browsers skip the CORS preflight):
//   {"action":"update", "secret":"<tool_secret>", "link":"https://xxx.trycloudflare.com"}
//       ← automation tool on the office PC (also acts as a heartbeat)
//   {"action":"get", "password":"<viewer_password>"}
//       ← GitHub Pages front page

const SETTINGS_SHEET = "Settings";
const HISTORY_SHEET  = "History";

// Only Cloudflare quick-tunnel links are accepted, so even a leaked secret
// can't point the front page at a phishing site.
const LINK_PATTERN = /^https:\/\/[a-z0-9-]+\.trycloudflare\.com\/?$/;

const MAX_FAILS       = 20;       // wrong passwords allowed per window (all visitors)
const FAIL_WINDOW_SEC = 15 * 60;
const HISTORY_MAX     = 1000;     // rows kept in History

// ─── One-time setup — run this from the editor ───────────────────────────────
function setup() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  const s = ss.getSheetByName(SETTINGS_SHEET) || ss.insertSheet(SETTINGS_SHEET);
  s.getRange("B:B").setNumberFormat("@");   // plain text, so "0123" stays "0123"
  if (s.getLastRow() === 0) {
    s.appendRow(["Key", "Value", "Notes"]);
    s.getRange("A1:C1").setFontWeight("bold");
  }
  const existing = readSettings();
  const defaults = [
    ["viewer_password", "",           "Password for the GitHub page. Change it here any time."],
    ["tool_secret",     newSecret(),  "Paste into the automation tool. Never share."],
    ["current_link",    "",           "Set automatically by the automation tool"],
    ["updated_at",      "",           "When the link last changed (UTC)"],
    ["last_seen",       "",           "Last time the office PC checked in (UTC)"],
  ];
  defaults.forEach(row => {
    if (!(row[0] in existing)) s.appendRow(row);
  });
  s.autoResizeColumns(1, 3);

  const h = ss.getSheetByName(HISTORY_SHEET) || ss.insertSheet(HISTORY_SHEET);
  if (h.getLastRow() === 0) {
    h.appendRow(["Time (UTC)", "Event", "Detail"]);
    h.getRange("A1:C1").setFontWeight("bold");
  }

  Logger.log("Setup done. Now type your password in Settings → viewer_password (column B).");
}

// ─── Web app entry points ────────────────────────────────────────────────────
function doGet() {
  return json({ ok: true, service: "SanStudio link backend" });
}

function doPost(e) {
  let body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (err) {
    return json({ ok: false, error: "Bad request" });
  }
  if (body.action === "update") return json(handleUpdate(body));
  if (body.action === "get")    return json(handleGet(body));
  return json({ ok: false, error: "Unknown action" });
}

// ─── Actions ─────────────────────────────────────────────────────────────────
function handleUpdate(body) {
  const settings = readSettings();
  if (!settings.tool_secret || !safeEqual(body.secret, settings.tool_secret.value)) {
    return { ok: false, error: "Unauthorized" };
  }
  const link = String(body.link || "").trim().replace(/\/$/, "");
  if (!LINK_PATTERN.test(link)) {
    return { ok: false, error: "Invalid link" };
  }

  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const now = new Date().toISOString();
    const fresh = readSettings();
    if (fresh.current_link.value !== link) {
      writeSetting(fresh.current_link, link);
      writeSetting(fresh.updated_at, now);
      logEvent("link_changed", link);
    }
    writeSetting(fresh.last_seen, now);
  } finally {
    lock.releaseLock();
  }
  return { ok: true };
}

function handleGet(body) {
  const cache = CacheService.getScriptCache();
  const fails = Number(cache.get("fails") || 0);
  if (fails >= MAX_FAILS) {
    return { ok: false, error: "Too many wrong attempts. Try again in 15 minutes." };
  }

  const settings = readSettings();
  const expected = settings.viewer_password ? settings.viewer_password.value.trim() : "";
  if (!expected) {
    return { ok: false, error: "Viewer password is not set in the sheet." };
  }
  if (!safeEqual(String(body.password || ""), expected)) {
    cache.put("fails", String(fails + 1), FAIL_WINDOW_SEC);
    Utilities.sleep(1000);   // slow down guessing
    logEvent("login_failed", "");
    return { ok: false, error: "Wrong password." };
  }

  logEvent("login_ok", "");
  return {
    ok: true,
    link:       settings.current_link.value,
    updated_at: settings.updated_at.value,
    last_seen:  settings.last_seen.value,
    now:        new Date().toISOString(),
  };
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
function readSettings() {
  const s = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SETTINGS_SHEET);
  const map = {};
  if (!s || s.getLastRow() < 2) return map;
  const rows = s.getRange(2, 1, s.getLastRow() - 1, 2).getValues();
  rows.forEach((r, i) => {
    if (r[0]) map[String(r[0]).trim()] = { row: i + 2, value: String(r[1]) };
  });
  return map;
}

function writeSetting(entry, value) {
  SpreadsheetApp.getActiveSpreadsheet()
    .getSheetByName(SETTINGS_SHEET)
    .getRange(entry.row, 2)
    .setValue(value);
}

function logEvent(event, detail) {
  const h = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(HISTORY_SHEET);
  if (!h) return;
  h.appendRow([new Date().toISOString(), event, detail]);
  const extra = h.getLastRow() - 1 - HISTORY_MAX;
  if (extra > 0) h.deleteRows(2, extra);
}

function safeEqual(a, b) {
  a = String(a == null ? "" : a);
  b = String(b == null ? "" : b);
  if (a.length !== b.length || a.length === 0) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function newSecret() {
  return (Utilities.getUuid() + Utilities.getUuid()).replace(/-/g, "");
}

function json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
