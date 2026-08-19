window.ConfdenceCard = (() => {
  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function sourceLabel(source, copy) {
    if (source === "lab") return copy.sourceLab;
    if (source === "booklet") return copy.sourceBooklet;
    if (source === "self") return copy.sourceSelf;
    return "";
  }

  function listHtml(items, line, empty) {
    if (!items || !items.length) {
      return "<li class=\"empty\">" + escapeHtml(empty) + "</li>";
    }
    return items.map((item) => "<li>" + line(item) + "</li>").join("");
  }

  function build(record, copy) {
    const r = record || {};
    const sev = copy.sev || {};
    const meta = [sourceLabel(r.blood_source, copy), r.blood_confirmed_on]
      .filter(Boolean)
      .join(" · ");
    const allergies = listHtml(
      r.allergies,
      (item) =>
        "<strong>" +
        escapeHtml(item.name) +
        "</strong> · " +
        escapeHtml(sev[item.severity] || item.severity) +
        (item.detail ? " — " + escapeHtml(item.detail) : ""),
      copy.none
    );
    const meds = listHtml(
      r.medications,
      (item) =>
        "<strong>" +
        escapeHtml(item.name) +
        "</strong>" +
        (item.dose ? " · " + escapeHtml(item.dose) : "") +
        (item.schedule ? " · " + escapeHtml(item.schedule) : ""),
      copy.none
    );
    const conds = listHtml(
      r.conditions,
      (item) =>
        "<strong>" +
        escapeHtml(item.name) +
        "</strong>" +
        (item.since ? " · " + escapeHtml(item.since) : ""),
      copy.none
    );
    const emergency =
      [r.emergency_name, r.emergency_phone].filter(Boolean).join(" · ") || copy.none;
    const hospitals = listHtml(
      r.hospitals,
      (item) =>
        "<strong>" +
        escapeHtml(item.name) +
        "</strong>" +
        (item.city ? " · " + escapeHtml(item.city) : "") +
        (item.note ? " · " + escapeHtml(item.note) : ""),
      copy.none
    );
    const professionals = listHtml(
      r.professionals,
      (item) =>
        "<strong>" +
        escapeHtml(item.name) +
        "</strong>" +
        (item.role ? " · " + escapeHtml(item.role) : "") +
        (item.phone ? " · " + escapeHtml(item.phone) : ""),
      copy.none
    );

    return `<!DOCTYPE html>
<html lang="${escapeHtml(r.preferred_lang || "fr")}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Confdence</title>
<style>
  :root { --bg:#f3efe6; --ink:#1b1814; --muted:#5c564c; --line:#d4cdc0; --card:#fffaf1; --blood:#8f1d1d; --warn:#6b3a1f; --font:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif; --ui:"Avenir Next","Segoe UI",system-ui,sans-serif; }
  * { box-sizing: border-box; }
  html, body { margin:0; background:var(--bg); color:var(--ink); font-family:var(--ui); }
  .sheet { max-width:40rem; margin:0 auto; padding:1.25rem; }
  .kicker { letter-spacing:.14em; text-transform:uppercase; font-size:.8rem; color:var(--muted); }
  .name { font-family:var(--font); font-size:1.6rem; margin:.2rem 0 1rem; }
  .eyebrow { color:var(--muted); letter-spacing:.08em; text-transform:uppercase; font-size:.78rem; margin:0; }
  .blood { font-family:var(--font); font-size:clamp(4rem,18vw,6.5rem); line-height:.95; color:var(--blood); margin:.2rem 0; }
  .meta, .fine { color:var(--muted); }
  .warn { color:var(--warn); }
  .grid { display:grid; gap:.8rem; margin:1rem 0; }
  @media (min-width:640px) { .grid { grid-template-columns:1fr 1fr; } }
  h2 { font-family:var(--font); font-weight:500; font-size:1.1rem; margin:0 0 .4rem; }
  ul { list-style:none; margin:0; padding:0; }
  .empty { color:var(--muted); }
  @media print {
    @page { size: letter; margin: 12mm; }
    html, body { background: white; }
    .sheet { padding: 0; }
  }
</style>
</head>
<body>
  <article class="sheet">
    <p class="kicker">Confdence</p>
    <p class="name">${escapeHtml(r.display_name || "")}</p>
    <p class="eyebrow">${escapeHtml(copy.bloodType)}</p>
    <p class="blood">${escapeHtml(r.blood_type || "—")}</p>
    <p class="meta">${escapeHtml(meta)}</p>
    <p class="warn">${escapeHtml(copy.transfusionNote)}</p>
    <div class="grid">
      <section><h2>${escapeHtml(copy.allergies)}</h2><ul>${allergies}</ul></section>
      <section><h2>${escapeHtml(copy.medications)}</h2><ul>${meds}</ul></section>
      <section><h2>${escapeHtml(copy.conditions)}</h2><ul>${conds}</ul></section>
      <section><h2>${escapeHtml(copy.emergency)}</h2><p>${escapeHtml(emergency)}</p></section>
      <section><h2>${escapeHtml(copy.hospitals)}</h2><ul>${hospitals}</ul></section>
      <section><h2>${escapeHtml(copy.professionals)}</h2><ul>${professionals}</ul></section>
    </div>
    <p class="fine">${escapeHtml(copy.cardFooter)}</p>
  </article>
</body>
</html>`;
  }

  function filename(record) {
    const slug = String(record && record.display_name ? record.display_name : "card")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");
    return "confdence-" + (slug || "card") + ".html";
  }

  async function shareOrDownload(record, copy) {
    const html = build(record, copy);
    const name = filename(record);
    const file = new File([html], name, { type: "text/html" });
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      await navigator.share({ files: [file], title: "Confdence" });
      return "shared";
    }
    const url = URL.createObjectURL(new Blob([html], { type: "text/html" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
    return "downloaded";
  }

  return { escapeHtml, sourceLabel, build, filename, shareOrDownload };
})();
