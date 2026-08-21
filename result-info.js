// Results-page match information panel: full Matchday timeline where recorded.
(() => {
  store.timeline = store.timeline || [];

  // Visit counter is no longer part of the Dashboard UI.
  setupVisitCounter = function () {
    document.getElementById("visitCounter")?.remove();
  };

  function minuteText(value) {
    if (value === null || value === undefined || value === "") return "";
    const number = Number(value);
    if (Number.isFinite(number)) return `${Math.round(number)}' `;
    return `${value}' `;
  }

  function timelineForMatch(match) {
    return (store.timeline || []).find(row =>
      (row.matchId && match.id && row.matchId === match.id) ||
      (row.date === match.date && row.opposition === match.opposition)
    );
  }

  function parsedDetail(detail) {
    if (!detail) return null;
    if (typeof detail === "object") return detail;
    const text = String(detail).trim();
    if (!text.startsWith("{") || !text.endsWith("}")) return null;
    try {
      return JSON.parse(text);
    } catch (_) {
      return null;
    }
  }

  function cleanGoalDetail(detail, fallback = "") {
    const parsed = parsedDetail(detail);
    if (parsed) {
      return String(parsed.goalType || parsed.detail || fallback || "").trim();
    }
    const text = String(detail || fallback || "").trim();
    return text.toLowerCase() === "goal" ? "" : text;
  }

  function formatTimelineEvent(event) {
    const type = String(event.type || "Event").trim();
    const typeLower = type.toLowerCase();
    const minute = minuteText(event.minute);
    const player = event.player || event.playerId || "";
    const related = event.relatedPlayer || event.relatedPlayerId || "";
    const detail = String(event.detail || "").trim();

    if (typeLower === "substitution") {
      return `${minute}<strong>🔄 Substitution</strong> — ${related || "Player"} on for ${player || "Player"}`;
    }

    if (typeLower === "goal") {
      const goalType = cleanGoalDetail(detail);
      const goalDetail = goalType ? ` · ${goalType}` : "";
      const assist = related ? ` <span class="timeline-muted">(assist: ${related})</span>` : "";
      return `${minute}<strong>⚽ Goal — ${player || "Welling"}</strong>${assist}${goalDetail}`;
    }

    if (typeLower === "own goal") {
      const goalType = cleanGoalDetail(detail, "Own Goal");
      const extra = goalType && goalType.toLowerCase() !== "own goal" ? ` · ${goalType}` : "";
      return `${minute}<strong>⚽ Own Goal — Welling</strong>${extra}`;
    }

    if (typeLower === "opponent goal") {
      const goalType = cleanGoalDetail(detail);
      return `${minute}<strong>⚽ Opponent Goal</strong>${goalType ? ` · ${goalType}` : ""}`;
    }

    if (typeLower === "card") {
      const card = detail || "Card";
      const icon = card.toLowerCase().includes("red") ? "🟥" : card.toLowerCase().includes("yellow") ? "🟨" : "🟨";
      return `${minute}<strong>${icon} ${card}</strong>${player ? ` — ${player}` : ""}`;
    }

    if (typeLower === "note") {
      return `${minute}<strong>📝 Note</strong>${player ? ` — ${player}` : ""}${detail ? `: ${detail}` : ""}`;
    }

    return `${minute}<strong>${type}</strong>${player ? ` — ${player}` : ""}${detail ? ` · ${detail}` : ""}`;
  }

  function legacyInfoForMatch(match) {
    const lines = [];
    const goalRow = (store.goals || []).find(row => row.date === match.date && row.opposition === match.opposition);
    const assistRow = (store.assists || []).find(row => row.date === match.date && row.opposition === match.opposition);
    const eventRow = (store.events || []).find(row => row.date === match.date && row.opposition === match.opposition);

    Object.entries(goalRow?.goals || {}).forEach(([player, count]) => {
      const n = safeNumber(count);
      if (n > 0) lines.push(`<li><strong>⚽ Goal${n > 1 ? "s" : ""}</strong> — ${player}${n > 1 ? ` (${n})` : ""}</li>`);
    });

    Object.entries(assistRow?.assists || {}).forEach(([player, count]) => {
      const n = safeNumber(count);
      if (n > 0) lines.push(`<li><strong>Assist${n > 1 ? "s" : ""}</strong> — ${player}${n > 1 ? ` (${n})` : ""}</li>`);
    });

    Object.entries(eventRow?.events || {}).forEach(([player, event]) => {
      if (isRealEvent(event)) lines.push(`<li><strong>📝 ${player}</strong> — ${event}</li>`);
    });

    return lines;
  }

  renderResults = function () {
    const label = activeResultsFilter?.label || "";
    const rows = activeResultsFilter ? store.matches.filter(activeResultsFilter.filterFn) : store.matches;

    setDrillLabel("resultsDrillLabel", label);
    document.getElementById("resultsTitle").textContent = label || "Match Results";

    document.getElementById("resultsTable").innerHTML = rows.map((match, index) => {
      const timeline = timelineForMatch(match);
      const detailedEvents = (timeline?.events || []).map(event => `<li>${formatTimelineEvent(event)}</li>`);
      const fallback = detailedEvents.length ? [] : legacyInfoForMatch(match);
      const information = detailedEvents.length ? detailedEvents : fallback;

      return `
        <tr>
          <td>${formatDateUK(match.date)}</td>
          <td>${match.opposition || ""}</td>
          <td>${match.homeAway || ""}</td>
          <td>${match.competition || ""}</td>
          <td>${safeNumber(match.goalsFor)}</td>
          <td>${safeNumber(match.goalsAgainst)}</td>
          <td><span class="result-badge ${resultClass(match.result)}">${match.result || ""}</span></td>
          <td><button class="scorers-btn" onclick="toggleScorers(${index})">Info</button></td>
        </tr>
        <tr class="scorers-row" id="scorers-row-${index}">
          <td colspan="8">
            <div class="scorers-box match-info-box">
              <div class="match-info-heading">
                <strong>${formatDateUK(match.date)} · ${match.homeAway || ""} vs ${match.opposition || ""}</strong>
                <span>${match.competition || ""} · ${safeNumber(match.goalsFor)}–${safeNumber(match.goalsAgainst)} ${match.result || ""}</span>
              </div>
              <h3>Game Timeline</h3>
              ${information.length
                ? `<ol class="match-timeline">${information.join("")}</ol>`
                : `<p class="timeline-muted">No detailed match events were recorded for this fixture.</p>`}
            </div>
          </td>
        </tr>
      `;
    }).join("");
  };

  const style = document.createElement("style");
  style.textContent = `
    #visitCounter,
    #overview .card.executive {
      display:none !important;
    }
    .match-info-heading {
      display:flex;
      flex-wrap:wrap;
      justify-content:space-between;
      gap:8px 18px;
      margin-bottom:16px;
    }
    .match-info-heading span,
    .timeline-muted {
      color:var(--muted);
    }
    .match-info-box h3 {
      margin:0 0 10px;
    }
    .match-timeline {
      margin:0;
      padding-left:24px;
    }
    .match-timeline li {
      padding:7px 0;
      line-height:1.45;
      border-bottom:1px solid var(--line);
    }
    .match-timeline li:last-child {
      border-bottom:0;
    }
  `;
  document.head.appendChild(style);

  fetch("data/timeline.json", { cache: "no-store" })
    .then(response => response.ok ? response.json() : [])
    .then(rows => {
      store.timeline = Array.isArray(rows) ? rows : [];
      if (document.getElementById("results")?.classList.contains("active")) renderResults();
    })
    .catch(() => {
      store.timeline = [];
    });
})();
