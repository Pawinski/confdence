window.ConfdenceStore = (() => {
  const KEY = "confdence.record.v1";
  const DEFAULT = {
    display_name: "Alexander Pawinski",
    preferred_lang: "fr",
    blood_abo: null,
    blood_rh: null,
    blood_source: null,
    blood_confirmed_on: null,
    allergies: [],
    medications: [],
    conditions: [],
    hospitals: [],
    professionals: [],
    emergency_name: null,
    emergency_phone: null,
    updated_at: null,
  };

  function normalize(raw) {
    const r = Object.assign({}, DEFAULT, raw || {});
    r.allergies = Array.isArray(r.allergies) ? r.allergies : [];
    r.medications = Array.isArray(r.medications) ? r.medications : [];
    r.conditions = Array.isArray(r.conditions) ? r.conditions : [];
    r.hospitals = Array.isArray(r.hospitals) ? r.hospitals : [];
    r.professionals = Array.isArray(r.professionals) ? r.professionals : [];
    r.blood_type = r.blood_abo && r.blood_rh ? r.blood_abo + r.blood_rh : null;
    return r;
  }

  function load() {
    try {
      const raw = localStorage.getItem(KEY);
      return normalize(raw ? JSON.parse(raw) : null);
    } catch (err) {
      return normalize(null);
    }
  }

  function save(record) {
    const next = normalize(record);
    next.updated_at = new Date().toISOString();
    localStorage.setItem(KEY, JSON.stringify(next));
    return next;
  }

  return { KEY, DEFAULT, normalize, load, save };
})();
