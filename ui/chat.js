const DEFAULT_STARTERS = ["Satış neden değişti?", "Hangi bölge öne çıkıyor?"];

const STARTERS = {
  taxi_trips: ["Ücret neden değişti?", "Hangi bölge öne çıkıyor?"],
  olist: ["Teslimat gecikmesi puanı nasıl etkiler?", "Hangi kategori öne çıkıyor?"],
  clear_driver: DEFAULT_STARTERS,
  aov_trap: DEFAULT_STARTERS,
  no_signal: DEFAULT_STARTERS,
  missingness: DEFAULT_STARTERS,
  superstore: DEFAULT_STARTERS,
  uci_retail: DEFAULT_STARTERS,
};

const ICONS = {
  assistant:
    '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M7 8.5h10M7 12h7M8.5 18l-3.5 2v-4.5A7 7 0 0 1 5 5h14v8a5 5 0 0 1-5 5H8.5Z" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  user:
    '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="8" r="3" stroke="currentColor" stroke-width="1.7"/><path d="M6.5 19c.6-3.2 2.4-5 5.5-5s4.9 1.8 5.5 5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
  empty:
    '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" aria-hidden="true"><path d="M7 8.5h10M7 12h7M8.5 18l-3.5 2v-4.5A7 7 0 0 1 5 5h14v8a5 5 0 0 1-5 5H8.5Z" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
};

const $ = (id) => document.getElementById(id);
const state = { datasetId: null, chatId: null, sending: false, thinkTimer: null };

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
      fill: trace.fill || (String(trace.mode || "").includes("lines") || trace.type === "scatter" ? "tozeroy" : undefined),
      fillcolor: trace.fillcolor || "rgba(122, 78, 130, 0.16)",
      line: { ...(trace.line || {}), color: trace.line?.color || color, width: trace.line?.width || 2.8, shape: trace.line?.shape || "spline" },
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

const DECISION_LABELS = {
  primary_driver: "Tek dilimde yoğunlaştı",
  value_not_volume: "Sepet tutarı, adet değil",
  data_artefact: "Veri kalitesi işareti",
  ranking: "Sıralama",
  association: "İlişki, neden değil",
  abstain: "Belirgin yoğunlaşma yok",
};

const DECISION_SHORT = {
  primary_driver: "Tek dilim",
  value_not_volume: "Sepet tutarı",
  data_artefact: "Veri kalitesi",
  ranking: "Sıralama",
  association: "İlişki",
  abstain: "Yoğunlaşma yok",
};

function startersFor(fid) {
  return STARTERS[fid] || DEFAULT_STARTERS;
}

function setWorkspace(name) {
  const el = $("workspace-name");
  if (el && name) el.textContent = name;
}

function setWorkflowStep(step) {
  document.querySelectorAll(".workflow-list li").forEach((item, index) => {
    item.classList.remove("active", "done");
    if (index < step) item.classList.add("done");
    else if (index === step) item.classList.add("active");
  });
}

function timeLabel(value) {
  const date = value ? new Date(value) : new Date();
  return date.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
}

async function renderRunPreview(runId, reportUrl) {
  const preview = $("run-preview");
  if (!preview || !runId) return;
  preview.innerHTML = '<div class="preview-empty"><span class="loader" aria-hidden="true"></span><strong>Analiz hazırlanıyor</strong><p>Bulgular ve görseller yükleniyor.</p></div>';
  const res = await fetch(`/runs/${runId}`);
  if (!res.ok) return;
  const run = await res.json();
  const report = run.investigation_report || {};
  const findings = report.headline_findings || report.key_findings || run.claims || [];
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
    ["Sonuç", DECISION_SHORT[run.decision] || run.decision || "—"],
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
  setWorkflowStep(3);
}

function showBanner(text, kind) {
  const el = $("banner");
  el.textContent = text;
  el.classList.remove("hidden", "err");
  if (kind) el.classList.add(kind);
}

const SUGGEST_HINTS = {
  "Satış neden değişti?": "Dönem karşılaştırması ve kanıt zinciri",
  "Hangi bölge öne çıkıyor?": "Dilim sıralaması",
  "Ücret neden değişti?": "Hacim / sepet ayrımı",
  "Teslimat gecikmesi puanı nasıl etkiler?": "İlişki, neden değil",
  "Hangi kategori öne çıkıyor?": "Kategori katkısı",
};

