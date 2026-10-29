import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const htmlPath = path.join(root, "static", "questionnaire", "index.html");
const html = fs.readFileSync(htmlPath, "utf8");

if (html.includes("Object ...(")) {
  throw new Error("malformed Object ... headers construction is present");
}
if (!html.includes("{ ...(options.headers || {}), Authorization:")) {
  throw new Error("expected object-spread Authorization headers construction");
}

const match = html.match(/<script>([\s\S]*)<\/script>/);
if (!match) throw new Error("questionnaire script missing");
const script = match[1];

try {
  new Function(script);
} catch (err) {
  throw new Error(`questionnaire script is not valid JavaScript: ${err.message}`);
}
console.log("PASS", "questionnaire script parses");

const elements = {};
function makeEl(id) {
  elements[id] = {
    id,
    value: "",
    textContent: "",
    onclick: null,
  };
}
["token", "study", "site", "version", "visit", "item", "value", "message", "result", "stats-body", "start", "save", "finalize", "score", "stats"].forEach(makeEl);

const calls = [];
const documentStub = {
  getElementById(id) {
    return elements[id] || null;
  },
};
const context = {
  document: documentStub,
  fetch(url, options = {}) {
    calls.push({ url, options });
    const status = Number(context.__status || 200);
    const body = context.__body || { id: "syn-response", status: "draft" };
    return Promise.resolve({
      ok: status >= 200 && status < 300,
      status,
      async json() {
        return body;
      },
    });
  },
  console,
};
context.window = context;
vm.createContext(context);
vm.runInContext(script, context);

for (const id of ["start", "save", "finalize", "score", "stats"]) {
  if (typeof elements[id].onclick !== "function") {
    throw new Error(`${id} handler was not registered`);
  }
}
console.log("PASS", "questionnaire handlers registered");

elements.token.value = "token-a";
elements.version.value = "version-a";
elements.visit.value = "visit-a";
context.__status = 200;
context.__body = { id: "syn-1", status: "draft" };
await elements.start.onclick();
if (!elements.result.textContent.includes("syn-1")) {
  throw new Error(`authorized start did not update result: ${elements.result.textContent}`);
}
const authHeader = calls.at(-1)?.options?.headers?.Authorization || "";
if (!authHeader.startsWith("Bearer ")) {
  throw new Error("authorized request missing bearer token");
}
console.log("PASS", "authorized start keeps result");

elements.result.textContent = "응답 syn-stale · draft";
elements.token.value = "bad";
context.__status = 401;
context.__body = {};
try {
  await elements.start.onclick();
  throw new Error("401 should throw");
} catch (err) {
  if (String(err.message) !== "auth") throw err;
}
if (elements.result.textContent !== "") {
  throw new Error("401 left previous response visible");
}
if (!elements.message.textContent.includes("권한")) {
  throw new Error("401 message missing");
}
console.log("PASS", "401 clears questionnaire subject content");

elements.result.textContent = "응답 syn-stale · draft";
context.__status = 403;
try {
  await elements.stats.onclick();
  throw new Error("403 should throw");
} catch (err) {
  if (String(err.message) !== "auth") throw err;
}
if (elements.result.textContent !== "") {
  throw new Error("403 left previous response visible");
}
console.log("PASS", "403 clears questionnaire subject content");
