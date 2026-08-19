window.ConfdenceMcp = (() => {
  const KEY = "confdence.mcp.v1";
  const VERSION = "2026-08-18";
  const REQUIRED = [
    "agents_read",
    "agents_write",
    "law5",
    "leaves_device",
    "can_revoke",
  ];

  function empty() {
    return {
      version: VERSION,
      enabled: false,
      acknowledged: [],
      consented_at: null,
    };
  }

  function load() {
    try {
      const raw = localStorage.getItem(KEY);
      const row = raw ? Object.assign(empty(), JSON.parse(raw)) : empty();
      if (row.version !== VERSION) return empty();
      return row;
    } catch (err) {
      return empty();
    }
  }

  function isEnabled() {
    const row = load();
    if (!row.enabled) return false;
    return REQUIRED.every((ack) => row.acknowledged.indexOf(ack) !== -1);
  }

  function enable(acknowledged) {
    const acks = REQUIRED.filter((ack) => acknowledged.indexOf(ack) !== -1);
    if (acks.length !== REQUIRED.length) {
      throw new Error("incomplete consent");
    }
    const row = {
      version: VERSION,
      enabled: true,
      acknowledged: REQUIRED.slice(),
      consented_at: new Date().toISOString(),
    };
    localStorage.setItem(KEY, JSON.stringify(row));
    return row;
  }

  function disable() {
    const row = empty();
    row.disabled_at = new Date().toISOString();
    localStorage.setItem(KEY, JSON.stringify(row));
    return row;
  }

  const AGENT_KEY = "confdence.agent.v1";

  function agentMeta() {
    try {
      const raw = localStorage.getItem(AGENT_KEY);
      return raw ? JSON.parse(raw) : { hash: "" };
    } catch (err) {
      return { hash: "" };
    }
  }

  function hasAgentToken() {
    return Boolean(agentMeta().hash);
  }

  function revokeAgentToken() {
    localStorage.removeItem(AGENT_KEY);
  }

  async function mintAgentToken() {
    const bytes = crypto.getRandomValues(new Uint8Array(32));
    const token = btoa(String.fromCharCode.apply(null, Array.from(bytes)))
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/g, "");
    const digest = await crypto.subtle.digest(
      "SHA-256",
      new TextEncoder().encode(token)
    );
    const hash = Array.from(new Uint8Array(digest))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
    localStorage.setItem(
      AGENT_KEY,
      JSON.stringify({ hash: hash, created_at: new Date().toISOString() })
    );
    return { token: token, hash: hash };
  }

  function pack(record, incidents, consent, auth) {
    return {
      consent: consent || load(),
      auth: auth || null,
      agent: hasAgentToken() ? { hash: agentMeta().hash } : null,
      record: record || {},
      incidents: incidents || [],
    };
  }

  return {
    KEY,
    VERSION,
    REQUIRED,
    load,
    isEnabled,
    enable,
    disable,
    pack,
    hasAgentToken,
    mintAgentToken,
    revokeAgentToken,
    agentMeta,
  };
})();
