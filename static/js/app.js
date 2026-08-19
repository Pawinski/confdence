(() => {
  const COPY = window.HEALTH_COPY;
  const store = window.ConfdenceStore;
  const card = window.ConfdenceCard;
  const incidents = window.ConfdenceIncidents;
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