function fillSuggest(box, items, sendOnClick) {
  if (!box) return;
  box.innerHTML = "";
  const cards = box.classList.contains("suggest-cards");
  (items || startersFor($("fixture")?.value)).forEach((q) => {
    const b = document.createElement("button");
    b.type = "button";
    if (cards) {
      const title = document.createElement("strong");
      title.textContent = q;
      const hint = document.createElement("small");
      hint.textContent = SUGGEST_HINTS[q] || "Kanıta bağlı inceleme başlat";
      b.append(title, hint);
    } else {
      b.textContent = q;
    }
    b.addEventListener("click", () => {
      $("msg").value = q;
      syncSend();
      if (sendOnClick && state.chatId && !state.sending) {
        sendMessage();
        return;
      }
      $("msg").focus();
    });
    box.appendChild(b);
  });
}

function refreshStarters() {
  const items = startersFor($("fixture")?.value);
  fillSuggest($("examples"), items, Boolean(state.chatId));
  fillSuggest($("examples-empty"), items, Boolean(state.chatId));
  const help = document.querySelector("#empty .help");
  if (help && state.datasetId) {
    help.textContent = "Veri bağlamak inceleme başlatmaz. Aşağıdaki sorulardan birini sorun.";
  }
}

function bindHint(fid) {
  const q = startersFor(fid)[0];
  return `Veri bağlandı. Bu henüz bir cevap değil — şunu sorun: “${q}”`;
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
  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent = msg.role === "user" ? `${timeLabel(msg.created_at)} · gönderildi` : `${timeLabel(msg.created_at)} · analiz tamamlandı`;
  stack.appendChild(meta);
  if (msg.role !== "user" && msg.run) {
    stack.appendChild(responseCard(msg));
  }
  if (msg.report_url) {
    const a = document.createElement("a");
    a.href = msg.report_url;
    a.textContent = "Detaylı raporu aç";
    stack.appendChild(a);
  }
  if (msg.role !== "user") {
    const refs = document.createElement("div");
    refs.className = "refs";
    const st = msg.status || {};
    const bits = [
      st.decision ? DECISION_LABELS[st.decision] || st.decision : null,
      msg.run_id ? "inceleme hazır" : null,
      (msg.claim_ids || []).length ? `${(msg.claim_ids || []).length} bulgu` : null,
      (msg.evidence_ids || []).length ? `${(msg.evidence_ids || []).length} kanıt` : null,
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
    loadFollowUps(msg.run_id);
  }
}

function responseCard(msg) {
  const run = msg.run || {};
  const report = run.investigation_report || {};
  const card = document.createElement("div");
  card.className = "answer-card";
  const title = document.createElement("strong");
  title.textContent = "Analiz özeti";
  const source = document.createElement("span");
  source.textContent = `Kaynak: ${$("context-dataset")?.textContent || "bağlı veri seti"}`;
  card.append(title, source);

  const facts = document.createElement("div");
  facts.className = "answer-facts";
  const k = report.kpis || {};
  for (const [label, value] of [
    ["Değişim", k.change_pct == null ? "—" : `${String(k.change_pct).replace(".", ",")}%`],
    ["Kırılım", k.concentration || "—"],
    ["Kanıt", `${(run.evidence || []).length} kayıt`],
  ]) {
    const item = document.createElement("div");
    const small = document.createElement("small");
    small.textContent = label;
    const b = document.createElement("b");
    b.textContent = value;
    item.append(small, b);
    facts.appendChild(item);
  }
  card.appendChild(facts);

  const first = (report.headline_findings || [])[0];
  if (first?.text) {
    const finding = document.createElement("p");
    finding.textContent = first.text;
    card.appendChild(finding);
  }
  return card;
}

const THINKING_STEPS = [
  "Soru yorumlanıyor",
  "Hipotezler seçiliyor",
  "Kanıtlar hesaplanıyor",
  "Grafikler bağlanıyor",
];

function setThinking(on) {
  const old = document.getElementById("thinking");
  if (old) old.remove();
  if (state.thinkTimer) {
    clearInterval(state.thinkTimer);
    state.thinkTimer = null;
  }
  if (!on) return;
  const empty = $("empty");
  if (empty) empty.remove();
  const row = document.createElement("div");
  row.id = "thinking";
  row.className = "row assistant";
  row.innerHTML =
    `<span class="avatar assistant">${ICONS.assistant}</span><div class="stack"><div class="bubble thinking"><span class="thinking-dots" aria-hidden="true"><i></i><i></i><i></i></span><div class="thinking-copy"><strong>Analiz ediliyor…</strong><span id="thinking-step">${THINKING_STEPS[0]}</span></div></div><div class="message-meta">${timeLabel()} · çalışıyor</div></div>`;
  $("log").appendChild(row);
  $("log").scrollTop = $("log").scrollHeight;
  let step = 0;
  state.thinkTimer = setInterval(() => {
    step = (step + 1) % THINKING_STEPS.length;
    const label = document.getElementById("thinking-step");
    if (label) label.textContent = THINKING_STEPS[step];
  }, 900);
}

function renderHistory(messages) {
  $("log").innerHTML = "";
  if (!messages || !messages.length) {
    const empty = document.createElement("div");
    empty.id = "empty";
    empty.className = "empty-card";
    empty.innerHTML =
      `<span class="empty-icon">${ICONS.empty}</span><p class="hello">Verileriniz hakkında bir soru sorun</p><p class="help">Veri bağlamak cevap üretmez. Bu veri setine uygun bir soru sorun; Evidra kanıt, grafik ve adımları aynı sohbette döndürür.</p><div class="suggest suggest-cards" id="examples-empty"></div>`;
    $("log").appendChild(empty);
    refreshStarters();
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
    opt.textContent = item.available ? (item.name || item.id) : `${item.name || item.id} (yok)`;
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
  setWorkspace(ds.name);
  setWorkflowStep(0);
  renderHistory([]);
  refreshStarters();
  showBanner(bindHint(fid));
  syncSend();
}

async function bindFile(file) {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch("/datasets", { method: "POST", body });
  const ds = await res.json();
  if (!res.ok) {
    showBanner(ds.detail || "dosya okunamadı", "err");
    return;
  }
  state.datasetId = ds.id;
  const chat = await fetch("/chats", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: ds.id }),
  });
  const chatBody = await chat.json();
  if (!chat.ok) {
    showBanner(chatBody.detail || "sohbet açılamadı", "err");
    return;
  }
  state.chatId = chatBody.id;
  $("dataset-meta").textContent = `${ds.name} yüklendi`;
  $("context-dataset").textContent = ds.name;
  setWorkspace(ds.name);
  setWorkflowStep(0);
  renderHistory([]);
  fillSuggest($("examples"), DEFAULT_STARTERS, true);
  fillSuggest($("examples-empty"), DEFAULT_STARTERS, true);
  showBanner("Dosya bağlandı. Bu henüz bir cevap değil — bir iş sorusu sorun.");
  syncSend();
}

async function loadFollowUps(runId) {
  const res = await fetch(`/runs/${runId}`);
  if (!res.ok) return;
  const run = await res.json();
  const next = run.investigation_report?.recommended_next_investigations || [];
  const extras = ["Detaylı raporu göster.", "Araştırma adımlarını göster."];
  const items = [...next.slice(0, 2), ...extras];
  fillSuggest($("examples"), items, true);
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
  setWorkflowStep(1);
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
  refreshStarters();
  $("btn-fixture").addEventListener("click", bindDataset);
  $("fixture").addEventListener("change", () => {
    if ($("empty")) refreshStarters();
  });
  const file = $("file");
  if (file) {
    file.addEventListener("change", (ev) => {
      const picked = ev.target.files?.[0];
      if (picked) bindFile(picked);
    });
  }
  $("composer").addEventListener("submit", sendMessage);
  $("msg").addEventListener("input", syncSend);
  $("msg").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      sendMessage();
    }
  });
  syncSend();
  const wanted = new URLSearchParams(location.search).get("fixture");
  if (wanted) {
    const sel = $("fixture");
    if ([...sel.options].some((opt) => opt.value === wanted && !opt.disabled)) {
      sel.value = wanted;
      bindDataset();
    }
  }
});
