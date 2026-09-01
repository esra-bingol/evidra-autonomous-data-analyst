const EXAMPLES = [
  "Satış neden değişti?",
  "West'i daha detaylı incele.",
  "Araştırma adımlarını göster.",
  "Evidence raporunu göster.",
];

const $ = (id) => document.getElementById(id);
const state = { datasetId: null, chatId: null, sending: false };

function showBanner(text, kind) {
  const el = $("banner");
  el.textContent = text;
  el.classList.remove("hidden", "err");
  if (kind) el.classList.add(kind);
}

function fillSuggest(box, dashed) {
  box.innerHTML = "";
  EXAMPLES.forEach((q, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = q;
    if (dashed && i === 1) b.style.borderStyle = "dashed";
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
  av.textContent = msg.role === "user" ? "S" : "E";
  const stack = document.createElement("div");
  stack.className = "stack";
  const bubble = document.createElement("p");
  bubble.className = "bubble";
  bubble.textContent = msg.text || "";
  stack.appendChild(bubble);
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
    '<span class="avatar assistant">E</span><p class="bubble thinking">İnceleme çalışıyor <span class="dots">…</span></p>';
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
      '<p class="hello">Merhaba — ben Evidra. İş sorunu doğal dilde sor; analiz tabloyu bu katman değil investigation engine yapar.</p><p class="help">Ne konusunda yardımcı olayım?</p><div class="suggest" id="examples-empty"></div>';
    $("log").appendChild(empty);
    fillSuggest($("examples-empty"), true);
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
  fillSuggest($("examples"), true);
  fillSuggest($("examples-empty"), true);
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
