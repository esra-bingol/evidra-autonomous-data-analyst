const $ = (id) => document.getElementById(id);

const CHART_PLAIN = {
  trend: "Dönemler arası değişim",
  contribution: "Hangi dilim değişime katkı verdi",
  segment_comparison: "Dilim karşılaştırması",
  metric_comparison: "Hacim ve sepet tutarı",
  distribution: "Sıra dışı dönemler",
};

function themeValue(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function para(text) {
  const p = document.createElement("p");
  p.textContent = text;
  return p;
}

function fmtPct(n, withSign = true) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  const value = Number(n);
  const abs = Math.abs(value);
  let text = abs.toFixed(2).replace(/\.?0+$/, "").replace(".", ",");
  if (!text) text = "0";
  if (!withSign) return `%${text}`;
  if (value < 0) return `%${text} azaldı`;
  if (value > 0) return `%${text} arttı`;
  return "%0";
}

function fmtNum(n) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  const value = Number(n);
  const abs = Math.abs(value);
  const text =
    abs >= 100
      ? abs.toLocaleString("tr-TR", { maximumFractionDigits: 1 })
      : abs.toLocaleString("tr-TR", { maximumFractionDigits: 2 });
  return value < 0 ? `−${text}` : text;
}

function toneClass(n) {
  if (n == null) return "";
  if (n < 0) return "down";
  if (n > 0) return "up";
  return "";
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
      margin: { l: 48, r: 16, t: 16, b: 44, ...(source.margin || {}) },
      height: 280,
      bargap: 0.28,
      barcornerradius: 6,
      showlegend: false,
      hoverlabel: {
        bgcolor: themeValue("--color-text"),
        bordercolor: themeValue("--color-text"),
        font: { color: surface, family: themeValue("--font-sans") },
      },
    },
  };
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

function card(title, extraClass = "") {
  const el = document.createElement("section");
  el.className = `report-card ${extraClass}`.trim();
  if (title) {
    const h = document.createElement("h2");
    h.textContent = title;
    el.appendChild(h);
  }
  return el;
}

