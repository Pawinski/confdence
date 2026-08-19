window.ConfdenceIncidents = (() => {
  const KEY = "confdence.incidents.v1";
  const SEVERITIES = ["sev1", "sev2", "sev3", "sev4"];
  const STATUSES = ["active", "monitoring", "resolved"];
  const EVENT_KINDS = ["declared", "note", "step", "status", "notified", "commander"];

  function nowIso() {
    return new Date().toISOString();
  }

  function nid(prefix) {
    return (
      prefix +
      Date.now().toString(36) +
      Math.random().toString(36).slice(2, 8)
    );
  }

  function event(kind, text, extra) {
    if (EVENT_KINDS.indexOf(kind) === -1) throw new Error("invalid event");
    const row = {
      id: nid("evt_"),
      at: nowIso(),
      kind: kind,
      text: String(text || "").trim().slice(0, 500),
    };
    if (extra && extra.status) row.status = extra.status;
    return row;
  }

  function normalizeOne(raw) {
    const inc = raw && typeof raw === "object" ? raw : {};
    const severity = SEVERITIES.indexOf(inc.severity) === -1 ? "sev3" : inc.severity;
    const status = STATUSES.indexOf(inc.status) === -1 ? "active" : inc.status;
    const events = Array.isArray(inc.events) ? inc.events : [];
    return {
      id: inc.id || nid("inc_"),
      title: String(inc.title || "").trim().slice(0, 120),
      severity: severity,
      status: status,
      commander_name: inc.commander_name ? String(inc.commander_name).slice(0, 80) : "",
      commander_phone: inc.commander_phone ? String(inc.commander_phone).slice(0, 32) : "",
      commander_notified_at: inc.commander_notified_at || null,
      created_at: inc.created_at || nowIso(),
      resolved_at: inc.resolved_at || null,
      events: events.filter((row) => row && row.id && row.kind),
    };
  }

  function loadAll() {
    try {
      const raw = localStorage.getItem(KEY);
      const list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list.map(normalizeOne) : [];
    } catch (err) {
      return [];
    }
  }

  function saveAll(list) {
    localStorage.setItem(KEY, JSON.stringify(list.map(normalizeOne)));
    return loadAll();
  }

  function declareIncident(input) {
    const title = String((input && input.title) || "").trim();
    if (!title) throw new Error("title required");
    const inc = normalizeOne({
      title: title,
      severity: (input && input.severity) || "sev3",
      status: "active",
      commander_name: (input && input.commander_name) || "",
      commander_phone: (input && input.commander_phone) || "",
      events: [],
    });
    inc.events.push(
      event(
        "declared",
        title +
          (inc.commander_name ? " · commandant " + inc.commander_name : "")
      )
    );
    const list = loadAll();
    list.unshift(inc);
    saveAll(list);
    return inc;
  }

  function get(id) {
    return loadAll().filter((inc) => inc.id === id)[0] || null;
  }

  function update(id, fn) {
    const list = loadAll();
    const idx = list.findIndex((inc) => inc.id === id);
    if (idx === -1) throw new Error("not found");
    const next = fn(list[idx]);
    list[idx] = normalizeOne(next);
    saveAll(list);
    return list[idx];
  }

  function addNote(id, text) {
    const trimmed = String(text || "").trim();
    if (!trimmed) throw new Error("empty");
    return update(id, (inc) => {
      inc.events.push(event("note", trimmed));
      return inc;
    });
  }

  function addStep(id, text) {
    const trimmed = String(text || "").trim();
    if (!trimmed) throw new Error("empty");
    return update(id, (inc) => {
      inc.events.push(event("step", trimmed));
      return inc;
    });
  }

  function setStatus(id, status) {
    if (STATUSES.indexOf(status) === -1) throw new Error("invalid status");
    return update(id, (inc) => {
      inc.status = status;
      inc.resolved_at = status === "resolved" ? nowIso() : null;
      inc.events.push(event("status", status, { status: status }));
      return inc;
    });
  }

  function setCommander(id, name, phone) {
    return update(id, (inc) => {
      inc.commander_name = name || "";
      inc.commander_phone = phone || "";
      inc.events.push(
        event("commander", (name || "") + (phone ? " · " + phone : ""))
      );
      return inc;
    });
  }

  function digits(phone) {
    const s = String(phone || "").trim();
    const plus = s.charAt(0) === "+";
    const nums = s.replace(/\D/g, "");
    if (!nums) return "";
    return plus ? "+" + nums : nums;
  }

  function notifyBody(incident, patientName, copy) {
    const pack = copy || {};
    const template = pack.notifyBody || "{sev} {title} {name} {commander}";
    return template
      .replace("{sev}", String(incident.severity || "").toUpperCase())
      .replace("{title}", incident.title || "")
      .replace("{name}", patientName || "")
      .replace("{commander}", incident.commander_name || "");
  }

  function smsHref(phone, body) {
    const d = digits(phone);
    if (!d) return null;
    return "sms:" + encodeURIComponent(d) + "?&body=" + encodeURIComponent(body);
  }

  function markNotified(id) {
    return update(id, (inc) => {
      inc.commander_notified_at = nowIso();
      inc.events.push(event("notified", inc.commander_name || inc.commander_phone || ""));
      return inc;
    });
  }

  function openIncidents() {
    return loadAll().filter((inc) => inc.status !== "resolved");
  }

  return {
    KEY,
    SEVERITIES,
    STATUSES,
    loadAll,
    get,
    declareIncident,
    addNote,
    addStep,
    setStatus,
    setCommander,
    digits,
    notifyBody,
    smsHref,
    markNotified,
    openIncidents,
  };
})();
