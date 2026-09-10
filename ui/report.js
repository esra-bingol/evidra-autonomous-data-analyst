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

function kindLabel(kind) {
  if (kind === "line") return "çizgi";
  if (kind === "waterfall") return "şelale";
  if (kind === "bar") return "sütun";
  return kind || "grafik";
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

  const findings = report.headline_findings || [];
  const published = report.key_findings || [];
  const evidence = report.evidence || [];
  const visualizations = report.visualizations || [];

  const hero = document.createElement("section");
  hero.className = "report-hero";
  const heroCopy = document.createElement("div");
  heroCopy.className = "hero-copy";
  const kicker = document.createElement("p");
  kicker.className = "eyebrow";
  kicker.textContent = "Evidra investigation";
  const heroTitle = document.createElement("h2");
  heroTitle.textContent = report.title || "Evidra incelemesi";
  const question = document.createElement("p");
  question.className = "hero-question";
  question.textContent = report.investigation_question || run.question || "";
  heroCopy.append(kicker, heroTitle);
  if (question.textContent) heroCopy.appendChild(question);
  heroCopy.appendChild(para(report.executive_summary || ""));
  const metrics = document.createElement("div");
  metrics.className = "hero-metrics";
  const metricValues = [
    ["Sonuç", report.decision_label || run.decision || "—"],
    ["Bulgular", String(findings.length || published.length)],
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

  const sFind = section("Temel bulgular", "wide");
  if (!findings.length) sFind.appendChild(para("Yayımlanmış bulgu yok."));
  const ol = document.createElement("ol");
  ol.className = "headline-findings";
  for (const f of findings) {
    const li = document.createElement("li");
    const title = document.createElement("strong");
    title.textContent = f.text || "";
    li.appendChild(title);
    const chips = document.createElement("div");
    chips.className = "chips";
    for (const id of f.evidence_ids || []) chips.appendChild(chip(id));
    if (chips.childNodes.length) li.appendChild(chips);
    ol.appendChild(li);
  }
  if (findings.length) sFind.appendChild(ol);
  doc.appendChild(sFind);

  const s2 = section("Veri seti özeti");
  const ov = report.dataset_overview || {};
  s2.appendChild(
    para(`${ov.n_rows ?? "—"} satır · ${ov.n_cols ?? "—"} kolon · ${ov.n_tables ?? "—"} tablo`)
  );
  if ((ov.capabilities_present || []).length) {
    const chips = document.createElement("div");
    chips.className = "chips";
    for (const c of ov.capabilities_present) chips.appendChild(chip(c));
    s2.appendChild(chips);
  }
  doc.appendChild(s2);

  const s4 = section("İnceleme planı", "wide");
  const plan = report.plan_readable || [];
  if (plan.length) s4.appendChild(list(plan));
  else s4.appendChild(para((report.investigation_plan || []).join(" → ") || "—"));
  doc.appendChild(s4);

  const s6 = section("Yayımlanan iddialar", "wide");
  for (const f of published) {
    const box = document.createElement("div");
    box.className = "finding";
    box.appendChild(para(f.headline || f.text || ""));
    const chips = document.createElement("div");
    chips.className = "chips";
    if (f.reviewer_decision) chips.appendChild(chip(`reviewer ${f.reviewer_decision}`));
    for (const id of f.evidence_ids || []) chips.appendChild(chip(id));
    box.appendChild(chips);
    s6.appendChild(box);
  }
  if (!published.length) s6.appendChild(para("Yayımlanmış iddia yok."));
  doc.appendChild(s6);

  const s7 = section("Kanıt tablosu", "wide");
  const table = document.createElement("table");
  table.innerHTML = "<thead><tr><th>id</th><th>işlem</th><th>güç</th></tr></thead>";
  const tb = document.createElement("tbody");
  for (const e of evidence) {
    const tr = document.createElement("tr");
    for (const c of [e.evidence_id, e.operation_label || e.operation, e.strength]) {
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
  s8.appendChild(para(dec.primary_driver_label || dec.primary_driver || "Öne çıkan dilim yok."));
  if (dec.evidence_id) {
    const p = document.createElement("p");
    p.className = "meta";
    p.textContent = dec.evidence_id;
    s8.appendChild(p);
  }
  doc.appendChild(s8);

  const s9 = section("Destekleyici görseller", "wide");
  doc.appendChild(s9);
  if (!visualizations.length) s9.appendChild(para("Bu kanıt setinde amaçlı grafik yok."));
  visualizations.forEach((ch, i) => {
    const cap = document.createElement("p");
    cap.className = "meta";
    cap.textContent = `${ch.title || ch.id} · ${kindLabel(ch.kind)} · ${(ch.evidence_ids || []).join(", ")}`;
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
  if (!stats.length) s10.appendChild(para("Bu çalışmada ilişki testi yok."));
  for (const st of stats) {
    s10.appendChild(para(`r=${st.r} · p=${st.p_value} · n=${st.n} · ilişki, nedensellik değil (${st.evidence_id})`));
  }
  doc.appendChild(s10);

  const s11 = section("Reviewer kararları");
  const revs = report.reviewer_decisions || [];
  if (!revs.length) s11.appendChild(para("Reviewer satırı yok."));
  for (const v of revs) {
    const decision = v.decision === "accept" ? "kabul" : v.decision === "reject" ? "red" : v.decision;
    s11.appendChild(para(`${v.claim_id}: ${decision}${v.reason ? " — " + v.reason : ""}`));
  }
  doc.appendChild(s11);

  const s12 = section("Sınırlamalar");
  s12.appendChild(list(report.limitations));
  doc.appendChild(s12);

  const s13 = section("Önerilen sonraki incelemeler");
  s13.appendChild(list(report.recommended_next_investigations));
  doc.appendChild(s13);

  $("banner").textContent = `run ${run.id} · ${report.decision_label || run.decision} · grafikler ${visualizations.length}`;
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
