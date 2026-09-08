const $ = (id) => document.getElementById(id);

function chip(text) {
  const s = document.createElement("span");
  s.className = "chip";
  s.textContent = text;
  return s;
}

function section(title, className = "") {
  const el = document.createElement("section");
  el.className = `report-card ${className}`.trim();
  const h = document.createElement("h2");
  h.textContent = title;
  el.appendChild(h);
  return el;
}

function para(text) {
  const p = document.createElement("p");
  p.textContent = text;
  return p;
}

function list(items) {
  const ul = document.createElement("ul");
  for (const item of items || []) {
    const li = document.createElement("li");
    li.textContent = item;
    ul.appendChild(li);
  }
  return ul;
}

function themeValue(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function themedFigure(figure) {
  const palette = [
    themeValue("--color-accent"),
    themeValue("--color-success"),
    themeValue("--color-violet"),
    themeValue("--color-warning"),
  ];
  const text = themeValue("--color-text-secondary");
  const grid = themeValue("--color-border");
  const surface = themeValue("--color-surface");
  const data = (figure.data || []).map((trace, index) => {
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
  const source = figure.layout || {};
  const axis = { gridcolor: grid, linecolor: grid, zerolinecolor: grid, automargin: true };
  return {
    data,
    layout: {
      ...source,
      paper_bgcolor: "transparent",
      plot_bgcolor: surface,
      font: { ...(source.font || {}), family: themeValue("--font-sans"), color: text },
      xaxis: { ...axis, ...(source.xaxis || {}) },
      yaxis: { ...axis, ...(source.yaxis || {}) },
      margin: { l: 48, r: 24, t: 48, b: 44, ...(source.margin || {}) },
      height: 360,
      bargap: 0.28,
      barcornerradius: 6,
      legend: { orientation: "h", x: 0, y: 1.12, ...(source.legend || {}) },
      hoverlabel: {
        bgcolor: themeValue("--color-text"),
        bordercolor: themeValue("--color-text"),
        font: { color: surface, family: themeValue("--font-sans") },
      },
    },
  };
}

function renderReport(run, report) {
  const doc = $("doc");
  doc.replaceChildren();

  const findings = report.key_findings || [];
  const evidence = report.evidence || [];
  const visualizations = report.visualizations || [];
  const hero = document.createElement("section");
  hero.className = "report-hero";
  const heroCopy = document.createElement("div");
  heroCopy.className = "hero-copy";
  const heroKicker = document.createElement("p");
  heroKicker.className = "eyebrow";
  heroKicker.textContent = "Executive summary";
  const heroTitle = document.createElement("h2");
  heroTitle.textContent = report.investigation_question || run.question || "İnceleme özeti";
  heroCopy.append(heroKicker, heroTitle, para(report.executive_summary || ""));
  const metrics = document.createElement("div");
  metrics.className = "hero-metrics";
  const metricValues = [
    ["Karar", run.decision || "—"],
    ["Bulgular", String(findings.length)],
    ["Kanıtlar", String(evidence.length)],
    ["Grafikler", String(visualizations.length)],
  ];
  for (const [label, value] of metricValues) {
    const metric = document.createElement("div");
    metric.className = "hero-metric";
    const caption = document.createElement("span");
    caption.textContent = label;
    const strong = document.createElement("strong");
    strong.textContent = value;
    metric.append(caption, strong);
    metrics.appendChild(metric);
  }
  hero.append(heroCopy, metrics);
  doc.appendChild(hero);

  const s2 = section("Veri seti özeti");
  const ov = report.dataset_overview || {};
  s2.appendChild(
    para(
      `${ov.n_rows ?? "—"} rows · ${ov.n_cols ?? "—"} cols · tables ${ov.n_tables ?? "—"} · ${ov.path || ""}`
    )
  );
  if ((ov.capabilities_present || []).length) {
    const chips = document.createElement("div");
    chips.className = "chips";
    for (const c of ov.capabilities_present) chips.appendChild(chip(c));
    s2.appendChild(chips);
  }
  doc.appendChild(s2);

  const s3 = section("İnceleme sorusu");
  s3.appendChild(para(report.investigation_question || run.question || ""));
  doc.appendChild(s3);

  const s4 = section("İnceleme planı", "wide");
  s4.appendChild(para((report.investigation_plan || []).join(" → ") || "—"));
  doc.appendChild(s4);

  const s5 = section("Araştırma izi", "wide");
  const trace = report.research_trace || [];
  if (!trace.length) s5.appendChild(para("No trace rows."));
  else {
    const ul = document.createElement("ul");
    for (const row of trace.slice(0, 40)) {
      const li = document.createElement("li");
      li.textContent = [row.kind, row.template_id || row.tool, row.status || row.summary || row.reason]
        .filter(Boolean)
        .join(" · ");
      ul.appendChild(li);
    }
    s5.appendChild(ul);
  }
  doc.appendChild(s5);

  const s6 = section("Temel bulgular", "wide");
  for (const f of findings) {
    const box = document.createElement("div");
    box.className = "finding";
    box.appendChild(para(f.text || ""));
    const chips = document.createElement("div");
    chips.className = "chips";
    if (f.kind) chips.appendChild(chip(f.kind));
    if (f.reviewer_decision) chips.appendChild(chip(`reviewer ${f.reviewer_decision}`));
    for (const id of f.evidence_ids || []) chips.appendChild(chip(id));
    for (const id of f.chart_ids || []) chips.appendChild(chip(id));
    box.appendChild(chips);
    s6.appendChild(box);
  }
  if (!findings.length) s6.appendChild(para("Yayımlanmış bulgu yok."));
  doc.appendChild(s6);

  const s7 = section("Kanıt tablosu", "wide");
  const table = document.createElement("table");
  table.innerHTML = "<thead><tr><th>id</th><th>operation</th><th>strength</th></tr></thead>";
  const tb = document.createElement("tbody");
  for (const e of evidence) {
    const tr = document.createElement("tr");
    for (const c of [e.evidence_id, e.operation, e.strength]) {
      const td = document.createElement("td");
      td.textContent = c || "";
      tr.appendChild(td);
    }
    tb.appendChild(tr);
  }
  table.appendChild(tb);
  const tableWrap = document.createElement("div");
  tableWrap.className = "table-wrap";
  tableWrap.appendChild(table);
  s7.appendChild(tableWrap);
  doc.appendChild(s7);

  const s8 = section("Sürücü ayrıştırması");
  const dec = report.driver_decomposition || {};
  s8.appendChild(para(`Primary associated slice: ${dec.primary_driver || "—"}`));
  if (dec.evidence_id) {
    const p = document.createElement("p");
    p.className = "meta";
    p.textContent = `evidence ${dec.evidence_id}`;
    s8.appendChild(p);
  }
  doc.appendChild(s8);

  const s9 = section("Destekleyici görseller", "wide");
  const viz = visualizations;
  doc.appendChild(s9);
  if (!viz.length) s9.appendChild(para("No chart had an analytical purpose on this evidence set."));
  viz.forEach((ch, i) => {
    const cap = document.createElement("p");
    cap.className = "meta";
    cap.textContent = `${ch.id} · ${ch.purpose} · ${ch.kind} · ${(ch.evidence_ids || []).join(", ")}`;
    s9.appendChild(cap);
    const el = document.createElement("div");
    el.className = "chart";
    el.id = `viz-${i}`;
    s9.appendChild(el);
    if (window.Plotly && ch.plotly) {
      const figure = themedFigure(ch.plotly);
      Plotly.newPlot(el, figure.data, figure.layout, { displayModeBar: false, responsive: true });
    }
  });

  const s10 = section("İstatistiksel sonuçlar");
  const stats = report.statistical_results || [];
  if (!stats.length) s10.appendChild(para("No association_test evidence on this run."));
  for (const st of stats) {
    s10.appendChild(para(`r=${st.r} · p=${st.p_value} · n=${st.n} · ${st.interpretation} (${st.evidence_id})`));
  }
  doc.appendChild(s10);

  const s11 = section("Reviewer kararları");
  const revs = report.reviewer_decisions || [];
  if (!revs.length) s11.appendChild(para("No reviewer rows."));
  for (const v of revs) {
    s11.appendChild(para(`${v.claim_id}: ${v.decision} — ${v.reason || ""}`));
  }
  doc.appendChild(s11);

  const s12 = section("Sınırlamalar");
  s12.appendChild(list(report.limitations));
  doc.appendChild(s12);

  const s13 = section("Önerilen sonraki incelemeler");
  s13.appendChild(list(report.recommended_next_investigations));
  doc.appendChild(s13);

  $("banner").textContent = `run ${run.id} · decision ${run.decision} · charts ${viz.length}`;
  doc.classList.remove("hidden");
}

async function main() {
  const rid = new URLSearchParams(location.search).get("run");
  if (!rid) return;
  const res = await fetch(`/runs/${rid}`);
  if (!res.ok) {
    $("banner").textContent = "Run bulunamadı.";
    return;
  }
  const run = await res.json();
  const report = run.investigation_report || (await (await fetch(`/runs/${rid}/report`)).json());
  renderReport(run, report);
}

document.addEventListener("DOMContentLoaded", main);
