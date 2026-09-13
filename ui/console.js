const DEFAULT_EXAMPLES = [
  { q: "Satış neden değişti?", label: "değişim" },
  { q: "Hangi bölge öne çıkıyor?", label: "sıralama" },
];

const EXAMPLES_BY_FIXTURE = {
  taxi_trips: [
    { q: "Ücret neden değişti?", label: "değişim" },
    { q: "Hangi bölge öne çıkıyor?", label: "sıralama" },
  ],
  olist: [
    { q: "Teslimat gecikmesi puanı nasıl etkiler?", label: "ilişki" },
    { q: "Hangi kategori öne çıkıyor?", label: "sıralama" },
  ],
};

const DECISION_PLAIN = {
  primary_driver: "Değişim bir yerde yoğunlaşıyor",
  value_not_volume: "Sipariş sayısı değil, sepet tutarı",
  data_artefact: "Eksik bir veri penceresi olabilir",
  ranking: "Sıralama hazır",
  association: "İlişki var; neden değil",
  abstain: "Belirgin bir yoğunlaşma yok",
};

const STOP_PLAIN = {
  abstain: "yeterli sinyal yok",
  budget: "araştırma bütçesi doldu",
  complete: "inceleme tamamlandı",
};

const CHART_PLAIN = {
  trend: "Dönemler arası değişim",
  contribution: "Hangi dilim değişime katkı verdi",
  segment_comparison: "Dilim karşılaştırması",
  metric_comparison: "Hacim ve sepet tutarı",
  distribution: "Sıra dışı dönemler",
};

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
    opt.textContent = item.available ? (item.name || item.id) : `${item.name || item.id} (yok)`;
    opt.disabled = !item.available;
    sel.appendChild(opt);
  }
}

function renderExamples(fid) {
  const box = $("examples");
  box.innerHTML = "";
  const examples = EXAMPLES_BY_FIXTURE[fid] || DEFAULT_EXAMPLES;
  for (const ex of examples) {
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
  renderExamples(id);
  $("question").value = (EXAMPLES_BY_FIXTURE[id] || DEFAULT_EXAMPLES)[0].q;
  showBanner("Veri bağlandı. İnceleme henüz çalışmadı — örnek soruyu çalıştırın.");
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
  renderExamples();
  showBanner("Dosya bağlandı. İnceleme henüz çalışmadı — bir iş sorusu yazıp çalıştırın.");
  syncRunEnabled();
}

function fmtPct(n, withSign = true) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  const value = Number(n);
  let text = Math.abs(value).toFixed(2).replace(/\.?0+$/, "").replace(".", ",");
  if (!text) text = "0";
  if (!withSign) return `%${text}`;
  if (value < 0) return `%${text} azaldı`;
  if (value > 0) return `%${text} arttı`;
  return "%0 değişmedi";
}

function fmtNum(n) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  const value = Number(n);
  const abs = Math.abs(value);
  const text = abs.toLocaleString("tr-TR", { maximumFractionDigits: abs >= 100 ? 1 : 2 });
  return value < 0 ? `−${text}` : text;
}

function toneClass(n) {
  if (n == null) return "";
  if (n < 0) return "down";
  if (n > 0) return "up";
  return "";
}

function kpiCard(label, value, hint, tone) {
  const el = document.createElement("div");
  el.className = `kpi ${tone || ""}`.trim();
  const cap = document.createElement("span");
  cap.textContent = label;
  const strong = document.createElement("strong");
  strong.textContent = value;
  el.append(cap, strong);
  if (hint) {
    const small = document.createElement("small");
    small.textContent = hint;
    el.appendChild(small);
  }
  return el;
}

function periodHint(kpis) {
  if (!kpis?.previous_period || !kpis?.current_period) return "";
  return `${kpis.previous_period} → ${kpis.current_period}`;
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
  const tb = $("plan-table").querySelector("tbody");
  tb.replaceChildren();
  for (const t of traces) {
    const tr = document.createElement("tr");
    const cells = [t.tool, t.ok ? "tamam" : "hata", `${t.duration_ms ?? "—"} ms`, t.summary || t.error || ""];
    for (const c of cells) {
      const td = document.createElement("td");
      td.textContent = c;
      tr.appendChild(td);
    }
    tb.appendChild(tr);
  }
  $("plan-trace").classList.toggle("hidden", !traces.length);

  const steps = $("plan-steps");
  steps.replaceChildren();
  const readable = run.investigation_report?.plan_readable || [];
  for (const step of readable) {
    const li = document.createElement("li");
    li.textContent = step;
    steps.appendChild(li);
  }
  steps.classList.toggle("hidden", !readable.length);
  if (!readable.length && !traces.length) $("plan-empty").classList.remove("hidden");
}

