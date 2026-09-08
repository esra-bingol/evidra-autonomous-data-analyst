const EXAMPLES = [
  "Satış neden değişti?",
  "West'i daha detaylı incele.",
  "Araştırma adımlarını göster.",
  "Evidence raporunu göster.",
  "Detaylı raporu göster.",
];

const ICONS = {
  assistant:
    '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M7 8.5h10M7 12h7M8.5 18l-3.5 2v-4.5A7 7 0 0 1 5 5h14v8a5 5 0 0 1-5 5H8.5Z" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  user:
    '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="8" r="3" stroke="currentColor" stroke-width="1.7"/><path d="M6.5 19c.6-3.2 2.4-5 5.5-5s4.9 1.8 5.5 5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
  empty:
    '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" aria-hidden="true"><path d="M7 8.5h10M7 12h7M8.5 18l-3.5 2v-4.5A7 7 0 0 1 5 5h14v8a5 5 0 0 1-5 5H8.5Z" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
};

const $ = (id) => document.getElementById(id);
const state = { datasetId: null, chatId: null, sending: false };

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
      font: { ...(source.font || {}), family: themeValue("--font-sans"), color: text, size: 11 },
      xaxis: { ...axis, ...(source.xaxis || {}) },
      yaxis: { ...axis, ...(source.yaxis || {}) },
      margin: { l: 44, r: 16, t: 40, b: 40, ...(source.margin || {}) },
      height: 240,
      showlegend: (source.showlegend ?? data.length > 1),
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

function setWorkflowDone() {
  document.querySelectorAll(".workflow-list li").forEach((item) => {
    item.classList.remove("active");
    item.classList.add("done");
  });
}

async function renderRunPreview(runId, reportUrl) {
  const preview = $("run-preview");
  if (!preview || !runId) return;
  preview.innerHTML = '<div class="preview-empty"><span class="loader" aria-hidden="true"></span><strong>Analiz hazırlanıyor</strong><p>Bulgular ve görseller yükleniyor.</p></div>';
  const res = await fetch(`/runs/${runId}`);
  if (!res.ok) return;
  const run = await res.json();
  const report = run.investigation_report || {};
  const findings = report.key_findings || run.claims || [];
  const charts = report.visualizations || run.charts || [];
  const evidence = report.evidence || run.evidence || [];

  preview.replaceChildren();
  const title = document.createElement("h3");
  title.className = "preview-title";
  title.textContent = "Son inceleme";
  preview.appendChild(title);

  const metrics = document.createElement("div");
  metrics.className = "metric-grid";
  const metricValues = [
    ["Karar", run.decision || "—"],
    ["Bulgular", String(findings.length)],
    ["Kanıtlar", String(evidence.length)],
    ["Grafikler", String(charts.length)],
  ];
  for (const [label, value] of metricValues) {
    const card = document.createElement("div");
    card.className = "metric-card";
    const caption = document.createElement("span");
    caption.textContent = label;
    const strong = document.createElement("strong");
    strong.textContent = value;
    card.append(caption, strong);
    metrics.appendChild(card);
  }
  preview.appendChild(metrics);

  if (findings.length) {
    const box = document.createElement("div");
    box.className = "preview-findings";
    const heading = document.createElement("p");
    heading.className = "context-label";
    heading.textContent = "Öne çıkan bulgular";
    box.appendChild(heading);
    for (const finding of findings.slice(0, 2)) {
      const item = document.createElement("div");
      item.className = "preview-finding";
      item.textContent = finding.text || "";
      box.appendChild(item);
    }
    preview.appendChild(box);
  }

  const firstChart = charts.find((chart) => chart.plotly);
  if (firstChart && window.Plotly) {
    const chart = document.createElement("div");
    chart.className = "preview-chart";
    preview.appendChild(chart);
    const figure = themedFigure(firstChart.plotly);
    window.Plotly.newPlot(chart, figure.data, figure.layout, {
      displayModeBar: false,
      responsive: true,
    });
  }

  const link = document.createElement("a");
  link.className = "preview-report-link";
  link.href = reportUrl || `/report?run=${runId}`;
  link.textContent = "Detaylı raporu aç";
  preview.appendChild(link);
  setWorkflowDone();
}

function showBanner(text, kind) {
  const el = $("banner");
  el.textContent = text;
  el.classList.remove("hidden", "err");
  if (kind) el.classList.add(kind);
}

function fillSuggest(box) {
  box.innerHTML = "";
  EXAMPLES.forEach((q) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = q;
    b.addEventListener("click", () => {
      $("msg").value = q;
      syncSend();
      $("msg").focus();
    });
    box.appendChild(b);
  });
}

