import fs from "node:fs";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const html = fs.readFileSync(path.join(root, "static", "clinical-dashboard", "index.html"), "utf8");
const match = html.match(/<script>([\s\S]*)<\/script>/);
if (!match) throw new Error("dashboard script missing");

const elements = {};
function makeEl(id) {
  elements[id] = {
    id,
    innerHTML: "",
    textContent: "",
    className: "",
    value: "",
    listeners: {},
    addEventListener(type, fn) { this.listeners[type] = fn; },
  };
}
["token", "study", "site", "message", "overview-body", "subjects-body", "visits-body", "analytics-body", "quality-body", "imports-body", "gate", "ecrf", "questionnaire"].forEach(makeEl);

const subjectClicks = {};
const documentStub = {
  getElementById(id) { return elements[id] || null; },
  querySelectorAll(selector) {
    if (selector !== "[data-subject]") return [];
    return [...elements["subjects-body"].innerHTML.matchAll(/data-subject="([^"]*)"/g)].map((found) => ({
      getAttribute() { return found[1]; },
      addEventListener(_type, fn) { subjectClicks[found[1]] = fn; },
    }));
  },
};

const pending = [];
const calls = [];
function fetchImpl(url, options) {
  calls.push({ url, options });
  let resolve;
  let reject;
  const promise = new Promise((ok, fail) => { resolve = ok; reject = fail; });
  pending.push({ resolve, reject });
  return promise;
}
function http(status, body) {
  return { ok: status >= 200 && status < 300, status, async json() { return body; } };
}
function payload(subject, value) {
  return {
    safety: { enable_r1: false, protocol_advisory_id: null, window_check: false },
    overview: { subject_count: 1, visit_count: 1, observation_status: { draft: 0, final: 1 }, staged_row_count: 0, unresolved_row_count: 0 },
    subjects: [
      { subject_code: subject, visit_count: 1, draft_count: 0, final_count: 1 },
      { subject_code: "SYN-OTHER", visit_count: 1, draft_count: 0, final_count: 0 },
    ],
    visits: [{ visit_code: "V1", occurred_on: "2026-03-02", draft_count: 0, final_count: 1 }],
    analytics: {
      final_descriptive: [{
        code: "TBUT", laterality: "OD", method: "reported_average", unit: "s",
        visits: [{ visit_code: "V1", n: 1, min: value, max: value, q1: value, median: value, q3: value }],
      }],
      draft_exploratory: [],
      subject_series: {
        FINAL: [{ visit_code: "V1", code: "TBUT", laterality: "OD", method: "reported_average", repeat_index: 0, value_number: value }],
        DRAFT: [],
      },
      coverage: [],
      provenance: [{ visit_code: "V1", code: "TBUT", laterality: "OD", method: "reported_average", record_status: "FINAL", source: "import", unit: "s" }],
    },
    quality: { findings: { open: 1 }, queries: { open: 1 } },
    imports: { batch_count: 1, discrepancy_count: 0, mapping_versions: [subject] },
  };
}
function panels() {
  return ["overview-body", "subjects-body", "visits-body", "analytics-body", "quality-body", "imports-body"]
    .map((id) => elements[id].innerHTML)
    .join("\n");
}
function assertClean(label) {
  const text = panels();
  if (text.includes("SYN-01") || text.includes("4.5") || text.includes("SYN-OLD")) {
    throw new Error(`${label}\n${text}`);
  }
  console.log("PASS", label);
}
function assertHas(label, token) {
  if (!panels().includes(token)) throw new Error(`${label} missing ${token}\n${panels()}`);
  console.log("PASS", label);
}

const context = {
  document: documentStub,
  fetch: fetchImpl,
  URLSearchParams,
  console,
  location: { assign() {} },
};
context.window = context;
vm.createContext(context);
vm.runInContext(match[1], context);

async function submit(study, site, token) {
  elements.study.value = study;
  elements.site.value = site;
  elements.token.value = token;
  return elements.gate.listeners.submit({ preventDefault() {} });
}
function take() {
  const item = pending.shift();
  if (!item) throw new Error("missing request");
  return item;
}

const first = submit("study-a", "site-a", "token-a");
take().resolve(http(200, payload("SYN-01", 4.5)));
await first;
assertHas("authorized load shows subject", "SYN-01");
assertHas("authorized load shows value", "4.5");
if (!calls.at(-1).options.headers.Authorization.startsWith("Bearer ")) {
  throw new Error("request missing bearer token");
}

const denied = submit("study-a", "site-a", "token-a");
take().resolve(http(401, {}));
await denied;
assertClean("401 clears sensitive content");
if (!elements.message.textContent.includes("거절")) throw new Error("401 message missing");

const again = submit("study-a", "site-a", "token-a");
take().resolve(http(200, payload("SYN-01", 4.5)));
await again;
const forbidden = submit("study-a", "site-a", "token-a");
take().resolve(http(403, {}));
await forbidden;
assertClean("403 clears sensitive content");

const restored = submit("study-a", "site-a", "token-a");
take().resolve(http(200, payload("SYN-01", 4.5)));
await restored;
elements.study.value = "study-b";
elements.study.listeners.input();
assertClean("study change clears prior subject content");

const sitePaint = submit("study-b", "site-a", "token-a");
take().resolve(http(200, payload("SYN-01", 4.5)));
await sitePaint;
elements.site.value = "site-b";
elements.site.listeners.input();
assertClean("site change clears prior subject content");

const subjectPaint = submit("study-b", "site-b", "token-a");
take().resolve(http(200, payload("SYN-01", 4.5)));
await subjectPaint;
const subjectLoad = subjectClicks["SYN-OTHER"]();
if (panels().includes("4.5")) throw new Error("subject change left the previous value visible");
take().resolve(http(200, payload("SYN-OTHER", 8.5)));
await subjectLoad;
assertHas("subject change shows the new value", "8.5");
if (panels().includes("4.5")) throw new Error("subject change kept the stale value");
console.log("PASS", "subject change cannot expose stale values");

const beforeFail = submit("study-b", "site-b", "token-a");
take().resolve(http(200, payload("SYN-01", 4.5)));
await beforeFail;
const failed = submit("study-b", "site-b", "token-a");
take().reject(new Error("offline"));
await failed;
assertClean("failed reload clears prior panels");

const beforeDelay = submit("study-b", "site-b", "token-a");
take().resolve(http(200, payload("SYN-01", 4.5)));
await beforeDelay;
const delayed = submit("study-b", "site-b", "token-a");
const stale = take();
elements.token.value = "expired";
elements.token.listeners.input();
stale.resolve(http(200, payload("SYN-01", 4.5)));
await delayed;
assertClean("delayed response cannot repopulate revoked content");

const fresh = submit("study-c", "site-c", "token-new");
const oldStudy = take();
elements.study.value = "study-d";
elements.study.listeners.input();
const replacement = elements.gate.listeners.submit({ preventDefault() {} });
const currentRequest = take();
oldStudy.resolve(http(200, payload("SYN-01", 4.5)));
await fresh;
if (panels().includes("4.5") || panels().includes("SYN-01")) {
  throw new Error("old study response restored revoked content");
}
currentRequest.resolve(http(200, payload("SYN-02", 8.5)));
await replacement;
assertHas("authorized reload restores new subject", "SYN-02");
assertHas("authorized reload restores new value", "8.5");
if (panels().includes("4.5") || panels().includes("SYN-01")) {
  throw new Error("authorized reload kept the previous subject");
}
console.log("PASS", "valid authorized reload restores only newly authorized information");
