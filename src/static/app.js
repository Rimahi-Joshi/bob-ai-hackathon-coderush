let current = null;
let scoring = null;
let travel = {};
let tab = "home";
let open = null;   // key of the expanded row, e.g. "o:T07-1" or "r:T07"

const $ = (s) => document.querySelector(s);

const FIELD = {
  distinguishing_marks: "scar / marks", clothing_upper: "top", clothing_lower: "trousers",
  footwear: "footwear", accessories: "bag / items", hair: "hair", height: "height",
  apparent_age: "age", build: "build", complexion: "complexion",
};
const DOCS = { lead_sheet: "Investigative Lead Sheet", appeal: "Public Appeal Notice", case_file: "Case File Draft" };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const KIND = { family: "Family report", tip: "Phone tip", cctv: "CCTV note" };

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
const hhmm = (s) => (s ? s.slice(11, 16) : "");
const nowLocal = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16);
const day = (s) => (s ? `${+s.slice(8, 10)} ${MONTHS[+s.slice(5, 7) - 1]}, ${hhmm(s)}` : "");

async function api(method, url, body, msg) {
  $("#busy-text").textContent = msg || "Working...";
  $("#busy").hidden = false;
  try {
    const r = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    return await r.json();
  } catch (e) {
    alert("Something went wrong: " + e.message);
    throw e;
  } finally {
    $("#busy").hidden = true;
  }
}

const analysed = () => !!current && current.timeline.length > 0;
const hasDocs = () => !!current && Object.keys(current.documents).length > 0;
const obs = (id) => current.observations.find((o) => o.id === id);
const obsOf = (ref) => current.observations.filter((o) => o.source_ref === ref);
const aside = (id) => current.set_aside.find((a) => a.id === id);

function reports() {
  const c = current;
  return [{ id: "F01", kind: "family", name: `${c.intake.informant_name} (${c.intake.relation.toLowerCase()})`, when: c.intake.reported_at, text: c.intake.text }]
    .concat(c.tips.map((t) => ({ id: t.id, kind: "tip", name: t.caller_name || "Anonymous caller", when: t.received_at, text: t.text, phone: t.phone })))
    .concat(c.cctv.map((n) => ({ id: n.id, kind: "cctv", name: `${n.camera}, ${n.location}`, when: n.timestamp, text: n.text })));
}

function source(o) {
  if (o.source_type === "family") return "Family report";
  if (o.source_type === "cctv") return "CCTV camera";
  const t = current.tips.find((x) => x.id === o.source_ref);
  return t && t.caller_name ? `Tip: ${t.caller_name}` : "Tip: anonymous";
}

function verdict(o) {
  if (o.source_type === "family") return ["Last seen", "v-family"];
  if (o.extraction_failed) return ["Needs manual entry", "v-check"];
  if (aside(o.id)) return ["Not used", "v-unused"];
  if (current.conflicts.some((f) => f.alternative === o.id)) return ["Needs checking", "v-check"];
  if (o.priority >= 80) return ["Strong match", "v-strong"];
  if (o.priority >= 50) return ["Possible", "v-possible"];
  return ["Weak", "v-weak"];
}
const tag = ([word, cls]) => `<span class="tag ${cls}">${word}</span>`;

function panel(title, badge, body, cls = "") {
  return `<div class="panel ${cls}"><div class="panel-head"><span>${title}</span>${badge || ""}</div>${body}</div>`;
}
const badge = (text, cls = "") => `<span class="badge ${cls}">${text}</span>`;