function appendBubble(msg) {
  const empty = $("empty");
  if (empty) empty.remove();
  const log = $("log");
  const row = document.createElement("div");
  row.className = `row ${msg.role === "user" ? "user" : "assistant"}`;
  const av = document.createElement("span");
  av.className = `avatar ${msg.role === "user" ? "user" : "assistant"}`;
  av.innerHTML = msg.role === "user" ? ICONS.user : ICONS.assistant;
  const stack = document.createElement("div");
  stack.className = "stack";
  const bubble = document.createElement("p");
  bubble.className = "bubble";
  bubble.textContent = msg.text || "";
  stack.appendChild(bubble);
  if (msg.report_url) {
    const a = document.createElement("a");
    a.href = msg.report_url;
    a.textContent = "Open detailed report";
    stack.appendChild(a);
  }
  if (msg.role !== "user") {
    const refs = document.createElement("div");
    refs.className = "refs";
    const st = msg.status || {};
    const bits = [
      st.decision ? `status ${st.decision}` : null,
      st.stop_reason ? st.stop_reason : null,
      msg.run_id ? `run ${msg.run_id}` : null,
      (msg.claim_ids || []).length ? `claims ${(msg.claim_ids || []).join(", ")}` : null,
      (msg.evidence_ids || []).length ? `evidence ${(msg.evidence_ids || []).join(", ")}` : null,
      msg.intent ? msg.intent : null,
    ].filter(Boolean);
    for (const bit of bits) {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = bit;
      refs.appendChild(chip);
    }
    if (bits.length) stack.appendChild(refs);
  }
  row.appendChild(av);
  row.appendChild(stack);
  log.appendChild(row);
  log.scrollTop = log.scrollHeight;
  if (msg.role !== "user" && msg.run_id) {
    renderRunPreview(msg.run_id, msg.report_url);
  }
}

function setThinking(on) {
  const old = document.getElementById("thinking");
  if (old) old.remove();
  if (!on) return;
  const empty = $("empty");
  if (empty) empty.remove();
  const row = document.createElement("div");
  row.id = "thinking";
  row.className = "row assistant";
  row.innerHTML =
    `<span class="avatar assistant">${ICONS.assistant}</span><p class="bubble thinking"><span class="loader" aria-hidden="true"></span><span>İşleniyor</span></p>`;
  $("log").appendChild(row);
  $("log").scrollTop = $("log").scrollHeight;
}

function renderHistory(messages) {
  $("log").innerHTML = "";
  if (!messages || !messages.length) {
    const empty = document.createElement("div");
    empty.id = "empty";
    empty.className = "empty-card";
    empty.innerHTML =
      `<span class="empty-icon">${ICONS.empty}</span><p class="hello">Verileriniz hakkında bir soru sorun</p><p class="help">Satış değişimlerini, segmentleri ve mevcut inceleme bulgularını doğal dille keşfedin.</p><div class="suggest" id="examples-empty"></div>`;
    $("log").appendChild(empty);
    fillSuggest($("examples-empty"));
    return;
  }
  for (const msg of messages) appendBubble(msg);
}

function syncSend() {
  $("btn-send").disabled = !state.chatId || !$("msg").value.trim() || state.sending;
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

async function bindDataset() {
  const fid = $("fixture").value;
  const res = await fetch("/datasets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fixture_id: fid }),
  });
  const ds = await res.json();
  if (!res.ok) {
    showBanner(ds.detail || "dataset bağlanamadı", "err");
    return;
  }
  state.datasetId = ds.id;
  const chat = await fetch("/chats", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: ds.id }),
  });
  const body = await chat.json();
  if (!chat.ok) {
    showBanner(body.detail || "sohbet açılamadı", "err");
    return;
  }
  state.chatId = body.id;
  $("dataset-meta").textContent = `${ds.name} bağlı`;
  $("context-dataset").textContent = ds.name;
  renderHistory([]);
  showBanner("Dataset bağlandı. Follow-up son run state’ini kullanır.");
  syncSend();
}

async function sendMessage(ev) {
  if (ev) ev.preventDefault();
  const text = $("msg").value.trim();
  if (!text || !state.chatId || state.sending) return;
  state.sending = true;
  syncSend();
  appendBubble({ role: "user", text });
  $("msg").value = "";
  setThinking(true);
  const res = await fetch(`/chats/${state.chatId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  const body = await res.json();
  setThinking(false);
  state.sending = false;
  if (!res.ok) {
    showBanner(body.detail || "gönderilemedi", "err");
    syncSend();
    return;
  }
  appendBubble(body.message);
  syncSend();
}

document.addEventListener("DOMContentLoaded", async () => {
  await loadFixtures();
  fillSuggest($("examples"));
  fillSuggest($("examples-empty"));
  $("btn-fixture").addEventListener("click", bindDataset);
  $("composer").addEventListener("submit", sendMessage);
  $("msg").addEventListener("input", syncSend);
  $("msg").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      sendMessage();
    }
  });
  syncSend();
});
