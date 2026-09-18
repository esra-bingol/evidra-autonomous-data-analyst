(function () {
  const overlayId = "evidra-gate";

  function hide() {
    document.getElementById(overlayId)?.remove();
    document.documentElement.classList.remove("gated");
  }

  function show(errorText) {
    let box = document.getElementById(overlayId);
    if (!box) {
      box = document.createElement("div");
      box.id = overlayId;
      box.className = "gate";
      box.innerHTML =
        '<form class="gate-card" id="gate-form">' +
        "<p class=\"gate-kicker\">Evidra</p>" +
        "<strong>Bu örnek kilitli</strong>" +
        "<p>Paylaşılan erişim anahtarını girin. Varsayılan yerel kurulum anahtarsızdır.</p>" +
        '<input id="gate-token" type="password" name="token" autocomplete="current-password" placeholder="Erişim anahtarı" />' +
        '<button type="submit">Kilidi aç</button>' +
        '<p class="gate-error" id="gate-error" hidden></p>' +
        "</form>";
      document.body.appendChild(box);
      document.getElementById("gate-form").addEventListener("submit", unlock);
    }
    document.documentElement.classList.add("gated");
    const err = document.getElementById("gate-error");
    if (errorText) {
      err.hidden = false;
      err.textContent = errorText;
    } else {
      err.hidden = true;
    }
    document.getElementById("gate-token")?.focus();
  }

  async function unlock(ev) {
    ev.preventDefault();
    const token = document.getElementById("gate-token")?.value || "";
    const res = await fetch("/auth/unlock", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
    if (!res.ok) {
      show("Anahtar eşleşmedi.");
      return;
    }
    hide();
  }

  async function boot() {
    try {
      const res = await fetch("/auth/status");
      if (!res.ok) return;
      const data = await res.json();
      if (data.required && !data.unlocked) show();
    } catch (_err) {
      /* local pages still work if the gate endpoint is missing */
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
