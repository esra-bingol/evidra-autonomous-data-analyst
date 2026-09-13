const $ = (id) => document.getElementById(id);

function token(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function themedFigure(figure) {
  const palette = [token("--accent"), token("--green"), "#8a6590", token("--amber"), token("--rose")];
  const grid = token("--border");
  const text = token("--text-secondary");
  const surface = token("--surface-subtle");
  const source = figure.layout || {};
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
  const axis = {
    gridcolor: grid,
    linecolor: grid,
    zeroline: false,
    tickfont: { color: text, size: 10 },
    automargin: true,
  };
  return {
    data,
    layout: {
      ...source,
      paper_bgcolor: "transparent",
      plot_bgcolor: surface,
      font: { ...(source.font || {}), family: token("--font"), color: text, size: 11 },
      xaxis: { ...axis, ...(source.xaxis || {}) },
      yaxis: { ...axis, ...(source.yaxis || {}) },
      margin: { l: 44, r: 14, t: 28, b: 38 },
      height: 272,
      bargap: 0.28,
      showlegend: data.length > 1,
      legend: { orientation: "h", x: 0, y: 1.12, font: { size: 9 } },
      hoverlabel: {
        bgcolor: token("--text"),
        bordercolor: token("--text"),
        font: { color: token("--surface"), family: token("--font"), size: 11 },
      },
    },
  };
}

function formatDate(value) {
  if (!value) return "Tarih yok";
  return new Intl.DateTimeFormat("tr-TR", { day: "numeric", month: "short", year: "numeric" }).format(
    new Date(value)
  );
}

function pctText(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return null;
  const n = Number(value);
  const text = Math.abs(n).toFixed(2).replace(/\.?0+$/, "").replace(".", ",") || "0";
  return { n, text };
}

function formatPct(value) {
  const parsed = pctText(value);
  if (!parsed) return "—";
  if (parsed.n < 0) return `%${parsed.text} azaldı`;
  if (parsed.n > 0) return `%${parsed.text} arttı`;
  return "%0 değişmedi";
}

function shortPct(value) {
  const parsed = pctText(value);
  if (!parsed) return "—";
  if (parsed.n === 0) return "%0";
  return `${parsed.n < 0 ? "−" : "+"}%${parsed.text}`;
}

const DECISION_PLAIN = {
  primary_driver: "Değişim bir yerde yoğunlaşıyor",
  value_not_volume: "Sipariş sayısı değil, sepet tutarı",
  data_artefact: "Eksik bir veri penceresi olabilir",
  ranking: "Sıralama hazır",
  association: "İlişki var; neden değil",
  abstain: "Belirgin bir yoğunlaşma yok",
};

const CHART_PLAIN = {
  trend: "Dönemler arası değişim",
  contribution: "Hangi dilim değişime katkı verdi",
  segment_comparison: "Dilim karşılaştırması",
  metric_comparison: "Hacim ve sepet tutarı",
  distribution: "Sıra dışı dönemler",
};

function plainDecision(run) {
  const key = run?.decision || "";
  if (DECISION_PLAIN[key]) return DECISION_PLAIN[key];
  const label = run?.investigation_report?.decision_label;
  if (label && !/sürücü|dilim destekleniyor/i.test(label)) return label;
  return "İnceleme tamamlandı";
}

function plainDriver(run) {
  const report = run.investigation_report || {};
  if (report.kpis?.concentration) return report.kpis.concentration;
  const raw = report.driver_decomposition?.primary_driver_label || report.driver_decomposition?.primary_driver;
  if (raw) return raw;
  if ((run.decision || "") === "abstain") return "Tek bir bölge veya kategoride toplanmadı";
  return "Henüz bir yoğunlaşma yok";
}
function kpisFrom(run) {
  const report = run.investigation_report || {};
  let change = null;
  let volume = null;
  let aov = null;
  for (const ev of run.evidence || []) {
    const val = ev.value || {};
    if (ev.operation === "compare_periods" && val.change_pct != null) change = val.change_pct;
    if (ev.operation === "decompose_volume_value") {
      volume = val.volume_change_pct;
      aov = val.aov_change_pct;
    }
  }
  const kpis = report.kpis || {};
  return {
    decision: plainDecision(run),
    change: kpis.change_pct ?? change,
    driver: plainDriver(run),
    volume: kpis.volume_change_pct ?? volume,
    aov: kpis.aov_change_pct ?? aov,
    question: report.investigation_question || run.question || "",
    summary: report.executive_summary || "",
  };
}

function renderRecent(runs) {
  const list = $("recent-list");
  list.replaceChildren();
  if (!runs.length) {
    list.innerHTML =
      '<div class="empty-state"><strong>Henüz inceleme yok</strong><p>İlk iş sorunuzu sorarak başlayın.</p></div>';
    return;
  }
  for (const run of runs.slice(0, 5)) {
    const link = document.createElement("a");
    link.className = "recent-item";
    link.href = `/report?run=${run.id || run.run_id}`;
    const header = document.createElement("div");
    header.className = "recent-item-header";
    const date = document.createElement("small");
    date.textContent = formatDate(run.created_at);
    const status = document.createElement("span");
    status.className = "recent-status";
    status.textContent = plainDecision(run);
    header.append(date, status);
    const title = document.createElement("strong");
    title.textContent = run.question || "Adsız inceleme";
    link.append(header, title);
    list.appendChild(link);
  }
}

function friendlyChartTitle(chart, question) {
  if (chart.purpose && CHART_PLAIN[chart.purpose]) return CHART_PLAIN[chart.purpose];
  if (chart.title && !/[_]|fare_amount|sales eğilimi/i.test(chart.title)) return chart.title;
  return question || "Kanıta bağlı grafik";
}

function renderCharts(run) {
  const gallery = $("chart-gallery");
  const reportCharts = run?.investigation_report?.visualizations || [];
  const charts = reportCharts.length ? reportCharts : run?.charts || [];
  const bound = charts.filter((chart) => chart.plotly);
  gallery.replaceChildren();
  if (!bound.length) {
    gallery.innerHTML =
      '<div class="empty-state"><strong>Henüz grafik yok</strong><p>Bir iş sorusu sorduğunuzda dönem değişimi veya dilim karşılaştırması burada görünür.</p></div>';
    return;
  }
  bound.slice(0, 2).forEach((chart) => {
    const card = document.createElement("div");
    card.className = "chart-card";
    const title = document.createElement("h3");
    title.textContent = friendlyChartTitle(chart, run.question);
    const cap = document.createElement("p");
    cap.className = "chart-cap";
    cap.textContent = "Bu görsel son sorunuzun kanıtından üretildi. Ham tablodan sayı uydurulmaz.";
    const plot = document.createElement("div");
    plot.className = "chart";
    card.append(title, cap, plot);
    gallery.appendChild(card);
    if (window.Plotly) {
      const figure = themedFigure(chart.plotly);
      window.Plotly.newPlot(plot, figure.data, figure.layout, {
        displayModeBar: false,
        responsive: true,
      });
    }
  });
}

function renderMetrics(run) {
  const empty = !run;
  const kpi = empty ? {} : kpisFrom(run);
  $("kpi-decision").textContent = kpi.decision || "—";
  $("kpi-change").textContent = empty ? "—" : formatPct(kpi.change);
  $("kpi-driver").textContent = kpi.driver || "—";
  if (kpi.volume == null && kpi.aov == null) {
    $("kpi-volume").textContent = "—";
  } else {
    $("kpi-volume").textContent = `sipariş ${shortPct(kpi.volume)} · sepet ${shortPct(kpi.aov)}`;
  }
  const note = $("kpi-limitation");
  if (!note) return;
  if (empty) {
    note.textContent = "Bu kartlar son sorduğunuz sorunun incelemesinden gelir. Henüz soru yoksa önce verini bağlayıp bir iş sorusu sorun.";
    return;
  }
  note.textContent = kpi.summary || kpi.question || "";
}

async function loadDashboard() {
  const response = await fetch("/runs");
  if (!response.ok) return;
  const metadata = (await response.json()).runs || [];
  renderRecent(metadata);
  const details = await Promise.all(
    metadata.slice(0, 8).map(async (item) => {
      const id = item.id || item.run_id;
      const runResponse = await fetch(`/runs/${id}`);
      return runResponse.ok ? runResponse.json() : item;
    })
  );
  renderRecent(details);
  const latest = details[0] || null;
  renderMetrics(latest);
  renderCharts(latest);
  const workspace = $("workspace-name");
  if (workspace && latest) {
    workspace.textContent = latest.investigation_report?.title || "Evidra çalışma alanı";
  }
}

document.addEventListener("DOMContentLoaded", loadDashboard);