function sightingDetail(o) {
  if (o.extraction_failed) return `<p class="muted">The system could not read this report automatically. It needs manual entry.</p>`;
  if (o.source_type === "family") {
    return `<h4>Description used as the baseline</h4><ul>${Object.entries(o.descriptors).filter(([, v]) => v)
      .map(([f, v]) => `<li><b>${FIELD[f] || f}:</b> ${esc(v)}</li>`).join("")}</ul>`;
  }
  const cmp = Object.entries(o.comparison);
  const chips = (r, cls) => cmp.filter(([, c]) => c.result === r)
    .map(([f, c]) => `<span class="chip ${cls}" title="${esc(c.reason)}">${FIELD[f]}</span>`).join("") || `<span class="muted">none</span>`;
  const known = cmp.filter(([, c]) => c.result !== "unknown").length;
  const why = aside(o.id);
  return `
    ${why ? `<p class="muted">Not used on the timeline: ${esc(why.why)}.</p>` : ""}
    <div class="cols">
      <div><h4>Matches the description</h4>${chips("match", "c-yes")}
           <h4>Does not match</h4>${chips("mismatch", "c-no")}
           <p class="muted">${10 - known} of 10 details not mentioned.</p></div>
      <div><h4>Score</h4><span class="sum">Match ${o.descriptor_score} × 0.6 + trust ${o.credibility} × 0.4 = <b>${o.priority}</b></span>
           <h4>Why this much trust</h4><ul>${o.score_notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul></div>
    </div>`;
}

function obsRow(o, cols) {
  const key = "o:" + o.id;
  const alt = current.conflicts.some((f) => f.alternative === o.id);
  let html = `<tr class="click ${alt ? "alt" : ""} ${open === key ? "hl" : ""}" data-open="${key}" id="${key}">
    <td class="time">${hhmm(o.observed_at || o.observed_until) || "--"}</td>
    <td>${esc(o.location || "Place not given")}<span class="id">${o.id}</span></td>
    <td class="muted">${esc(source(o))}</td>
    <td>${tag(verdict(o))}</td><td class="chev">${open === key ? "&#9652;" : "&#9662;"}</td></tr>`;
  if (open === key) {
    html += `<tr class="detail"><td colspan="${cols}"><div class="quote">"${esc(o.raw_text)}"</div>${sightingDetail(o)}
      ${o.extraction_notes ? `<h4>Extraction notes</h4><p class="muted">${esc(o.extraction_notes)}</p>` : ""}</td></tr>`;
  }
  return html;
}

function viewReports() {
  if (!current) return `<div class="panel"><div class="empty">No case open. Use <b>Load demo case</b> on the Home tab.</div></div>`;
  const a = analysed();
  const rows = reports().map((r) => {
    const key = "r:" + r.id;
    const o = obsOf(r.id)[0];
    let html = `<tr class="click ${open === key ? "hl" : ""}" data-open="${key}" id="${key}">
      <td>${esc(r.name)}<span class="id">${r.id}</span></td>
      <td class="muted">${KIND[r.kind]}</td>
      <td class="time muted">${day(r.when)}</td>
      <td>${a && o ? tag(verdict(o)) : ""}</td><td class="chev">${open === key ? "&#9652;" : "&#9662;"}</td></tr>`;
    if (open === key) {
      html += `<tr class="detail"><td colspan="5"><div class="quote">"${esc(r.text)}"</div>
        ${r.kind === "tip" ? `<p class="muted">${r.phone ? "Caller left a phone number." : "No phone number given."}</p>` : ""}
        ${a ? obsOf(r.id).map((x) => `<h4>Sighting ${x.id}: ${esc(x.location || "place not given")}, ${hhmm(x.observed_at || x.observed_until) || "no time given"}</h4>${sightingDetail(x)}`).join("")
            : `<p class="muted">Press <b>Analyse reports</b> on the Home tab to check this report.</p>`}</td></tr>`;
    }
    return html;
  }).join("");
  return panel("Reports Received", badge(`${reports().length} REPORTS`),
    `<div class="panel-body"><table class="rows"><thead><tr><th>From</th><th>Type</th><th>Received</th><th>Result</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`);
}

function gapMinutes(a, b) {
  const span = (o) => [new Date(o.observed_at || o.observed_until), new Date(o.observed_until || o.observed_at)];
  const [a0, a1] = span(a), [b0, b1] = span(b);
  return Math.round(Math.max(0, (b0 - a1) / 60000, (a0 - b1) / 60000));
}

