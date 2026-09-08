const EXAMPLES = [
  { q: "Satış neden değişti?", label: "driver" },
  { q: "Teslimat gecikmesi puanı nasıl etkiler?", label: "abstain / Olist" },
  { q: "Yüksek ciro, düşük puan kategorileri hangileri?", label: "Olist join" },
  { q: "Hangi bölge en yüksek?", label: "ranking" },
];

const $ = (id) => document.getElementById(id);

const state = { datasetId: null, running: false };

function themeValue(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function themedFigure(fig) {
  const palette = [
    themeValue("--color-accent"),
    themeValue("--color-success"),
    themeValue("--color-violet"),
    themeValue("--color-warning"),
  ];
  const text = themeValue("--color-text-secondary");
  const grid = themeValue("--color-border");
  const surface = themeValue("--color-surface");
  const sourceData = fig.data || [];
  const data = sourceData.map((trace, index) => {
    const color = palette[index % palette.length];
    return {
      ...trace,
      marker: {
        ...(trace.marker || {}),
        color: trace.marker?.color || color,
        line: { width: 0, ...(trace.marker?.line || {}) },
      },
      line: { ...(trace.line || {}), color: trace.line?.color || color, width: trace.line?.width || 2.5 },
    };
  });
  const sourceLayout = fig.layout || {};
  const axisTheme = { gridcolor: grid, linecolor: grid, zerolinecolor: grid, automargin: true };
  const layout = {
    ...sourceLayout,
    paper_bgcolor: "transparent",
    plot_bgcolor: surface,
    font: { ...(sourceLayout.font || {}), family: themeValue("--font-sans"), color: text },
    xaxis: { ...axisTheme, ...(sourceLayout.xaxis || {}) },
    yaxis: { ...axisTheme, ...(sourceLayout.yaxis || {}) },
    margin: { l: 48, r: 24, t: 48, b: 44, ...(sourceLayout.margin || {}) },
    bargap: 0.28,
    barcornerradius: 6,
    legend: { orientation: "h", x: 0, y: 1.12, ...(sourceLayout.legend || {}) },
    hoverlabel: {
      bgcolor: themeValue("--color-text"),
      bordercolor: themeValue("--color-text"),
      font: { color: surface, family: themeValue("--font-sans") },
    },
  };
  return { data, layout };
}

function showBanner(text, kind) {
  const el = $("banner");
  el.textContent = text;
  el.classList.remove("hidden", "err", "warn");
  if (kind) el.classList.add(kind);
}

function clearBanner() {
  $("banner").classList.add("hidden");
}

async function loadFixtures() {
  const res = await fetch("/fixtures");
  const data = await res.json();
  const sel = $("fixture");
  sel.innerHTML = "";
  for (const item of data.items) {
    const opt = document.createElement("option");
    opt.value = item.id;
    opt.textContent = item.available ? item.id : `${item.id} (yok)`;
    opt.disabled = !item.available;
    sel.appendChild(opt);
  }
}

function renderExamples() {
  const box = $("examples");
  box.innerHTML = "";
  for (const ex of EXAMPLES) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = `${ex.label}: ${ex.q}`;
    b.addEventListener("click", () => {
      $("question").value = ex.q;
      syncRunEnabled();
    });
    box.appendChild(b);
  }
}

function syncRunEnabled() {
  $("btn-run").disabled = !state.datasetId || !$("question").value.trim() || state.running;
}

function renderDataset(ds) {
  $("dataset-empty").classList.add("hidden");
  const meta = $("dataset-meta");
  meta.classList.remove("hidden");
  meta.replaceChildren();
  const p = document.createElement("p");
  p.textContent = `${ds.name} · ${ds.n_rows} satır · ${ds.n_cols} kolon · ${ds.source}`;
  meta.appendChild(p);
  const caps = document.createElement("div");
  caps.className = "caps";
  for (const [k, v] of Object.entries(ds.capabilities || {})) {
    const s = document.createElement("span");
    s.textContent = k;
    if (v) s.classList.add("on");
    caps.appendChild(s);
  }
  meta.appendChild(caps);
}

async function registerFixture() {
  clearBanner();
  const id = $("fixture").value;
  const res = await fetch("/datasets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fixture_id: id }),
  });
  const ds = await res.json();
  if (!res.ok) {
    showBanner(ds.detail || "dataset yüklenemedi", "err");
    return;
  }
  state.datasetId = ds.id;
  renderDataset(ds);
  syncRunEnabled();
}

async function registerFile(file) {
  clearBanner();
  const body = new FormData();
  body.append("file", file);
  const res = await fetch("/datasets", { method: "POST", body });
  const ds = await res.json();
  if (!res.ok) {
    showBanner(ds.detail || "dosya okunamadı", "err");
    state.datasetId = null;
    $("dataset-meta").classList.add("hidden");
    $("dataset-empty").classList.remove("hidden");
    syncRunEnabled();
    return;
  }
  state.datasetId = ds.id;
  renderDataset(ds);
  syncRunEnabled();
}

function strengthsFor(claim, evidence) {
  const byId = Object.fromEntries((evidence || []).map((e) => [e.evidence_id, e]));
  const vals = (claim.evidence_ids || []).map((id) => byId[id]?.strength).filter(Boolean);
  return [...new Set(vals)];
}

