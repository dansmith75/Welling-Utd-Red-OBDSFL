// Add opposition to the Player > Match Attendance drill-down.
(() => {
  if (typeof showPlayerDetail !== "function") return;

  const originalShowPlayerDetail = showPlayerDetail;

  window.showPlayerDetail = function (player, type) {
    if (type !== "matchAttendance") {
      return originalShowPlayerDetail(player, type);
    }

    const box = document.getElementById("playerDetailBox");
    if (!box) return;

    const games = attendanceRecordsForPlayer(player, "Match")
      .filter(record => isAttendancePresent(record.status))
      .map(record => {
        const match = (store.matches || []).find(item => item.date === record.date);
        const opposition = match?.opposition ? ` vs ${match.opposition}` : "";
        const homeAway = record.venue || match?.homeAway || match?.venue || "";
        return `
          <li>
            ${formatDateUK(record.date)}${opposition}
            ${homeAway ? ` — ${homeAway}` : ""}
            ${record.status ? ` — ${record.status}` : ""}
          </li>
        `;
      });

    box.innerHTML = `
      <div class="player-detail-box">
        <h2>${player} — Match Attendance</h2>
        ${games.length ? `<ul>${games.join("")}</ul>` : `<p>No match attendances recorded for ${player}.</p>`}
      </div>
    `;
  };
})();