function viewTimeline() {
  const c = current;
  if (!analysed()) return `<div class="panel"><div class="empty">The timeline appears after <b>Analyse reports</b> on the Home tab.</div></div>`;
  const head = `<tr><th>Time</th><th>Place</th><th>Source</th><th>Result</th><th></th></tr>`;
  const table = (list) => `<div class="panel-body"><table class="rows"><thead>${head}</thead><tbody>${list.map((o) => obsRow(o, 5)).join("")}</tbody></table></div>`;

  const conflicts = c.conflicts.map((f) => {
    const alt = obs(f.alternative);
    const prim = f.primary.map(obs);
    const p = prim.find((x) => x.source_type === "cctv") || prim[0];
    const gap = gapMinutes(p, alt);
    const mini = (list) => `<table class="rows"><tbody>${list.map((o) => `<tr class="click" data-go="${o.id}">
      <td class="time">${hhmm(o.observed_at || o.observed_until)}</td><td>${esc(o.location)}<br><span class="muted">${esc(source(o))}</span></td></tr>`).join("")}</tbody></table>`;
    return panel("Two reports disagree", badge("UNRECONCILED", "req"), `<div class="panel-body">
      <p class="why"><b>${esc(f.label)}.</b> ${esc(p.location)} and ${esc(alt.location)} are ${travel[p.location][alt.location]} minutes apart by road,
        but the sightings ${gap ? `are only ${gap} minutes apart` : "overlap in time"}. The more trusted side stays on the timeline; the other is kept for field checks.</p>
      <div class="fork-cols"><div><h4>More trusted</h4>${mini(prim)}</div><div><h4>Needs checking</h4>${mini([alt])}</div></div></div>`, "conflict");
  }).join("");

  const trail = [...c.timeline].reverse().map((r) => obs(r.id));
  const unused = c.set_aside.map((a) => obs(a.id));
  return panel("What We Think Happened", badge("SUMMARY"), `<div class="panel-body"><p class="narr">${esc(c.narrative)}</p></div>`)
    + conflicts
    + panel("Sightings, Newest First", badge(`${trail.length} SIGHTINGS`, "green"), table(trail))
    + panel("Reports Not Used on the Timeline", badge(`${unused.length} REPORTS`), table(unused));
}

function viewLeads() {
  if (!analysed()) return `<div class="panel"><div class="empty">Leads appear after <b>Analyse reports</b> on the Home tab.</div></div>`;
  return current.leads.map((l) => panel(`<span class="lead-head"><span class="num">${l.rank}</span>${esc(l.title)}</span>`, badge(`SCORE ${l.score}`),
    `<div class="panel-body"><dl>
      <dt>What to do</dt><dd>${esc(l.action)}</dd>
      <dt>Where</dt><dd>${esc(l.where)}</dd>
      <dt>Why</dt><dd>${esc(l.why)}</dd>
      <dt>Based on these reports</dt><dd>${l.supports.map((s) => `<span class="ref" data-go="${s}">${s}</span>`).join("")}</dd>
      <dt>This would confirm it</dt><dd>${esc(l.confirm)}</dd>
      <dt>This would rule it out</dt><dd>${esc(l.kill)}</dd>
      <dt>Why it is number ${l.rank}</dt><dd>Its best supporting report scores ${l.score}.</dd>
    </dl></div>`)).join("");
}

function viewDocuments() {
  if (!hasDocs()) return `<div class="panel"><div class="empty">Documents appear after <b>Write documents</b> on the Home tab.</div></div>`;
  return Object.entries(DOCS).map(([k, title]) =>
    panel(title, `<button class="pill" data-download="${k}">Download .txt</button>`, `<pre class="doc">${esc(current.documents[k])}</pre>`)).join("");
}

