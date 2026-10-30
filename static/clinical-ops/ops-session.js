/** Memory-only clinical operations session. Do not persist JWT in browser storage. */
(function (global) {
  const state = {
    token: "",
    userId: "",
    role: "",
    studyId: "",
    siteId: "",
    subjectId: "",
    requestSeq: 0,
    aborted: false,
  };

  function clearSensitive() {
    state.token = "";
    state.userId = "";
    state.role = "";
    state.studyId = "";
    state.siteId = "";
    state.subjectId = "";
    // Bump seq so in-flight fetches become STALE; do not permanently block later calls.
    state.requestSeq += 1;
    state.aborted = false;
  }

  function setAuth(token, userId, role) {
    state.token = token || "";
    state.userId = userId || "";
    state.role = role || "";
    state.aborted = false;
  }

  function setScope(studyId, siteId, subjectId) {
    state.studyId = studyId || "";
    state.siteId = siteId || "";
    state.subjectId = subjectId || "";
    state.requestSeq += 1;
  }

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[char]));
  }

  async function api(path, options = {}) {
    const seq = ++state.requestSeq;
    const headers = { ...(options.headers || {}) };
    if (state.token) headers.Authorization = `Bearer ${state.token}`;
    if (options.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
    const response = await fetch(path, { ...options, headers });
    if (seq !== state.requestSeq || state.aborted) {
      const err = new Error("stale");
      err.code = "STALE";
      throw err;
    }
    if (response.status === 401 || response.status === 403) {
      clearSensitive();
      const err = new Error("auth");
      err.code = "AUTH";
      err.status = response.status;
      throw err;
    }
    return response;
  }

  async function login(username, password) {
    const body = new URLSearchParams({ username, password });
    const response = await fetch("/api/v1/auth/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    if (!response.ok) {
      const err = new Error("login_failed");
      err.status = response.status;
      throw err;
    }
    const payload = await response.json();
    const token = payload.access_token;
    const me = await fetch("/api/v1/clinical-support/ops/session", {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!me.ok) {
      const err = new Error("session_failed");
      err.status = me.status;
      throw err;
    }
    const session = await me.json();
    setAuth(token, session.user_id, session.role);
    return session;
  }

  function logout() {
    clearSensitive();
  }

  global.ClinicalOpsSession = {
    state,
    clearSensitive,
    setAuth,
    setScope,
    esc,
    api,
    login,
    logout,
  };
})(window);
