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
    status.textContent = run.status || "tamamlandı";
    header.append(date, status);
    const title = document.createElement("strong");
    title.textContent = run.question || "Adsız inceleme";
    link.append(header, title);
    list.appendChild(link);
  }
}

function chartTitle(chart, fallback) {
  const title = chart.plotly?.layout?.title;
  if (typeof title === "string") return title;
  if (title && typeof title.text === "string") return title.text;
  return chart.purpose || fallback;
}

function renderCharts(runs) {
  const gallery = $("chart-gallery");
  const candidates = [];
  for (const run of runs) {
    const reportCharts = run.investigation_report?.visualizations || [];
    const charts = reportCharts.length ? reportCharts : run.charts || [];
    for (const chart of charts) {
      if (chart.plotly) candidates.push({ chart, run });
    }
  }
  gallery.replaceChildren();
  if (!candidates.length) {
    gallery.innerHTML =
      '<div class="empty-state"><strong>Henüz görsel analiz yok</strong><p>Bir inceleme çalıştırdığınızda grafikler burada görünür.</p></div>';
    return;
  }
  candidates.slice(0, 2).forEach(({ chart, run }, index) => {
    const card = document.createElement("div");
    card.className = "chart-card";
    const title = document.createElement("h3");
    title.textContent = chartTitle(chart, run.question || `Analiz ${index + 1}`);
    const plot = document.createElement("div");
    plot.className = "chart";
    card.append(title, plot);
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

function renderMetrics(runs) {
  const findings = runs.reduce(
    (total, run) => total + (run.investigation_report?.key_findings || run.claims || []).length,
    0
  );
  const evidence = runs.reduce(
    (total, run) => total + (run.investigation_report?.evidence || run.evidence || []).length,
    0
  );
  const charts = runs.reduce(
    (total, run) => total + (run.investigation_report?.visualizations || run.charts || []).length,
    0
  );
  $("metric-runs").textContent = String(runs.length);
  $("metric-findings").textContent = String(findings);
  $("metric-evidence").textContent = String(evidence);
  $("metric-charts").textContent = String(charts);
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
  renderMetrics(details);
  renderCharts(details);
}

document.addEventListener("DOMContentLoaded", loadDashboard);
