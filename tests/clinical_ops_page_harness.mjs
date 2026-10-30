import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const sessionPath = path.join(root, "static", "clinical-ops", "ops-session.js");
const appPath = path.join(root, "static", "clinical-ops", "ops-app.js");
const htmlPath = path.join(root, "static", "clinical-ops", "index.html");

const sessionSrc = fs.readFileSync(sessionPath, "utf8");
const appSrc = fs.readFileSync(appPath, "utf8");
const html = fs.readFileSync(htmlPath, "utf8");

for (const [label, src] of [["ops-session.js", sessionSrc], ["ops-app.js", appSrc]]) {
  try {
    new Function(src);
  } catch (err) {
    throw new Error(`${label} parse error: ${err.message}`);
  }
}
console.log("PASS", "clinical-ops scripts parse");

if (/localStorage\.(get|set|remove)Item/.test(sessionSrc + appSrc + html)) {
  throw new Error("JWT must not use browser storage APIs");
}
if (/sessionStorage\.(get|set|remove)Item/.test(sessionSrc + appSrc + html)) {
  throw new Error("JWT must not use browser storage APIs");
}
if (!sessionSrc.includes("Bearer") || !sessionSrc.includes("clearSensitive")) {
  throw new Error("session helpers incomplete");
}
console.log("PASS", "memory-only session constraints");

const ids = [
  "login-view", "app-view", "login-msg", "who", "study", "site", "subject", "scope-msg",
  "username", "password", "login-btn", "logout-btn", "apply-scope", "nav",
  "load-dashboard", "dashboard-body", "subjects-body", "schema-id", "load-schema", "ecrf-body",
  "q-version", "q-visit", "q-item", "q-value", "q-start", "q-save", "q-finalize", "q-score", "q-body",
  "q-status", "load-queries", "new-query-text", "new-query-cat", "create-query", "queries-body",
  "query-id", "query-response", "respond-query", "resolve-query", "reopen-query", "query-history", "query-detail",
  "lock-type", "lock-target", "lock-reason", "lock-readiness", "lock-request", "lock-apply",
  "unlock-request", "lock-history", "locks-body",
  "unlock-request-id", "unlock-decision-reason", "unlock-approve", "unlock-reject",
  "obs-edit-id", "obs-edit-value", "obs-edit-try",
  "audit-action", "audit-target-type", "audit-from", "audit-to", "load-audit", "audit-body",
  "load-protocol-info", "protocol-body",
];

function el(id) {
  return {
    id,
    value: "",
    textContent: "",
    innerHTML: "",
    className: "",
    classList: {
      _set: new Set(id === "app-view" ? ["hidden"] : []),
      add(name) { this._set.add(name); },
      remove(name) { this._set.delete(name); },
      contains(name) { return this._set.has(name); },
    },
    style: {},
    children: [],
    addEventListener(type, fn) { this[`on${type}`] = fn; },
    setAttribute() {},
    getAttribute(name) { return this._attrs?.[name] || null; },
    querySelectorAll() { return []; },
  };
}

const elements = Object.fromEntries(ids.map((id) => [id, el(id)]));
elements.nav.querySelectorAll = () => [];
const panelNames = ["dashboard", "subjects", "ecrf", "questionnaires", "queries", "locks", "audit", "protocol"];
panelNames.forEach((name) => {
  const id = `panel-${name}`;
  elements[id] = el(id);
  elements[id].classList.add("hidden");
});

const fetchCalls = [];
const context = {
  window: {},
  location: { hash: "#dashboard" },
  addEventListener() {},
  document: {
    getElementById(id) { return elements[id] || null; },
    querySelectorAll(sel) {
      if (sel === ".panel") return panelNames.map((n) => elements[`panel-${n}`]);
      if (sel === "#nav a" || sel === "#nav a[data-panel]") return [];
      return [];
    },
    querySelector() { return null; },
  },
  fetch(url, options = {}) {
    fetchCalls.push({ url, options });
    const status = Number(context.__status || 200);
    const body = context.__body;
    return Promise.resolve({
      ok: status >= 200 && status < 300,
      status,
      async json() { return body; },
      async text() { return JSON.stringify(body); },
    });
  },
  console,
};
context.window = context;
context.window.addEventListener = () => {};
vm.createContext(context);
vm.runInContext(sessionSrc, context);
if (!context.ClinicalOpsSession) throw new Error("ClinicalOpsSession missing");
console.log("PASS", "ClinicalOpsSession registered");

vm.runInContext(appSrc, context);
if (typeof elements["login-btn"].onclick !== "function") {
  throw new Error("login handler missing");
}
console.log("PASS", "ops-app handlers registered");

context.__status = 401;
context.ClinicalOpsSession.setAuth("tok", "u1", "doctor");
context.ClinicalOpsSession.state.aborted = false;
try {
  await context.ClinicalOpsSession.api("/api/v1/clinical-support/ops/audits");
  throw new Error("401 should throw");
} catch (err) {
  if (err.code !== "AUTH") throw err;
}
if (context.ClinicalOpsSession.state.token) {
  throw new Error("401 did not clear token");
}
console.log("PASS", "401 clears sensitive session");

context.__status = 403;
context.ClinicalOpsSession.setAuth("tok2", "u1", "doctor");
try {
  await context.ClinicalOpsSession.api("/api/v1/clinical-support/ops/audits");
  throw new Error("403 should throw");
} catch (err) {
  if (err.code !== "AUTH") throw err;
}
if (context.ClinicalOpsSession.state.token) {
  throw new Error("403 did not clear token");
}
console.log("PASS", "403 clears sensitive session");

context.ClinicalOpsSession.setAuth("tok3", "u1", "doctor");
context.ClinicalOpsSession.setScope("s1", "site1", "subj1");
const seq = context.ClinicalOpsSession.state.requestSeq;
context.__status = 200;
context.__body = [];
const pending = context.ClinicalOpsSession.api("/slow");
context.ClinicalOpsSession.setScope("s2", "site2", "");
try {
  await pending;
  throw new Error("stale should throw");
} catch (err) {
  if (err.code !== "STALE") throw err;
}
if (context.ClinicalOpsSession.state.requestSeq <= seq) {
  throw new Error("scope change did not bump requestSeq");
}
console.log("PASS", "stale response protection");

console.log("ALL_PASS clinical-ops harness");
