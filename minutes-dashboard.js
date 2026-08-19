// Player minutes reporting and player-summary layout for the Welling dashboard.
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

  function statCard(value, label, onclick = "", tone = "") {
    const clickable = onclick ? " clickable" : "";
    const toneClass = tone ? ` ${tone}` : "";
    const action = onclick ? ` onclick="${onclick}"` : "";
    return `<div class="stat${toneClass}${clickable}"${action}><b>${value}</b><span>${label}</span></div>`;
  }

  // Keep the player summary as a tidy 4 x 2 grid on desktop. All cards use
  // identical dimensions, regardless of label length.
  const style = document.createElement("style");
  style.textContent = `
    #playerProfile .summary.player-summary-grid {
      display:grid;
      grid-template-columns:repeat(4,minmax(0,1fr));
      gap:14px;
    }
    #playerProfile .summary.player-summary-grid .stat {
      min-width:0;
      min-height:114px;
      height:114px;
      display:flex;
      flex-direction:column;
      justify-content:center;
      align-items:flex-start;
    }
    @media (max-width:760px) {
      #playerProfile .summary.player-summary-grid {
        grid-template-columns:repeat(2,minmax(0,1fr));
      }
    }
    @media (max-width:430px) {
      #playerProfile .summary.player-summary-grid {
        grid-template-columns:1fr;
      }
    }
  `;
  document.head.appendChild(style);

  const coreRenderPlayerProfile = renderPlayerProfile;
  renderPlayerProfile = function (player) {
    coreRenderPlayerProfile(player);
    const summary = document.querySelector("#playerProfile .summary");
    if (!summary) return;

    const stats = minutesSummary(player);
    const goals = getPlayerGoals(player);
    const assists = getPlayerAssists(player);
    const cards = getCardCounts(player);
    const trainingAttendance = countAttendanceForPlayer(store.trainingAttendance, player);
    const injuryWeeks = getInjuryDates(player).length;

    summary.classList.add("player-summary-grid");
    summary.innerHTML = [
      statCard(goals, "Goals", `showPlayerDetail('${player}', 'goals')`),
      statCard(assists, "Assists", `showPlayerDetail('${player}', 'assists')`),
      statCard(stats.appearances, "Appearances", `showPlayerDetail('${player}', 'minutes')`),
      statCard(stats.totalMinutes, "Minutes Played", `showPlayerDetail('${player}', 'minutes')`),
      statCard(cards.yellow, "Yellow Cards", `showPlayerDetail('${player}', 'yellowCards')`, "warning"),
      statCard(cards.red, "Red Cards", `showPlayerDetail('${player}', 'redCards')`, "danger"),
      statCard(trainingAttendance, "Training Attendances", `showPlayerDetail('${player}', 'trainingAttendance')`, "training"),
      statCard(injuryWeeks, "Weeks Injured", `showPlayerDetail('${player}', 'injuries')`),
    ].join("");
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
        <p><strong>${stats.totalMinutes}</strong> minutes across <strong>${stats.appearances}</strong> appearances.</p>
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