function renderFindings(run) {
  $("findings-empty").classList.add("hidden");
  const bar = $("decision-bar");
  bar.classList.remove("hidden");
  bar.replaceChildren();
  const line = document.createElement("p");
  const decision = run.decision || "—";
  const stop = run.stop_reason || "";
  const report = run.investigation_report || {};
  const decisionText =
    report.decision_label || DECISION_PLAIN[decision] || decision;
  const stopText = STOP_PLAIN[stop];
  line.textContent = stopText ? `${decisionText} · ${stopText}` : decisionText;
  bar.appendChild(line);
  if (run.id) {
    const a = document.createElement("a");
    a.href = `/report?run=${run.id}`;
    a.textContent = "Detaylı raporu aç";
    bar.appendChild(a);
  }
  if (decision === "abstain" || stop === "abstain") {
    showBanner(
      "Bu soru için mevcut veride belirgin bir yoğunlaşma yok. Uydurma açıklama üretilmedi.",
      "warn",
    );
  }

  const summary = $("summary-text");
  summary.textContent = report.executive_summary || "";
  summary.classList.toggle("hidden", !report.executive_summary);

  const kpiRow = $("kpi-row");
  kpiRow.replaceChildren();
  const kpis = report.kpis;
  if (kpis) {
    const noun = kpis.metric_noun || "Metrik";
    kpiRow.append(
      kpiCard(`${noun} değişimi`, fmtPct(kpis.change_pct), periodHint(kpis), toneClass(kpis.change_pct)),
      kpiCard("Sipariş sayısı", fmtPct(kpis.volume_change_pct), "Adet", toneClass(kpis.volume_change_pct)),
      kpiCard("Ortalama sepet", fmtPct(kpis.aov_change_pct), "Sipariş başına tutar", toneClass(kpis.aov_change_pct)),
      kpiCard("Nerede yoğunlaştı", kpis.concentration || "—", kpis.n_rows ? `${kpis.n_rows} satır incelendi` : ""),
    );
  }
  kpiRow.classList.toggle("hidden", !kpis);

  const findList = $("findings-list");
  findList.replaceChildren();
  for (const item of report.headline_findings || []) {
    const li = document.createElement("li");
    li.textContent = item.text;
    findList.appendChild(li);
  }
  findList.classList.toggle("hidden", !(report.headline_findings || []).length);

  const sliceTable = $("slice-table");
  const sliceBody = sliceTable.querySelector("tbody");
  sliceBody.replaceChildren();
  const slices = report.slice_table || [];
  for (const row of slices) {
    const tr = document.createElement("tr");
    const cells = [
      row.label,
      fmtNum(row.previous),
      fmtNum(row.current),
      fmtNum(row.change),
      row.share_pct == null ? "—" : fmtPct(row.share_pct, false),
    ];
    for (const c of cells) {
      const td = document.createElement("td");
      td.textContent = c;
      tr.appendChild(td);
    }
    sliceBody.appendChild(tr);
  }
  sliceTable.classList.toggle("hidden", !slices.length);

  const caveats = $("caveats");
  caveats.replaceChildren();
  for (const note of report.limitations || []) {
    const li = document.createElement("li");
    li.textContent = note;
    caveats.appendChild(li);
  }
  caveats.classList.toggle("hidden", !(report.limitations || []).length);

  $("tech").classList.remove("hidden");

  const revBox = $("reviews");
  if (revBox) {
    revBox.replaceChildren();
    for (const rev of run.reviews || []) {
      const p = document.createElement("p");
      p.className = "mono";
      p.textContent = `denetim: ${rev.decision} · ${rev.reason || ""}`;
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
    ids.textContent = (claim.evidence_ids || []).join(", ") || "Kanıta bağlanmayan kayıt";
    div.appendChild(ids);
    claimsBox.appendChild(div);
  }

  const evBody = $("evidence-table").querySelector("tbody");
  evBody.replaceChildren();
  for (const e of run.evidence || []) {
    const tr = document.createElement("tr");
    const val = typeof e.value === "object" ? JSON.stringify(e.value) : String(e.value ?? "");
    for (const c of [e.evidence_id, e.operation, e.strength || "", val.slice(0, 180)]) {
      const td = document.createElement("td");
      td.textContent = c;
      tr.appendChild(td);
    }
    evBody.appendChild(tr);
  }

  const charts = $("charts");
  charts.replaceChildren();
  const viz = report.visualizations || run.charts || [];
  viz.forEach((ch, i) => {
    const wrap = document.createElement("div");
    wrap.className = "chart-cell";
    const cap = document.createElement("p");
    cap.className = "chart-cap";
    cap.textContent = CHART_PLAIN[ch.purpose] || ch.title || "Grafik";
    const el = document.createElement("div");
    el.className = "chart";
    el.id = `chart-${i}`;
    wrap.append(cap, el);
    charts.appendChild(wrap);
    if (window.Plotly && ch.plotly) {
      const fig = themedFigure(ch.plotly);
      fig.layout.title = undefined;
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
  for (const run of runs.slice(0, 6)) {
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
