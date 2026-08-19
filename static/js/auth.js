window.ConfdenceAuth = (() => {
  const VERIFIER_KEY = "confdence.auth.v1";
  const SESSION_KEY = "confdence.auth.session";
  const ITERS = 210000;
  const MIN = 10;

  function empty() {
    return { algo: "pbkdf2-sha256", iters: ITERS, salt: "", hash: "" };
  }

  function loadVerifier() {
    try {
      const raw = localStorage.getItem(VERIFIER_KEY);
      return raw ? Object.assign(empty(), JSON.parse(raw)) : empty();
    } catch (err) {
      return empty();
    }
  }

  function hasPassword() {
    const row = loadVerifier();
    return Boolean(row.salt && row.hash);
  }

  function isUnlocked() {
    return sessionStorage.getItem(SESSION_KEY) === "1" && hasPassword();
  }

  function lock() {
    sessionStorage.removeItem(SESSION_KEY);
  }

  async function derive(password, saltBytes) {
    const enc = new TextEncoder();
    const key = await crypto.subtle.importKey(
      "raw",
      enc.encode(password),
      "PBKDF2",
      false,
      ["deriveBits"]
    );
    const bits = await crypto.subtle.deriveBits(
      { name: "PBKDF2", hash: "SHA-256", salt: saltBytes, iterations: ITERS },
      key,
      256
    );
    return new Uint8Array(bits);
  }

  function toHex(bytes) {
    return Array.from(bytes)
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  }

  function fromHex(hex) {
    const out = new Uint8Array(hex.length / 2);
    for (let i = 0; i < out.length; i += 1) {
      out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
    }
    return out;
  }

  async function setPassword(password) {
    const pw = String(password || "");
    if (pw.length < MIN) throw new Error("short");
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const hash = await derive(pw, salt);
    const row = {
      algo: "pbkdf2-sha256",
      iters: ITERS,
      salt: toHex(salt),
      hash: toHex(hash),
    };
    localStorage.setItem(VERIFIER_KEY, JSON.stringify(row));
    sessionStorage.setItem(SESSION_KEY, "1");
    return row;
  }

  async function unlock(password) {
    if (!hasPassword()) throw new Error("no_password");
    const row = loadVerifier();
    const got = await derive(String(password || ""), fromHex(row.salt));
    const expected = fromHex(row.hash);
    if (got.length !== expected.length) throw new Error("bad");
    let ok = 0;
    for (let i = 0; i < got.length; i += 1) ok |= got[i] ^ expected[i];
    if (ok !== 0) throw new Error("bad");
    sessionStorage.setItem(SESSION_KEY, "1");
  }

  return {
    MIN,
    hasPassword,
    isUnlocked,
    lock,
    setPassword,
    unlock,
    verifier: loadVerifier,
  };
})();
