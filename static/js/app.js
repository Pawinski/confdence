(() => {
  const COPY = window.HEALTH_COPY;
  const store = window.ConfdenceStore;
  const card = window.ConfdenceCard;
  const incidents = window.ConfdenceIncidents;
  const mcpGate = window.ConfdenceMcp;
  const auth = window.ConfdenceAuth;
  const state = {
    lang: localStorage.getItem("health.lang") || "fr",
    record: store.load(),
    incidentId: null,
  };

  const $ = (id) => document.getElementById(id);

  function t(key) {
    const pack = COPY[state.lang] || COPY.fr;
    return pack[key] || COPY.fr[key] || key;
  }

  function copyPack() {
    return COPY[state.lang] || COPY.fr;
  }

  function applyLang() {
    document.documentElement.lang = state.lang;
    document.title = t("mark");
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (key) el.textContent = t(key);
    });
    $("lang-toggle").textContent = state.lang === "fr" ? "EN" : "FR";
    renderIncidentList();
    if (state.incidentId) renderIncident();
    renderMcp();
  }

  function toast(msg) {
    const el = $("toast");
    el.textContent = msg;
    el.classList.remove("hidden");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.add("hidden"), 2200);
  }

  function renderList(id, items, line) {
    const ul = $(id);
    ul.innerHTML = "";
    if (!items || !items.length) {
      const li = document.createElement("li");
      li.className = "empty";
      li.textContent = t("none");
      ul.appendChild(li);
      return;
    }
    items.forEach((item) => {
      const li = document.createElement("li");
      li.appendChild(line(item));
      ul.appendChild(li);
    });
  }

  function allergyLine(item) {
    const wrap = document.createElement("span");
    const strong = document.createElement("strong");
    strong.textContent = item.name;
    wrap.appendChild(strong);
    const sev = document.createElement("span");
    sev.className = "sev-" + item.severity;
    const labels = t("sev") || {};
    sev.textContent = " · " + (labels[item.severity] || item.severity);
    wrap.appendChild(sev);
    if (item.detail) wrap.appendChild(document.createTextNode(" — " + item.detail));
    return wrap;
  }

  function medLine(item) {
    const wrap = document.createElement("span");
    const strong = document.createElement("strong");
    strong.textContent = item.name;
    wrap.appendChild(strong);
    const extra = [item.dose, item.schedule].filter(Boolean).join(" · ");
    if (extra) wrap.appendChild(document.createTextNode(" · " + extra));
    return wrap;
  }

  function condLine(item) {
    const wrap = document.createElement("span");
    const strong = document.createElement("strong");
    strong.textContent = item.name;
    wrap.appendChild(strong);
    if (item.since) wrap.appendChild(document.createTextNode(" · " + item.since));
    return wrap;
  }

  function hospitalLine(item) {
    const wrap = document.createElement("span");
    const strong = document.createElement("strong");
    strong.textContent = item.name;
    wrap.appendChild(strong);
    const extra = [item.city, item.note].filter(Boolean).join(" · ");
    if (extra) wrap.appendChild(document.createTextNode(" · " + extra));
    return wrap;
  }

  function proLine(item) {
    const wrap = document.createElement("span");
    const strong = document.createElement("strong");
    strong.textContent = item.name;
    wrap.appendChild(strong);
    const extra = [item.role, item.phone].filter(Boolean).join(" · ");
    if (extra) wrap.appendChild(document.createTextNode(" · " + extra));
    return wrap;
  }

  function metaText(r) {
    const bits = [];
    if (r.blood_source) bits.push(card.sourceLabel(r.blood_source, copyPack()));
    if (r.blood_confirmed_on) bits.push(r.blood_confirmed_on);
    return bits.join(" · ");
  }

  function renderRecord() {
    const r = state.record;
    $("blood-type").textContent = r.blood_type || "—";
    $("blood-type").classList.toggle("is-empty", !r.blood_type);
    $("blood-meta").textContent = r.blood_type
      ? metaText(r)
      : t("addBloodHint");
    $("holder-name").textContent = r.display_name;
    renderList("allergies", r.allergies, allergyLine);
    renderList("medications", r.medications, medLine);
    renderList("conditions", r.conditions, condLine);
    renderList("hospitals", r.hospitals, hospitalLine);
    renderList("professionals", r.professionals, proLine);
    $("emergency").textContent =
      [r.emergency_name, r.emergency_phone].filter(Boolean).join(" · ") || t("none");
    renderIncidentList();
  }

  function when(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString(state.lang === "fr" ? "fr-CA" : "en-CA", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function statusLabel(status) {
    if (status === "monitoring") return t("statusMonitoringLabel");
    if (status === "resolved") return t("statusResolvedLabel");
    return t("statusActiveLabel");
  }

  function kindLabel(kind) {
    const map = {
      declared: t("kindDeclared"),
      note: t("kindNote"),
      step: t("kindStep"),
      status: t("kindStatus"),
      notified: t("kindNotified"),
      commander: t("kindCommander"),
    };
    return map[kind] || kind;
  }

  function renderIncidentList() {
    const ul = $("incident-list");
    if (!ul) return;
    ul.innerHTML = "";
    const list = incidents.loadAll();
    if (!list.length) {
      const li = document.createElement("li");
      li.className = "empty";
      li.textContent = t("noIncidents");
      ul.appendChild(li);
      return;
    }
    list.forEach((inc) => {
      const li = document.createElement("li");
      li.className = "share-item";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "text-btn inc-open";
      btn.textContent =
        inc.severity.toUpperCase() +
        " · " +
        inc.title +
        " · " +
        statusLabel(inc.status);
      btn.addEventListener("click", () => openIncident(inc.id));
      li.appendChild(btn);
      ul.appendChild(li);
    });
  }

  function renderIncident() {
    const inc = incidents.get(state.incidentId);
    if (!inc) {
      closeIncident();
      return;
    }
    $("inc-sev").textContent = t(inc.severity);
    $("inc-title").textContent = inc.title;
    $("inc-commander").textContent = inc.commander_name
      ? t("commanderLine").replace("{name}", inc.commander_name) +
        (inc.commander_notified_at ? " · " + t("notifiedAt") : "")
      : t("commanderNone");
    $("inc-status-line").textContent = t("statusLine")
      .replace("{status}", statusLabel(inc.status))
      .replace("{when}", when(inc.created_at));
    const log = $("inc-log");
    log.innerHTML = "";
    inc.events.forEach((row) => {
      const li = document.createElement("li");
      li.className = "timeline-item kind-" + row.kind;
      const head = document.createElement("p");
      head.className = "timeline-head";
      head.textContent = kindLabel(row.kind) + " · " + when(row.at);
      const body = document.createElement("p");
      body.className = "body";
      body.textContent = row.kind === "status" ? statusLabel(row.status || row.text) : row.text;
      li.appendChild(head);
      li.appendChild(body);
      log.appendChild(li);
    });
    $("inc-resolve").classList.toggle("hidden", inc.status === "resolved");
    $("inc-monitor").classList.toggle("hidden", inc.status !== "active");
    $("inc-reopen").classList.toggle("hidden", inc.status !== "resolved");
  }

  function renderHold() {
    const r = state.record;
    $("hold-name").textContent = r.display_name;
    $("hold-blood").textContent = r.blood_type || "—";
    $("hold-blood").classList.toggle("is-empty", !r.blood_type);
    $("hold-meta").textContent = metaText(r);
    renderList("hold-allergies", r.allergies, allergyLine);
    renderList("hold-medications", r.medications, medLine);
    renderList("hold-conditions", r.conditions, condLine);
    renderList("hold-hospitals", r.hospitals, hospitalLine);
    renderList("hold-professionals", r.professionals, proLine);
    $("hold-emergency").textContent =
      [r.emergency_name, r.emergency_phone].filter(Boolean).join(" · ") || t("none");
  }

  function lines(text) {
    return text
      .split("\n")
      .map((row) => row.trim())
      .filter(Boolean)
      .map((row) => row.split("|").map((part) => part.trim()));
  }

  function fillForm() {
    const r = state.record;
    const form = $("edit-form");
    form.display_name.value = r.display_name || "";
    form.blood_abo.value = r.blood_abo || "";
    form.blood_rh.value = r.blood_rh || "";
    form.blood_source.value = r.blood_source || "";
    form.blood_confirmed_on.value = r.blood_confirmed_on || "";
    form.allergies.value = (r.allergies || [])
      .map((a) => [a.name, a.severity, a.detail].filter(Boolean).join(" | "))
      .join("\n");
    form.medications.value = (r.medications || [])
      .map((m) => [m.name, m.dose, m.schedule].filter(Boolean).join(" | "))
      .join("\n");
    form.conditions.value = (r.conditions || [])
      .map((c) => [c.name, c.since].filter(Boolean).join(" | "))
      .join("\n");
    form.hospitals.value = (r.hospitals || [])
      .map((h) => [h.name, h.city, h.note].filter(Boolean).join(" | "))
      .join("\n");
    form.professionals.value = (r.professionals || [])
      .map((p) => [p.name, p.role, p.phone].filter(Boolean).join(" | "))
      .join("\n");
    form.emergency_name.value = r.emergency_name || "";
    form.emergency_phone.value = r.emergency_phone || "";
  }

  function saveRecord(event) {
    event.preventDefault();
    const form = $("edit-form");
    const abo = form.blood_abo.value || null;
    const rh = form.blood_rh.value || null;
    if (Boolean(abo) !== Boolean(rh)) {
      toast(t("incompleteBlood"));
      return;
    }
    if (abo && !form.blood_source.value) {
      toast(t("needSource"));
      return;
    }
    state.record = store.save({
      display_name: form.display_name.value,
      preferred_lang: state.lang,
      blood_abo: abo,
      blood_rh: rh,
      blood_source: form.blood_source.value || null,
      blood_confirmed_on: form.blood_confirmed_on.value || null,
      allergies: lines(form.allergies.value).map((parts) => ({
        name: parts[0],
        severity: parts[1] || "moderate",
        detail: parts[2] || "",
      })),
      medications: lines(form.medications.value).map((parts) => ({
        name: parts[0],
        dose: parts[1] || "",
        schedule: parts[2] || "",
      })),
      conditions: lines(form.conditions.value).map((parts) => ({
        name: parts[0],
        since: parts[1] || "",
      })),
      hospitals: lines(form.hospitals.value).map((parts) => ({
        name: parts[0],
        city: parts[1] || "",
        note: parts[2] || "",
      })),
      professionals: lines(form.professionals.value).map((parts) => ({
        name: parts[0],
        role: parts[1] || "",
        phone: parts[2] || "",
      })),
      emergency_name: form.emergency_name.value || null,
      emergency_phone: form.emergency_phone.value || null,
    });
    renderRecord();
    $("edit-dialog").close();
    toast(t("saved"));
    syncMcpSnapshot();
  }

  function openHold() {
    renderHold();
    $("hold-card").classList.remove("hidden");
    $("workspace").classList.add("hidden");
  }

  function closeHold() {
    $("hold-card").classList.add("hidden");
    $("workspace").classList.remove("hidden");
  }

  function openIncident(id) {
    state.incidentId = id;
    $("hold-card").classList.add("hidden");
    $("workspace").classList.add("hidden");
    $("incident-view").classList.remove("hidden");
    renderIncident();
  }

  function closeIncident() {
    state.incidentId = null;
    $("incident-view").classList.add("hidden");
    $("workspace").classList.remove("hidden");
    renderIncidentList();
  }

  function openDeclare() {
    const form = $("declare-form");
    form.title.value = "";
    form.severity.value = "sev3";
    form.commander_name.value = state.record.emergency_name || "";
    form.commander_phone.value = state.record.emergency_phone || "";
    $("declare-dialog").showModal();
  }

  function declareIncident(event) {
    event.preventDefault();
    const form = $("declare-form");
    const title = form.title.value.trim();
    if (!title) {
      toast(t("needTitle"));
      return;
    }
    const inc = incidents.declareIncident({
      title: title,
      severity: form.severity.value,
      commander_name: form.commander_name.value,
      commander_phone: form.commander_phone.value,
    });
    $("declare-dialog").close();
    openIncident(inc.id);
  }

  function appendLog(event) {
    event.preventDefault();
    if (!state.incidentId) return;
    const form = $("inc-log-form");
    const text = form.text.value.trim();
    if (!text) {
      toast(t("needLog"));
      return;
    }
    const as = (event.submitter && event.submitter.value) || "note";
    try {
      if (as === "step") incidents.addStep(state.incidentId, text);
      else incidents.addNote(state.incidentId, text);
    } catch (err) {
      toast(t("needLog"));
      return;
    }
    form.reset();
    renderIncident();
  }

  function notifyCommander() {
    const inc = incidents.get(state.incidentId);
    if (!inc) return;
    const body = incidents.notifyBody(inc, state.record.display_name, copyPack());
    const href = incidents.smsHref(inc.commander_phone, body);
    if (href) {
      incidents.markNotified(inc.id);
      window.location.href = href;
      toast(t("notifyOpened"));
    } else {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(body).then(() => toast(t("notifyCopied")));
      } else {
        toast(t("needCommanderPhone"));
      }
    }
    renderIncident();
  }

  function bind() {
    $("lang-toggle").addEventListener("click", () => {
      state.lang = state.lang === "fr" ? "en" : "fr";
      localStorage.setItem("health.lang", state.lang);
      state.record.preferred_lang = state.lang;
      store.save(state.record);
      applyLang();
      renderRecord();
      if (!$("hold-card").classList.contains("hidden")) renderHold();
      if (state.incidentId) renderIncident();
    });
    $("auth-set").addEventListener("click", () => $("auth-set-dialog").showModal());
    $("auth-set-cancel").addEventListener("click", () => $("auth-set-dialog").close());
    $("auth-set-form").addEventListener("submit", submitSetPassword);
    $("auth-unlock").addEventListener("click", () => $("auth-unlock-dialog").showModal());
    $("auth-unlock-cancel").addEventListener("click", () => $("auth-unlock-dialog").close());
    $("auth-unlock-form").addEventListener("submit", submitUnlock);
    $("auth-lock").addEventListener("click", submitLock);
    $("mcp-toggle").addEventListener("click", toggleMcp);
    $("mcp-cancel").addEventListener("click", () => $("mcp-dialog").close());
    $("mcp-form").addEventListener("submit", acceptMcp);
    $("mcp-form").addEventListener("change", refreshMcpConfirm);
    $("mcp-pack").addEventListener("click", downloadPack);
    $("declare-btn").addEventListener("click", openDeclare);
    $("declare-cancel").addEventListener("click", () => $("declare-dialog").close());
    $("declare-form").addEventListener("submit", declareIncident);
    $("inc-log-form").addEventListener("submit", appendLog);
    $("inc-notify").addEventListener("click", notifyCommander);
    $("inc-monitor").addEventListener("click", () => {
      incidents.setStatus(state.incidentId, "monitoring");
      renderIncident();
    });
    $("inc-resolve").addEventListener("click", () => {
      incidents.setStatus(state.incidentId, "resolved");
      renderIncident();
    });
    $("inc-reopen").addEventListener("click", () => {
      incidents.setStatus(state.incidentId, "active");
      renderIncident();
    });
    $("inc-back").addEventListener("click", closeIncident);
    $("edit-blood").addEventListener("click", () => {
      fillForm();
      $("edit-dialog").showModal();
    });
    $("edit-cancel").addEventListener("click", () => $("edit-dialog").close());
    $("edit-form").addEventListener("submit", saveRecord);
    $("hold-btn").addEventListener("click", openHold);
    $("hold-done").addEventListener("click", closeHold);
    $("print-btn").addEventListener("click", () => window.print());
    $("save-card").addEventListener("click", () => {
      card.shareOrDownload(state.record, copyPack()).then((how) => {
        toast(how === "shared" ? t("shared") : t("cardSaved"));
      }).catch((err) => toast(err.message));
    });
  }

  function csrfToken() {
    const match = document.cookie.match(/(?:^|; )health_csrf=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  function mcpSnippet() {
    return [
      "[mcp_servers.confdence]",
      'command = "/Users/apawinski/dev/health/.venv/bin/python"',
      'args = ["/Users/apawinski/dev/health/mcp_server.py"]',
      "",
      t("mcpInstallHelp"),
    ].join("\n");
  }

  function renderMcp() {
    const on = mcpGate.isEnabled();
    const hasPw = auth.hasPassword();
    const unlocked = auth.isUnlocked();
    let stateText = t("mcpOff");
    if (!hasPw) stateText = t("mcpNeedAuth");
    else if (!unlocked) stateText = t("authLocked");
    else if (on) stateText = t("mcpOn");
    $("mcp-state").textContent = stateText;
    $("auth-set").classList.toggle("hidden", hasPw);
    $("auth-unlock").classList.toggle("hidden", !hasPw || unlocked);
    $("auth-lock").classList.toggle("hidden", !unlocked);
    $("mcp-toggle").classList.toggle("hidden", !unlocked);
    $("mcp-toggle").textContent = on ? t("mcpDisable") : t("mcpEnable");
    $("mcp-toggle").classList.toggle("primary", !on);
    $("mcp-toggle").classList.toggle("ghost", on);
    $("mcp-pack").classList.toggle("hidden", !on || !unlocked);
    $("mcp-snippet").classList.toggle("hidden", !on || !unlocked);
    $("mcp-snippet").textContent = on && unlocked ? mcpSnippet() : "";
  }

  function mcpAcksFromForm() {
    const form = $("mcp-form");
    return mcpGate.REQUIRED.filter((name) => form[name] && form[name].checked);
  }

  function refreshMcpConfirm() {
    $("mcp-confirm").disabled = mcpAcksFromForm().length !== mcpGate.REQUIRED.length;
  }

  function downloadPack() {
    const payload = mcpGate.pack(
      state.record,
      incidents.loadAll(),
      mcpGate.load(),
      auth.hasPassword() ? auth.verifier() : null
    );
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "confdence-agent-pack.json";
    a.click();
    URL.revokeObjectURL(url);
    toast(t("mcpPackSaved"));
  }

  async function syncMcpSnapshot() {
    if (!mcpGate.isEnabled()) return;
    const token = csrfToken();
    if (!token || location.protocol === "file:") return;
    try {
      await fetch("/api/mcp/snapshot", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": token,
        },
        body: JSON.stringify({
          record: state.record,
          incidents: incidents.loadAll(),
        }),
      });
    } catch (err) {
      /* Pages / file — pack download is the path */
    }
  }

  async function persistConsent(enabled, acknowledged) {
    const token = csrfToken();
    if (!token || location.protocol === "file:") return;
    try {
      await fetch("/api/mcp/consent", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": token,
        },
        body: JSON.stringify({ enabled: enabled, acknowledged: acknowledged || [] }),
      });
    } catch (err) {
      /* local API optional */
    }
  }

  function openMcpConsent() {
    const form = $("mcp-form");
    mcpGate.REQUIRED.forEach((name) => {
      if (form[name]) form[name].checked = false;
    });
    refreshMcpConfirm();
    $("mcp-dialog").showModal();
  }

  function acceptMcp(event) {
    event.preventDefault();
    const acks = mcpAcksFromForm();
    if (acks.length !== mcpGate.REQUIRED.length) {
      toast(t("mcpNeedChecks"));
      return;
    }
    mcpGate.enable(acks);
    $("mcp-dialog").close();
    renderMcp();
    persistConsent(true, acks);
    syncMcpSnapshot();
    downloadPack();
  }

  async function submitSetPassword(event) {
    event.preventDefault();
    const form = $("auth-set-form");
    const pw = form.password.value;
    const again = form.confirm.value;
    if (pw !== again) {
      toast(t("authNeedMatch"));
      return;
    }
    if (pw.length < auth.MIN) {
      toast(t("authTooShort"));
      return;
    }
    try {
      await auth.setPassword(pw);
    } catch (err) {
      toast(t("authTooShort"));
      return;
    }
    await persistAuth("set", pw);
    form.reset();
    $("auth-set-dialog").close();
    renderMcp();
    toast(t("authReady"));
  }

  async function submitUnlock(event) {
    event.preventDefault();
    const form = $("auth-unlock-form");
    const pw = form.password.value;
    try {
      await auth.unlock(pw);
    } catch (err) {
      toast(t("authBad"));
      return;
    }
    await persistAuth("unlock", pw);
    form.reset();
    $("auth-unlock-dialog").close();
    renderMcp();
    toast(t("authUnlocked"));
  }

  async function submitLock() {
    auth.lock();
    await persistAuth("lock", "");
    if (mcpGate.isEnabled()) {
      /* consent stays; connection is what lock cuts */
    }
    renderMcp();
    toast(t("authLocked"));
  }

  async function persistAuth(kind, password) {
    const token = csrfToken();
    if (!token || location.protocol === "file:") return;
    const path =
      kind === "set" ? "/api/auth/set" : kind === "unlock" ? "/api/auth/unlock" : "/api/auth/lock";
    const body = kind === "lock" ? {} : { password: password };
    try {
      await fetch(path, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": token,
        },
        body: JSON.stringify(body),
      });
    } catch (err) {
      /* Pages / file — Mac unlock is the agent gate */
    }
  }

  function toggleMcp() {
    if (!auth.isUnlocked()) {
      toast(t("mcpNeedAuth"));
      if (!auth.hasPassword()) $("auth-set-dialog").showModal();
      else $("auth-unlock-dialog").showModal();
      return;
    }
    if (mcpGate.isEnabled()) {
      mcpGate.disable();
      persistConsent(false, []);
      renderMcp();
      return;
    }
    openMcpConsent();
  }

  function registerShell() {
    if (!("serviceWorker" in navigator)) return;
    const host = location.hostname;
    const secure =
      location.protocol === "https:" ||
      host === "localhost" ||
      host === "127.0.0.1";
    if (!secure) return;
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }

  applyLang();
  bind();
  renderRecord();
  registerShell();
})();