function viewScoring() {
  const s = scoring, b = s.base_credibility;
  return panel("How the Scores Are Worked Out", badge("RULES"), `<div class="panel-body rules">
    <p><b>Description match (0-100).</b> Each detail a report mentions is checked against the family's description.
      Score = points that match ÷ points mentioned. Details not mentioned don't count either way.
      Fewer than ${s.min_known_fields} details: capped at ${s.insufficient_cap}.</p>
    <table>${Object.entries(s.weights).map(([f, v]) => `<tr><td>${FIELD[f]}</td><td>${v} points</td></tr>`).join("")}</table>
    <p><b>Trust in source (0-100).</b> Starts at: family ${b.family}, CCTV ${b.cctv}, named caller ${b.named_tip}, anonymous ${b.anonymous_tip}.
      +${s.contactable} left a phone number. +${s.corroborated} someone else saw the same nearby within ${s.corroboration_window_min / 60} hours.
      ${s.contradicted} clashes with a more trusted report. ${s.stale} reported over ${s.stale_after_hours} hours late.</p>
    <p><b>Overall</b> = ${s.priority.descriptor} × description match + ${s.priority.credibility} × trust.
      80 and above: strong match. 50 to 79: possible. Below 50: weak.</p></div>`);
}

function renderHome() {
  const c = current;
  const a = analysed();
  document.querySelectorAll(".svc[data-action]").forEach((el) => {
    const act = el.dataset.action;
    const ready = act === "seed" || (act === "analyse" && c) || (act === "docs" && a);
    const next = (act === "seed" && !c) || (act === "analyse" && c && !a) || (act === "docs" && a && !hasDocs());
    el.classList.toggle("off", !ready);
    el.classList.toggle("next", !!next);
  });
  $("#sum-text").textContent = c
    ? `${c.intake.subject_name}, reported by ${c.intake.informant_name} (${c.intake.relation.toLowerCase()}). ` +
      `${c.tips.length} phone tips and ${c.cctv.length} CCTV notes received.` +
      (c.last_seen_location ? ` Last seen at ${c.last_seen_location}, ${hhmm(c.last_seen_at)}.` : "")
    : "No case open. Start with \"Load demo case\" or open a new case.";
  $("#conf-text").textContent = a
    ? (c.conflicts.length ? `${c.conflicts.length} conflict: two reports place the person in different places at the same time. Unreconciled — requires field verification.` : "No conflicts found.")
    : "Appears after analysis. Reports that cannot both be true are flagged here, never silently dropped.";
  $("#lead-count").textContent = a ? c.leads.length : 0;
}

function render() {
  const c = current;
  $("#case-box").innerHTML = c
    ? `Case: <b>${esc(c.intake.subject_name)}</b>${c.last_seen_location ? ` · last seen ${esc(c.last_seen_location)}` : ""}`
    : "No case open";
  document.querySelectorAll("#tabs button").forEach((b) => {
    const t = b.dataset.tab;
    b.classList.toggle("on", t === tab || (tab === "addreport" && t === "reports"));
    b.disabled = (["timeline", "leads"].includes(t) && !analysed()) || (t === "documents" && !hasDocs());
  });
  document.querySelectorAll("main > section").forEach((s) => (s.hidden = s.dataset.view !== tab));
  renderHome();
  if (tab === "reports") $("#reports").innerHTML = viewReports();
  if (tab === "timeline") $("#timeline").innerHTML = viewTimeline();
  if (tab === "leads") $("#leads").innerHTML = viewLeads();
  if (tab === "documents") $("#documents").innerHTML = viewDocuments();
  if (tab === "scoring") $("#scoring").innerHTML = viewScoring();
}

function go(t) { tab = t; open = null; render(); window.scrollTo(0, 0); }

// jump to a sighting from anywhere: open the timeline with that row expanded
function goObs(id) {
  tab = "timeline";
  open = "o:" + id;
  render();
  const el = document.getElementById(open);
  if (el) el.scrollIntoView({ block: "center" });
}

