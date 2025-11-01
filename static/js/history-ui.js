document.addEventListener("DOMContentLoaded", async () => {
  const list = document.getElementById("hist-list");
  if (!list) return;

  const fmtDur = (s) => {
    s = Math.max(0, Number(s || 0) | 0);
    const m = Math.floor(s / 60), r = s % 60;
    return m ? `${m}m ${r}s` : `${r}s`;
  };

  try {
    const res = await fetch("/calls/history", { credentials: "same-origin" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const items = Array.isArray(data) ? data : (data.calls || data.history || data.results || []);
    list.replaceChildren();

    if (!items.length) {
      list.innerHTML = '<p class="muted small">No calls yet.</p>';
      return;
    }

    items.forEach(it => {
      const name = it.peer_display_name || it.receiver_display_name || it.caller_display_name || it.peer_name || "User";
      const phone = it.peer_phone || it.receiver_phone || it.caller_phone || null;
      const startedUTC = it.started_at || it.start_time || "";
      const started = startedUTC ? new Date(startedUTC).toLocaleString() : "";
      const dur = it.duration_sec != null ? it.duration_sec : it.duration || 0;
      const rawTox = (it.avg_toxicity != null ? it.avg_toxicity : it.toxicity_avg);
      const tox = (rawTox == null ? "—" : Number(rawTox).toFixed(3));
      const lang = it.language || it.lang || "";

      const row = document.createElement("div");
      row.className = "cell";
      row.innerHTML = `
        <div class="cell__main">
          <div class="cell__title">${name}</div>
          <div class="cell__sub">${started} · ${fmtDur(dur)} · avg tox ${tox}</div>
        </div>
        <div class="cell__actions">
          ${lang ? `<span class="chip">${lang}</span>` : ""}
          ${phone ? `<a class="chip chip-success" href="/?dial=${encodeURIComponent(phone)}">Call</a>` : ""}
        </div>
      `;
      list.appendChild(row);
    });
  } catch (e) {
    console.error("History load failed:", e);
    list.innerHTML = '<p class="muted small">Could not load history.</p>';
  }
});
