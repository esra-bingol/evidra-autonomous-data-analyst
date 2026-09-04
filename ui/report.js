const $ = (id) => document.getElementById(id);

function chip(text) {
  const s = document.createElement("span");
  s.className = "chip";
  s.textContent = text;
  return s;
}

function section(title) {
  const el = document.createElement("section");
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

function renderReport(run, report) {
  const doc = $("doc");
  doc.replaceChildren();

  const s1 = section("1 · Executive summary");
  s1.appendChild(para(report.executive_summary || ""));
  doc.appendChild(s1);

  const s2 = section("2 · Dataset overview");
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

  const s3 = section("3 · Investigation question");
  s3.appendChild(para(report.investigation_question || run.question || ""));
  doc.appendChild(s3);

  const s4 = section("4 · Investigation plan");
  s4.appendChild(para((report.investigation_plan || []).join(" → ") || "—"));
  doc.appendChild(s4);

  const s5 = section("5 · Research trace");
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

  const s6 = section("6 · Key findings");
  for (const f of report.key_findings || []) {
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
  if (!(report.key_findings || []).length) s6.appendChild(para("No published findings."));
  doc.appendChild(s6);

  const s7 = section("7 · Evidence");
  const table = document.createElement("table");
  table.innerHTML = "<thead><tr><th>id</th><th>operation</th><th>strength</th></tr></thead>";
  const tb = document.createElement("tbody");
  for (const e of report.evidence || []) {
    const tr = document.createElement("tr");
    for (const c of [e.evidence_id, e.operation, e.strength]) {
      const td = document.createElement("td");
      td.textContent = c || "";
      tr.appendChild(td);
    }
    tb.appendChild(tr);
  }
  table.appendChild(tb);
  s7.appendChild(table);
  doc.appendChild(s7);

  const s8 = section("8 · Driver decomposition");
  const dec = report.driver_decomposition || {};
  s8.appendChild(para(`Primary associated slice: ${dec.primary_driver || "—"}`));
  if (dec.evidence_id) {
    const p = document.createElement("p");
    p.className = "meta";
    p.textContent = `evidence ${dec.evidence_id}`;
    s8.appendChild(p);
  }
  doc.appendChild(s8);

  const s9 = section("9 · Supporting visualizations");
  const viz = report.visualizations || [];
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
      Plotly.newPlot(el, ch.plotly.data || [], ch.plotly.layout || {}, { displayModeBar: false });
    }
  });
  doc.appendChild(s9);

  const s10 = section("10 · Statistical results");
  const stats = report.statistical_results || [];
  if (!stats.length) s10.appendChild(para("No association_test evidence on this run."));
  for (const st of stats) {
    s10.appendChild(para(`r=${st.r} · p=${st.p_value} · n=${st.n} · ${st.interpretation} (${st.evidence_id})`));
  }
  doc.appendChild(s10);

  const s11 = section("11 · Reviewer decisions");
  const revs = report.reviewer_decisions || [];
  if (!revs.length) s11.appendChild(para("No reviewer rows."));
  for (const v of revs) {
    s11.appendChild(para(`${v.claim_id}: ${v.decision} — ${v.reason || ""}`));
  }
  doc.appendChild(s11);

  const s12 = section("12 · Limitations");
  s12.appendChild(list(report.limitations));
  doc.appendChild(s12);

  const s13 = section("13 · Recommended next investigations");
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