function renderReport(run, report) {
  const doc = $("doc");
  doc.replaceChildren();
  const kpis = report.kpis || {};
  const findings = report.headline_findings || [];
  const visualizations = report.visualizations || [];
  const slices = report.slice_table || [];
  const next = report.recommended_next_investigations || [];
  const limits = (report.limitations || []).slice(0, 4);
  const periodHint = [kpis.previous_period, kpis.current_period].filter(Boolean).join(" → ");

  const hero = document.createElement("section");
  hero.className = "report-hero";
  const kicker = document.createElement("p");
  kicker.className = "eyebrow";
  kicker.textContent = "Veri analisti brifingi";
  const title = document.createElement("h2");
  title.textContent = report.title || "İnceleme raporu";
  const asked = document.createElement("p");
  asked.className = "hero-question";
  asked.textContent = report.investigation_question || run.question || "";
  const summary = para(report.executive_summary || "");
  summary.className = "hero-summary";
  hero.append(kicker, title);
  if (asked.textContent) hero.appendChild(asked);
  hero.appendChild(summary);
  doc.appendChild(hero);

  const kpiRow = document.createElement("section");
  kpiRow.className = "kpi-row";
  kpiRow.append(
    kpiCard(
      `${kpis.metric_noun || "Metrik"} değişimi`,
      fmtPct(kpis.change_pct),
      periodHint,
      toneClass(kpis.change_pct),
    ),
    kpiCard("Sipariş sayısı", fmtPct(kpis.volume_change_pct), "Adet", toneClass(kpis.volume_change_pct)),
    kpiCard(
      "Ortalama sepet",
      fmtPct(kpis.aov_change_pct),
      "Sipariş başına tutar",
      toneClass(kpis.aov_change_pct),
    ),
    kpiCard(
      "Nerede yoğunlaştı",
      kpis.concentration || "—",
      kpis.n_rows ? `${kpis.n_rows} satır incelendi` : "",
    ),
  );
  doc.appendChild(kpiRow);

  const vizCard = card("Grafikler", "wide");
  if (!visualizations.length) {
    vizCard.appendChild(para("Bu incelemede amaçlı bir grafik yok — soru mevcut kanıtla görselleştirilmedi."));
  } else {
    const grid = document.createElement("div");
    grid.className = "charts-grid";
    visualizations.forEach((ch, i) => {
      const cell = document.createElement("figure");
      cell.className = "chart-cell";
      const cap = document.createElement("figcaption");
      cap.textContent = CHART_PLAIN[ch.purpose] || ch.title || "Grafik";
      const plot = document.createElement("div");
      plot.className = "chart";
      plot.id = `viz-${i}`;
      cell.append(cap, plot);
      grid.appendChild(cell);
      if (window.Plotly && ch.plotly) {
        const figure = themedFigure(ch.plotly);
        figure.layout.title = undefined;
        window.Plotly.newPlot(plot, figure.data, figure.layout, { displayModeBar: false, responsive: true });
      }
    });
    vizCard.appendChild(grid);
  }
  doc.appendChild(vizCard);

  const findCard = card("Bulgular");
  if (!findings.length) {
    findCard.appendChild(para("Yayımlanmış bulgu yok."));
  } else {
    const ol = document.createElement("ol");
    ol.className = "headline-findings";
    for (const f of findings) {
      const li = document.createElement("li");
      li.textContent = f.text || "";
      ol.appendChild(li);
    }
    findCard.appendChild(ol);
  }
  doc.appendChild(findCard);

  const nextCard = card("Sonraki sorular");
  if (!next.length) {
    nextCard.appendChild(para("Bu brifingden sonra ayrı bir dilim sormak yeterli."));
  } else {
    const box = document.createElement("div");
    box.className = "next-chips";
    for (const item of next) {
      const a = document.createElement("a");
      a.href = "/chat";
      a.textContent = item;
      box.appendChild(a);
    }
    nextCard.appendChild(box);
  }
  doc.appendChild(nextCard);

  if (slices.length) {
    const sliceCard = card("Dilim tablosu", "wide");
    const intro = para("Pay, toplam değişimin ne kadarının o dilimde görüldüğünü gösterir. En büyük pay tek kaynak demek değildir.");
    intro.className = "section-note";
    sliceCard.appendChild(intro);
    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    const table = document.createElement("table");
    table.innerHTML =
      "<thead><tr><th>Dilim</th><th>Önceki dönem</th><th>Güncel dönem</th><th>Değişim</th><th>Pay</th></tr></thead>";
    const tb = document.createElement("tbody");
    for (const row of slices) {
      const tr = document.createElement("tr");
      const cells = [
        row.label,
        fmtNum(row.previous),
        fmtNum(row.current),
        fmtNum(row.change),
        row.share_pct == null ? "—" : fmtPct(row.share_pct, false),
      ];
      cells.forEach((c, idx) => {
        const td = document.createElement("td");
        td.textContent = c;
        if (idx === 3) td.className = toneClass(row.change);
        tr.appendChild(td);
      });
      tb.appendChild(tr);
    }
    table.appendChild(tb);
    wrap.appendChild(table);
    sliceCard.appendChild(wrap);
    doc.appendChild(sliceCard);
  }

  const cave = card("Bu raporun söylemediği şey", "wide");
  const ul = document.createElement("ul");
  ul.className = "caveats";
  for (const note of limits) {
    const li = document.createElement("li");
    li.textContent = note;
    ul.appendChild(li);
  }
  cave.appendChild(ul);
  doc.appendChild(cave);

  const method = document.createElement("details");
  method.className = "appendix";
  const sum = document.createElement("summary");
  sum.textContent = "Nasıl bakıldı";
  method.appendChild(sum);
  const plan = report.plan_readable || [];
  if (plan.length) {
    const ol = document.createElement("ol");
    for (const step of plan) {
      const li = document.createElement("li");
      li.textContent = step;
      ol.appendChild(li);
    }
    method.appendChild(ol);
  } else {
    method.appendChild(para("Bu incelemede kayıtlı adım listesi yok."));
  }
  const nEv = (report.evidence || []).length;
  method.appendChild(para(`${nEv} kanıt kaydı kullanıldı. Ham kimlikler sohbette dökülmez.`));
  doc.appendChild(method);

  $("banner").textContent = kpis.verdict || report.decision_label || "Rapor hazır";
  $("banner").classList.add("ready");
  doc.classList.remove("hidden");
}

async function main() {
  const rid = new URLSearchParams(location.search).get("run");
  if (!rid) {
    $("banner").textContent = "Açık bir inceleme yok. Sohbette bir soru sorun, sonra raporu açın.";
    return;
  }
  const res = await fetch(`/runs/${rid}`);
  if (!res.ok) {
    $("banner").textContent = "Bu inceleme bulunamadı.";
    return;
  }
  const run = await res.json();
  const report = run.investigation_report || (await (await fetch(`/runs/${rid}/report`)).json());
  renderReport(run, report);
}

document.addEventListener("DOMContentLoaded", main);
