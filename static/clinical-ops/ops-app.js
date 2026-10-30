/* Clinical Operations SPA — memory JWT only; no token logging. */
(function () {
  const S = window.ClinicalOpsSession;
  if (!S) throw new Error("ClinicalOpsSession missing");

  const els = {
    loginView: document.getElementById("login-view"),
    appView: document.getElementById("app-view"),
    loginMsg: document.getElementById("login-msg"),
    who: document.getElementById("who"),
    study: document.getElementById("study"),
    site: document.getElementById("site"),
    subject: document.getElementById("subject"),
    scopeMsg: document.getElementById("scope-msg"),
  };

  let sessionStudies = [];
  let responseId = "";

  function showLogin(message) {
    els.loginView.classList.remove("hidden");
    els.appView.classList.add("hidden");
    clearPanels();
    if (message) {
      els.loginMsg.textContent = message;
      els.loginMsg.className = "err";
    }
  }

  function showApp() {
    els.loginView.classList.add("hidden");
    els.appView.classList.remove("hidden");
    els.who.textContent = `${S.state.userId} / ${S.state.role}`;
    applyNavVisibility();
  }

  function clearPanels() {
    [
      "dashboard-body", "subjects-body", "ecrf-body", "q-body",
      "queries-body", "query-detail", "locks-body", "audit-body", "protocol-body",
    ].forEach((id) => {
      const node = document.getElementById(id);
      if (node) node.textContent = "";
    });
    responseId = "";
    els.study.innerHTML = "";
    els.site.innerHTML = "";
    els.subject.innerHTML = '<option value="">(대상자 선택)</option>';
    sessionStudies = [];
  }

  function applyNavVisibility() {
    const allowed = new Set((window.__opsNav || []).map(String));
    document.querySelectorAll("#nav a[data-panel]").forEach((link) => {
      const panel = link.getAttribute("data-panel");
      if (allowed.size && !allowed.has(panel)) {
        link.classList.add("hidden");
      } else {
        link.classList.remove("hidden");
      }
    });
  }

  function showPanel(name) {
    document.querySelectorAll(".panel").forEach((node) => node.classList.add("hidden"));
    document.querySelectorAll("#nav a").forEach((a) => a.classList.remove("active"));
    const panel = document.getElementById(`panel-${name}`);
    if (panel) panel.classList.remove("hidden");
    const link = document.querySelector(`#nav a[data-panel="${name}"]`);
    if (link) link.classList.add("active");
  }

  async function handleAuthError(err) {
    if (err && (err.code === "AUTH" || err.status === 401 || err.status === 403)) {
      S.clearSensitive();
      showLogin(err.status === 403 ? "권한이 없습니다. 다시 로그인하세요." : "인증이 만료되었거나 거부되었습니다.");
      return true;
    }
    if (err && err.code === "STALE") return true;
    return false;
  }

  function fillStudies(studies) {
    sessionStudies = studies || [];
    els.study.innerHTML = sessionStudies.map((s) =>
      `<option value="${S.esc(s.id)}">${S.esc(s.code)} — ${S.esc(s.name)}</option>`
    ).join("");
    fillSites();
  }

  function fillSites() {
    const study = sessionStudies.find((s) => s.id === els.study.value);
    const sites = (study && study.sites) || [];
    els.site.innerHTML = sites.map((site) =>
      `<option value="${S.esc(site.id)}">${S.esc(site.site_code)} — ${S.esc(site.name)}</option>`
    ).join("");
  }

  async function loadSubjects() {
    const studyId = els.study.value;
    if (!studyId) return;
    const siteId = els.site.value;
    const qs = siteId ? `?site_id=${encodeURIComponent(siteId)}` : "";
    try {
      const res = await S.api(`/api/v1/clinical-support/studies/${encodeURIComponent(studyId)}/subjects${qs}`);
      if (!res.ok) throw Object.assign(new Error("subjects"), { status: res.status });
      const rows = await res.json();
      els.subject.innerHTML = '<option value="">(대상자 선택)</option>' + rows.map((row) =>
        `<option value="${S.esc(row.id)}">${S.esc(row.subject_code || row.id)}</option>`
      ).join("");
      const body = document.getElementById("subjects-body");
      body.innerHTML = `<table><thead><tr><th>코드</th><th>ID</th><th>사이트</th></tr></thead><tbody>${
        rows.map((row) => `<tr><td>${S.esc(row.subject_code)}</td><td>${S.esc(row.id)}</td><td>${S.esc(row.site_id)}</td></tr>`).join("")
      }</tbody></table>`;
    } catch (err) {
      if (await handleAuthError(err)) return;
      document.getElementById("subjects-body").textContent = "대상자 목록을 불러오지 못했습니다.";
    }
  }

  document.getElementById("login-btn").addEventListener("click", async () => {
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;
    els.loginMsg.textContent = "로그인 중…";
    els.loginMsg.className = "muted";
    try {
      const session = await S.login(username, password);
      document.getElementById("password").value = "";
      window.__opsNav = session.nav || [];
      fillStudies(session.studies || []);
      showApp();
      showPanel("dashboard");
      els.loginMsg.textContent = "";
    } catch (err) {
      document.getElementById("password").value = "";
      S.clearSensitive();
      els.loginMsg.textContent = "로그인에 실패했습니다.";
      els.loginMsg.className = "err";
    }
  });

  document.getElementById("logout-btn").addEventListener("click", () => {
    S.logout();
    showLogin("로그아웃되었습니다.");
  });

  document.getElementById("study").addEventListener("change", () => {
    fillSites();
    S.setScope(els.study.value, els.site.value, els.subject.value);
  });
  document.getElementById("site").addEventListener("change", () => {
    S.setScope(els.study.value, els.site.value, els.subject.value);
  });
  document.getElementById("apply-scope").addEventListener("click", async () => {
    S.setScope(els.study.value, els.site.value, els.subject.value);
    els.scopeMsg.textContent = `적용됨: study=${els.study.value} site=${els.site.value}`;
    await loadSubjects();
  });

  document.querySelectorAll("#nav a[data-panel]").forEach((link) => {
    link.addEventListener("click", (ev) => {
      ev.preventDefault();
      showPanel(link.getAttribute("data-panel"));
    });
  });

  document.getElementById("load-dashboard").addEventListener("click", async () => {
    const body = document.getElementById("dashboard-body");
    body.textContent = "불러오는 중…";
    try {
      const studyId = els.study.value;
      const siteId = els.site.value;
      const res = await S.api(
        `/api/v1/clinical-support/studies/${encodeURIComponent(studyId)}/case-dashboard?site_id=${encodeURIComponent(siteId)}`
      );
      if (!res.ok) throw Object.assign(new Error("dash"), { status: res.status });
      const data = await res.json();
      body.textContent = JSON.stringify({
        study_id: data.study_id,
        site_id: data.site_id,
        subject_count: data.subject_count,
        visit_count: data.visit_count,
        observation_count: data.observation_count,
      }, null, 2);
    } catch (err) {
      if (await handleAuthError(err)) return;
      body.textContent = "대시보드를 불러오지 못했습니다.";
    }
  });

  document.getElementById("load-schema").addEventListener("click", async () => {
    const out = document.getElementById("ecrf-body");
    out.textContent = "조회 중…";
    try {
      const schemaId = document.getElementById("schema-id").value.trim();
      const studyId = els.study.value;
      const siteId = els.site.value;
      const res = await S.api(
        `/api/v1/clinical-support/studies/${encodeURIComponent(studyId)}/ecrf-schemas/${encodeURIComponent(schemaId)}?site_id=${encodeURIComponent(siteId)}`
      );
      if (!res.ok) throw Object.assign(new Error("schema"), { status: res.status });
      const data = await res.json();
      out.textContent = JSON.stringify({
        id: data.id,
        status: data.status,
        study_code: data.study_code,
        field_count: Array.isArray(data.fields) ? data.fields.length : undefined,
        forms: data.forms,
      }, null, 2);
    } catch (err) {
      if (await handleAuthError(err)) return;
      out.textContent = "스키마 조회 실패 (권한 또는 ID 확인).";
    }
  });

  document.getElementById("q-start").addEventListener("click", async () => {
    const out = document.getElementById("q-body");
    try {
      const res = await S.api("/api/v1/clinical-support/questionnaire-engine/responses", {
        method: "POST",
        body: JSON.stringify({
          version_id: document.getElementById("q-version").value.trim(),
          visit_id: document.getElementById("q-visit").value.trim(),
        }),
      });
      if (!res.ok) throw Object.assign(new Error("qstart"), { status: res.status });
      const data = await res.json();
      responseId = data.id || data.response_id || "";
      out.textContent = `응답 시작: ${responseId}`;
    } catch (err) {
      if (await handleAuthError(err)) return;
      out.textContent = "설문 시작 실패 (AMD는 OSDI 자동 연결 없음).";
    }
  });

  document.getElementById("q-save").addEventListener("click", async () => {
    const out = document.getElementById("q-body");
    if (!responseId) { out.textContent = "응답 ID 없음"; return; }
    try {
      const res = await S.api(`/api/v1/clinical-support/questionnaire-engine/responses/${encodeURIComponent(responseId)}/items`, {
        method: "POST",
        body: JSON.stringify({
          item_code: document.getElementById("q-item").value.trim(),
          value: document.getElementById("q-value").value.trim(),
        }),
      });
      if (!res.ok) throw Object.assign(new Error("qsave"), { status: res.status });
      out.textContent = "항목 저장됨";
    } catch (err) {
      if (await handleAuthError(err)) return;
      out.textContent = "항목 저장 실패";
    }
  });

  document.getElementById("q-finalize").addEventListener("click", async () => {
    const out = document.getElementById("q-body");
    if (!responseId) return;
    try {
      const res = await S.api(`/api/v1/clinical-support/questionnaire-engine/responses/${encodeURIComponent(responseId)}/finalize`, {
        method: "POST",
        body: "{}",
      });
      if (!res.ok) throw Object.assign(new Error("qfin"), { status: res.status });
      out.textContent = "확정됨";
    } catch (err) {
      if (await handleAuthError(err)) return;
      out.textContent = "확정 실패";
    }
  });

  document.getElementById("q-score").addEventListener("click", async () => {
    const out = document.getElementById("q-body");
    if (!responseId) return;
    try {
      const res = await S.api(`/api/v1/clinical-support/questionnaire-engine/responses/${encodeURIComponent(responseId)}/score`, {
        method: "POST",
        body: "{}",
      });
      if (!res.ok) throw Object.assign(new Error("qscore"), { status: res.status });
      const data = await res.json();
      out.textContent = JSON.stringify({
        score: data.score, status: data.status, version_id: data.version_id,
      }, null, 2);
    } catch (err) {
      if (await handleAuthError(err)) return;
      out.textContent = "채점 실패";
    }
  });

  document.getElementById("load-queries").addEventListener("click", async () => {
    const out = document.getElementById("queries-body");
    out.textContent = "불러오는 중…";
    try {
      const statusFilter = document.getElementById("q-status").value;
      const params = new URLSearchParams({ study_id: els.study.value });
      if (els.site.value) params.set("site_id", els.site.value);
      if (statusFilter) params.set("status", statusFilter);
      const res = await S.api(`/api/v1/clinical-support/queries?${params}`);
      if (!res.ok) throw Object.assign(new Error("queries"), { status: res.status });
      const rows = await res.json();
      out.innerHTML = `<table><thead><tr><th>ID</th><th>상태</th><th>대상</th><th>내용</th><th>배정</th></tr></thead><tbody>${
        rows.map((row) => `<tr>
          <td>${S.esc(row.id)}</td>
          <td>${S.esc(row.status)}</td>
          <td>${S.esc(row.target_type)}/${S.esc(row.target_id)}</td>
          <td>${S.esc(row.description || row.query_text || "")}</td>
          <td>${S.esc(row.assigned_role || "")} ${S.esc(row.assigned_user_id || "")}</td>
        </tr>`).join("")
      }</tbody></table>`;
    } catch (err) {
      if (await handleAuthError(err)) return;
      out.textContent = "질의 목록 실패";
    }
  });

  document.getElementById("create-query").addEventListener("click", async () => {
    const out = document.getElementById("query-detail");
    try {
      const res = await S.api("/api/v1/clinical-support/queries", {
        method: "POST",
        body: JSON.stringify({
          study_id: els.study.value,
          subject_id: els.subject.value || null,
          category: document.getElementById("new-query-cat").value.trim() || "manual",
          description: document.getElementById("new-query-text").value.trim(),
          severity: "medium",
        }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw Object.assign(new Error(detail || "create"), { status: res.status });
      }
      const data = await res.json();
      document.getElementById("query-id").value = data.id || "";
      out.textContent = JSON.stringify({ id: data.id, status: data.status }, null, 2);
    } catch (err) {
      if (await handleAuthError(err)) return;
      out.textContent = "질의 생성 실패 (백엔드 규칙 확인).";
    }
  });

  async function queryAction(path, body) {
    const out = document.getElementById("query-detail");
    const id = document.getElementById("query-id").value.trim();
    if (!id) { out.textContent = "Query ID 필요"; return; }
    try {
      const res = await S.api(`/api/v1/clinical-support/queries/${encodeURIComponent(id)}${path}`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (!res.ok) throw Object.assign(new Error("qact"), { status: res.status });
      const data = await res.json();
      out.textContent = JSON.stringify(data, null, 2);
    } catch (err) {
      if (await handleAuthError(err)) return;
      out.textContent = "질의 전이 실패 (허용되지 않는 전이일 수 있음).";
    }
  }

  document.getElementById("respond-query").addEventListener("click", () =>
    queryAction("/responses", { body: document.getElementById("query-response").value.trim() }));
  document.getElementById("resolve-query").addEventListener("click", () =>
    queryAction("/resolutions", { reason: "reviewed" }));
  document.getElementById("reopen-query").addEventListener("click", () =>
    queryAction("/reopens", { reason: "needs_more" }));

  document.getElementById("query-history").addEventListener("click", async () => {
    const out = document.getElementById("query-detail");
    const id = document.getElementById("query-id").value.trim();
    try {
      const res = await S.api(`/api/v1/clinical-support/queries/${encodeURIComponent(id)}/history`);
      if (!res.ok) throw Object.assign(new Error("hist"), { status: res.status });
      out.textContent = JSON.stringify(await res.json(), null, 2);
    } catch (err) {
      if (await handleAuthError(err)) return;
      out.textContent = "이력 조회 실패";
    }
  });

  async function lockCall(path, extra) {
    const out = document.getElementById("locks-body");
    try {
      const res = await S.api(`/api/v1/clinical-support/${path}`, {
        method: "POST",
        body: JSON.stringify({
          study_id: els.study.value,
          target_type: document.getElementById("lock-type").value.trim(),
          target_id: document.getElementById("lock-target").value.trim(),
          reason: document.getElementById("lock-reason").value.trim() || "ops-ui",
          ...extra,
        }),
      });
      const text = await res.text();
      let data = text;
      try { data = JSON.parse(text); } catch (_e) { /* keep text */ }
      if (!res.ok) {
        out.textContent = JSON.stringify({ status: res.status, body: data }, null, 2);
        return;
      }
      out.textContent = JSON.stringify(data, null, 2);
    } catch (err) {
      if (await handleAuthError(err)) return;
      out.textContent = "잠금 API 실패 (권한/전이 제한일 수 있음).";
    }
  }

  document.getElementById("lock-readiness").addEventListener("click", () => lockCall("locks/readiness", {}));
  document.getElementById("lock-request").addEventListener("click", () => lockCall("locks/requests", {}));
  document.getElementById("lock-apply").addEventListener("click", () => lockCall("locks/applications", {}));
  document.getElementById("unlock-request").addEventListener("click", async () => {
    const out = document.getElementById("locks-body");
    try {
      const res = await S.api("/api/v1/clinical-support/locks/unlock-requests", {
        method: "POST",
        body: JSON.stringify({
          study_id: els.study.value,
          target_type: document.getElementById("lock-type").value.trim(),
          target_id: document.getElementById("lock-target").value.trim(),
          reason: document.getElementById("lock-reason").value.trim() || "ops-ui",
        }),
      });
      if (!res.ok) throw Object.assign(new Error("unlock-req"), { status: res.status });
      const data = await res.json();
      if (data.id) document.getElementById("unlock-request-id").value = data.id;
      out.textContent = JSON.stringify(data, null, 2);
    } catch (err) {
      if (await handleAuthError(err)) return;
      out.textContent = "해제 요청 실패";
    }
  });

  document.getElementById("lock-history").addEventListener("click", async () => {
    const out = document.getElementById("locks-body");
    try {
      const params = new URLSearchParams({ study_id: els.study.value });
      const tt = document.getElementById("lock-type").value.trim();
      const tid = document.getElementById("lock-target").value.trim();
      if (tt) params.set("target_type", tt);
      if (tid) params.set("target_id", tid);
      const res = await S.api(`/api/v1/clinical-support/locks/history?${params}`);
      if (!res.ok) throw Object.assign(new Error("lh"), { status: res.status });
      out.textContent = JSON.stringify(await res.json(), null, 2);
    } catch (err) {
      if (await handleAuthError(err)) return;
      out.textContent = "잠금 이력 실패";
    }
  });

  async function unlockDecision(kind) {
    const out = document.getElementById("locks-body");
    const requestId = document.getElementById("unlock-request-id").value.trim();
    const reason = document.getElementById("unlock-decision-reason").value.trim() || "ops014";
    if (!requestId) { out.textContent = "unlock request id 필요"; return; }
    try {
      const res = await S.api(
        `/api/v1/clinical-support/locks/unlock-requests/${encodeURIComponent(requestId)}/${kind}`,
        { method: "POST", body: JSON.stringify({ reason }) },
      );
      if (!res.ok) throw Object.assign(new Error("unlock-dec"), { status: res.status });
      out.textContent = JSON.stringify(await res.json(), null, 2);
    } catch (err) {
      if (await handleAuthError(err)) return;
      out.textContent = "해제 결정 실패 (다른 사용자·역할 필요일 수 있음).";
    }
  }
  document.getElementById("unlock-approve").addEventListener("click", () => unlockDecision("approvals"));
  document.getElementById("unlock-reject").addEventListener("click", () => unlockDecision("rejections"));

  document.getElementById("obs-edit-try").addEventListener("click", async () => {
    const out = document.getElementById("locks-body");
    const obsId = document.getElementById("obs-edit-id").value.trim();
    const value = document.getElementById("obs-edit-value").value.trim();
    try {
      const res = await S.api(`/api/v1/clinical-support/observations/${encodeURIComponent(obsId)}/corrections`, {
        method: "POST",
        body: JSON.stringify({ reason: "ops014-lock-edit-try", value_number: Number(value) }),
      });
      out.textContent = JSON.stringify({ status: res.status, body: await res.json().catch(() => null) }, null, 2);
      if (!res.ok) out.textContent = `REJECTED status=${res.status}\n` + out.textContent;
    } catch (err) {
      if (await handleAuthError(err)) return;
      out.textContent = "수정 시도 실패";
    }
  });

  document.getElementById("load-audit").addEventListener("click", async () => {
    const out = document.getElementById("audit-body");
    out.textContent = "조회 중…";
    try {
      const params = new URLSearchParams({ study_id: els.study.value });
      if (els.site.value) params.set("site_id", els.site.value);
      if (els.subject.value) params.set("subject_id", els.subject.value);
      const action = document.getElementById("audit-action").value.trim();
      const tt = document.getElementById("audit-target-type").value.trim();
      const from = document.getElementById("audit-from").value;
      const to = document.getElementById("audit-to").value;
      if (action) params.set("action", action);
      if (tt) params.set("target_type", tt);
      if (from) params.set("date_from", `${from}T00:00:00Z`);
      if (to) params.set("date_to", `${to}T23:59:59Z`);
      const res = await S.api(`/api/v1/clinical-support/ops/audits?${params}`);
      if (!res.ok) throw Object.assign(new Error("audit"), { status: res.status });
      const rows = await res.json();
      out.innerHTML = `<p class="muted">사건별 integrity_status만 표시합니다. 전 사건 암호 검증을 주장하지 않습니다.</p>
        <table><thead><tr>
          <th>시각</th><th>행위자</th><th>역할</th><th>유형</th><th>사이트</th>
          <th>대상</th><th>개정</th><th>사유</th><th>상관ID</th><th>무결성</th>
        </tr></thead><tbody>${
        rows.map((row) => `<tr>
          <td>${S.esc(row.occurred_at)}</td>
          <td>${S.esc(row.actor_user_id)}</td>
          <td>${S.esc(row.actor_role || "")}</td>
          <td>${S.esc(row.event_type)}</td>
          <td>${S.esc(row.site_id || "")}</td>
          <td>${S.esc(row.target_type)}/${S.esc(row.target_id)}</td>
          <td>${S.esc(row.target_revision ?? "")}</td>
          <td>${S.esc(row.reason || "")}</td>
          <td>${S.esc(row.correlation_id || "")}</td>
          <td>${S.esc(row.integrity_status)}</td>
        </tr>`).join("")
      }</tbody></table>`;
    } catch (err) {
      if (await handleAuthError(err)) return;
      out.textContent = "감사 조회 실패";
    }
  });

  document.getElementById("load-protocol-info").addEventListener("click", async () => {
    const out = document.getElementById("protocol-body");
    try {
      const studyId = els.study.value;
      const res = await S.api(`/api/v1/clinical-support/studies/${encodeURIComponent(studyId)}`);
      if (!res.ok) throw Object.assign(new Error("proto"), { status: res.status });
      const data = await res.json();
      const code = (data.code || "").toUpperCase();
      out.textContent = JSON.stringify({
        id: data.id,
        code: data.code,
        name: data.name,
        protocol_version: data.protocol_version,
        study_kind: data.study_kind,
        notes: code.includes("AMD")
          ? {
              status: "DRAFT",
              unresolved_conflicts: ["AMD-WAVE", "AMD-SCHED-V6", "AMD-DATA-RETENTION", "AMD-DESIGN-RAND"],
              osdi_auto: false,
            }
          : { indication_hint: "DES may include OSDI" },
      }, null, 2);
    } catch (err) {
      if (await handleAuthError(err)) return;
      out.textContent = "연구 정보 실패";
    }
  });

  // Initial state
  if (!S.state.token) showLogin("");
  window.addEventListener("hashchange", () => {
    const name = (location.hash || "#dashboard").replace("#", "") || "dashboard";
    if (S.state.token) showPanel(name);
  });
})();