async function seed() {
  current = await api("GET", "/api/case/demo/seed", null, "Loading demo case...");
  go("reports");
}
async function analyse() {
  current = await api("POST", `/api/case/${current.id}/analyse`, null, `Analysing ${reports().length} reports...`);
  go("timeline");
}
async function docs() {
  current = await api("POST", `/api/case/${current.id}/documents`, null, "Writing documents...");
  go("documents");
}

document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-tab], [data-action], [data-open], [data-go], [data-download]");
  if (!t || t.disabled) return;
  if (t.dataset.tab) go(t.dataset.tab);
  else if (t.dataset.action) ({ seed, analyse, docs })[t.dataset.action]();
  else if (t.dataset.open) { open = open === t.dataset.open ? null : t.dataset.open; render(); }
  else if (t.dataset.go) goObs(t.dataset.go);
  else if (t.dataset.download) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([current.documents[t.dataset.download]], { type: "text/plain" }));
    a.download = `${current.id}_${t.dataset.download}.txt`;
    a.click();
  }
});

// the backend takes the family report as one statement, so the form fields are
// written out as sentences in front of whatever the family said
$("#f-case").onsubmit = async (e) => {
  e.preventDefault();
  const d = Object.fromEntries(new FormData(e.target));
  const parts = [
    `Missing person: ${d.subject_name}` + [d.age && `age ${d.age}`, d.gender, d.state].filter(Boolean).map((x) => ", " + x).join("") + ".",
    `Last seen${d.date ? " on " + d.date : ""}${d.time ? " at " + d.time : ""} at ${d.location}.`,
    d.height && `Height ${d.height} cm.`,
    d.weight && `Weight ${d.weight} kg.`,
    d.physical && `Physical description: ${d.physical}.`,
    d.clothing && `Clothing and belongings: ${d.clothing}.`,
    d.medical && `Medical conditions: ${d.medical}.`,
    d.text && `Statement: ${d.text}`,
  ];
  current = await api("POST", "/api/case", {
    informant_name: d.informant_name, relation: d.relation, phone: d.phone || null,
    subject_name: d.subject_name, reported_at: nowLocal(),
    text: parts.filter(Boolean).join(" "),
  }, "Opening case...");
  e.target.reset();
  const fam = obs("F01-1");
  if (fam && fam.extraction_failed) {
    alert("Case opened. In offline mode the system only has saved answers for the demo case, so this report could not be read automatically. Switch to live mode to analyse new cases.");
  }
  go("reports");
};

const fr = $("#f-report");
function showReportFields() {
  document.querySelectorAll("#f-report [data-for]").forEach((l) => (l.hidden = l.dataset.for !== fr.kind.value));
}
fr.kind.onchange = showReportFields;
showReportFields();

fr.onsubmit = async (e) => {
  e.preventDefault();
  if (!current) return alert("Load the demo case or open a new case first.");
  const d = Object.fromEntries(new FormData(fr));
  const when = d.date ? `${d.date}T${d.time || "00:00"}` : nowLocal();
  if (d.kind === "tip") {
    current = await api("POST", `/api/case/${current.id}/tip`,
      { caller_name: d.caller_name || null, phone: d.phone || null, received_at: when, text: d.text }, "Reading report...");
  } else {
    current = await api("POST", `/api/case/${current.id}/cctv`,
      { camera: d.camera || "unknown", location: d.location || "unknown", operator: null, timestamp: when, text: d.text }, "Reading report...");
  }
  const last = d.kind === "tip" ? current.tips.at(-1).id : current.cctv.at(-1).id;
  fr.reset();
  showReportFields();
  tab = "reports";
  open = "r:" + last;
  render();
  document.getElementById(open)?.scrollIntoView({ block: "center" });
};

(async () => {
  scoring = await (await fetch("/api/scoring")).json();
  travel = (await (await fetch("/api/places")).json()).travel_minutes;
  const h = await (await fetch("/api/health")).json();
  $("#mode").textContent = { live: "Live mode: IBM watsonx", bob: "Live mode: IBM Bob" }[h.llm_mode] || "Offline mode: saved AI answers";
  render();
})();