function renderPlan(run) {
  $("plan-empty").classList.add("hidden");
  $("plan-loading").classList.add("hidden");
  const traces = run.traces || [];
  const table = $("plan-table");
  const tb = table.querySelector("tbody");
  tb.replaceChildren();
  if (!traces.length) {
    table.classList.add("hidden");
    $("plan-empty").classList.remove("hidden");
  } else {
    table.classList.remove("hidden");
    for (const t of traces) {
      const tr = document.createElement("tr");
      const cells = [t.tool, t.ok ? "ok" : "hata", String(t.duration_ms ?? ""), t.summary || t.error || ""];
      for (const c of cells) {
        const td = document.createElement("td");
        td.textContent = c;
        tr.appendChild(td);
      }
      tb.appendChild(tr);
    }
  }
  const steps = $("plan-steps");
  if (run.plan?.length) {
    steps.classList.remove("hidden");
    steps.textContent = (run.plan || []).join(" → ");
  } else {
    steps.classList.add("hidden");
  }
}

function renderFindings(run) {
  $("findings-empty").classList.add("hidden");
  const bar = $("decision-bar");
  bar.classList.remove("hidden");
  bar.replaceChildren();
  const line = document.createElement("p");
  const decision = run.decision || "—";
  const stop = run.stop_reason || "—";
  line.textContent = `decision: ${decision} · stop_reason: ${stop}`;
  bar.appendChild(line);
  if (run.id) {
    const a = document.createElement("a");
    a.href = `/report?run=${run.id}`;
    a.textContent = "Detaylı rapor (V2.6)";
    bar.appendChild(a);
  }
  if (decision === "abstain" || stop === "abstain") {
    showBanner("Abstain: capability ∩ soru boş veya sinyal yok. Hipotez uydurulmadı.", "warn");
  }

  const revBox = $("reviews");
  if (revBox) {
    revBox.replaceChildren();
    for (const rev of run.reviews || []) {
      const p = document.createElement("p");
      p.className = "mono";
      p.textContent = `review: ${rev.decision} · ${rev.reason || ""}`;
      revBox.appendChild(p);
    }
  }

  const claimsBox = $("claims");
  claimsBox.replaceChildren();
  for (const claim of run.claims || []) {
    const div = document.createElement("div");
    div.className = "claim";
    for (const st of strengthsFor(claim, run.evidence)) {
      const badge = document.createElement("span");
      badge.className = "strength";
      badge.textContent = st;
      div.appendChild(badge);
    }
    const kind = document.createElement("span");
    kind.className = "strength";
    kind.textContent = claim.kind;
    div.appendChild(kind);
    const p = document.createElement("p");
    p.textContent = claim.text;
    div.appendChild(p);
    const ids = document.createElement("p");
    ids.className = "mono";
    ids.textContent = (claim.evidence_ids || []).join(", ") || "(evidence_ids boş — abstention)";
    div.appendChild(ids);
    claimsBox.appendChild(div);
  }

  const evTable = $("evidence-table");
  const evBody = evTable.querySelector("tbody");
  evBody.replaceChildren();
  const rows = run.evidence || [];
  if (!rows.length) {
    evTable.classList.add("hidden");
  } else {
    evTable.classList.remove("hidden");
    for (const e of rows) {
      const tr = document.createElement("tr");
      const val = typeof e.value === "object" ? JSON.stringify(e.value) : String(e.value ?? "");
      for (const c of [e.evidence_id, e.operation, e.strength || "", val.slice(0, 180)]) {
        const td = document.createElement("td");
        td.textContent = c;
        tr.appendChild(td);
      }
      evBody.appendChild(tr);
    }
  }

  const charts = $("charts");
  charts.replaceChildren();
  (run.charts || []).forEach((ch, i) => {
    const wrap = document.createElement("div");
    const el = document.createElement("div");
    el.className = "chart";
    el.id = `chart-${i}`;
    wrap.appendChild(el);
    const cap = document.createElement("p");
    cap.className = "chart-cap";
    cap.textContent = `${ch.kind} · evidence_ids: ${(ch.evidence_ids || []).join(", ")}`;
    wrap.appendChild(cap);
    charts.appendChild(wrap);
    if (window.Plotly && ch.plotly) {
      const fig = themedFigure(ch.plotly);
      window.Plotly.newPlot(el, fig.data, fig.layout, { displayModeBar: false, responsive: true });
    }
  });
}

async function runInvestigation() {
  if (!state.datasetId) {
    showBanner("Dataset yok.", "err");
    return;
  }
  const question = $("question").value.trim();
  if (!question) {
    showBanner("Soru yok.", "err");
    return;
  }
  clearBanner();
  state.running = true;
  syncRunEnabled();
  $("plan-empty").classList.add("hidden");
  $("plan-loading").classList.remove("hidden");
  const res = await fetch(`/datasets/${state.datasetId}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  const run = await res.json();
  state.running = false;
  syncRunEnabled();
  $("plan-loading").classList.add("hidden");
  if (run.error) {
    showBanner(run.error, "err");
  }
  renderPlan(run);
  renderFindings(run);
  loadHistory();
}

async function loadHistory() {
  const box = $("history-list");
  const empty = $("history-empty");
  if (!box) return;
  const res = await fetch("/runs");
  if (!res.ok) return;
  const data = await res.json();
  box.replaceChildren();
  const runs = data.runs || [];
  if (!runs.length) {
    if (empty) empty.classList.remove("hidden");
    return;
  }
  if (empty) empty.classList.add("hidden");
  for (const run of runs.slice(0, 12)) {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = `/report?run=${run.id || run.run_id}`;
    const when = (run.created_at || "").slice(0, 10);
    a.textContent = `${when} · ${run.question || "—"} · ${run.status || ""}`;
    li.appendChild(a);
    box.appendChild(li);
  }
}

function init() {
  renderExamples();
  loadFixtures();
  loadHistory();
  $("btn-fixture").addEventListener("click", registerFixture);
  $("file").addEventListener("change", (ev) => {
    const file = ev.target.files?.[0];
    if (file) registerFile(file);
  });
  $("question").addEventListener("input", syncRunEnabled);
  $("btn-run").addEventListener("click", runInvestigation);
}

init();
