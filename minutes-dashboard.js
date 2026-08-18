// Player minutes reporting for the Welling dashboard.
// Minutes are exported from Excel MatchdayRecords, which is populated from
// completed Matchday submissions in Supabase.
(() => {
  const MINUTES_URL = "data/minutes.json";

  function number(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function recordsForPlayer(player) {
    return (store.minutes || []).filter(record =>
      String(record.displayName || "").trim() === String(player || "").trim()
    );
  }

  function minutesSummary(player) {
    const records = recordsForPlayer(player);
    const appearances = records.filter(record => number(record.minutes) > 0);
    const totalMinutes = appearances.reduce((sum, record) => sum + number(record.minutes), 0);
    const starts = appearances.filter(record => record.starter === true).length;
    return {
      totalMinutes: Math.round(totalMinutes),
      appearances: appearances.length,
      starts,
      averageMinutes: appearances.length ? Math.round(totalMinutes / appearances.length) : 0,
    };
  }

  function statCard(value, label, onclick = "") {
    const clickable = onclick ? " clickable" : "";
    const action = onclick ? ` onclick="${onclick}"` : "";
    return `<div class="stat${clickable}"${action}><b>${value}</b><span>${label}</span></div>`;
  }

  const coreRenderPlayerProfile = renderPlayerProfile;
  renderPlayerProfile = function (player) {
    coreRenderPlayerProfile(player);
    const summary = document.querySelector("#playerProfile .summary");
    if (!summary) return;

    const stats = minutesSummary(player);
    summary.insertAdjacentHTML("beforeend", [
      statCard(stats.totalMinutes, "Minutes Played", `showPlayerDetail('${player}', 'minutes')`),
      statCard(stats.appearances, "Appearances", `showPlayerDetail('${player}', 'minutes')`),
      statCard(stats.starts, "Starts"),
      statCard(stats.averageMinutes, "Avg Minutes"),
    ].join(""));
  };

  const coreShowPlayerDetail = showPlayerDetail;
  showPlayerDetail = function (player, type) {
    if (type !== "minutes") {
      coreShowPlayerDetail(player, type);
      return;
    }

    const box = document.getElementById("playerDetailBox");
    if (!box) return;

    const records = recordsForPlayer(player)
      .filter(record => number(record.minutes) > 0)
      .sort((a, b) => String(a.date || "").localeCompare(String(b.date || "")));

    const stats = minutesSummary(player);
    const items = records.map(record => {
      const role = record.starter ? "Started" : "Sub appearance";
      const competition = record.competition ? ` · ${record.competition}` : "";
      return `<li><strong>${formatDateUK(record.date)}</strong> vs ${record.opposition || ""}${competition} — <strong>${Math.round(number(record.minutes))} min</strong> · ${role}</li>`;
    });

    box.innerHTML = `
      <div class="player-detail-box">
        <h2>${player} — Minutes Played</h2>
        <p><strong>${stats.totalMinutes}</strong> minutes across <strong>${stats.appearances}</strong> appearances · <strong>${stats.starts}</strong> starts · <strong>${stats.averageMinutes}</strong> min average.</p>
        ${items.length ? `<ul>${items.join("")}</ul>` : `<p>No playing minutes recorded for ${player} yet.</p>`}
      </div>
    `;
  };

  fetch(MINUTES_URL, { cache: "no-store" })
    .then(response => response.ok ? response.json() : [])
    .then(rows => {
      store.minutes = Array.isArray(rows) ? rows : [];
      const playersPage = document.getElementById("players");
      if (playersPage?.classList.contains("active") && selectedPlayer) {
        renderPlayerProfile(selectedPlayer);
      }
    })
    .catch(() => {
      store.minutes = [];
    });
})();
