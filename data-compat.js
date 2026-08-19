// Compatibility layer between stable ID-based JSON exports and the dashboard UI.
// Excel/JSON keep player IDs for reliable joins; the UI always shows displayName.

let wellingDataNormalised = false;

function wellingDisplayNameForId(playerId) {
  const player = (store.players || []).find(item => item && item.id === playerId);
  return player?.displayName || playerId;
}

function wellingMapPlayerKeys(values) {
  if (!values || typeof values !== "object") return values;

  return Object.entries(values).reduce((mapped, [playerId, value]) => {
    mapped[wellingDisplayNameForId(playerId)] = value;
    return mapped;
  }, {});
}

function wellingFindMatch(row) {
  return (store.matches || []).find(match =>
    match.date === row.date && match.opposition === row.opposition
  );
}

function wellingNormaliseResult(value) {
  const text = String(value || "").trim().toLowerCase();
  if (text === "w" || text === "win") return "Win";
  if (text === "l" || text === "loss" || text === "lose") return "Loss";
  if (text === "d" || text === "draw") return "Draw";
  return value || "";
}

function normaliseWellingDashboardData() {
  if (wellingDataNormalised) return;
  if (!store.players || !store.matches) return;

  // homeAway is now the canonical fixture field. `venue` is retained only as a
  // temporary compatibility alias for older consumers of the shared match feed.
  // Also normalise historic W/L/D values so every result uses the same coloured badge.
  store.matches.forEach(match => {
    if (!match.homeAway && match.venue) match.homeAway = match.venue;
    if (!match.venue && match.homeAway) match.venue = match.homeAway;
    match.result = wellingNormaliseResult(match.result);
  });

  store.goals = (store.goals || []).map(row => {
    const match = wellingFindMatch(row);
    return {
      ...row,
      competition: row.competition || match?.competition || null,
      homeAway: row.homeAway || row.venue || match?.homeAway || match?.venue || null,
      goals: wellingMapPlayerKeys(row.goals)
    };
  });

  store.assists = (store.assists || []).map(row => {
    const match = wellingFindMatch(row);
    return {
      ...row,
      competition: row.competition || match?.competition || null,
      homeAway: row.homeAway || row.venue || match?.homeAway || match?.venue || null,
      assists: wellingMapPlayerKeys(row.assists)
    };
  });

  store.events = (store.events || []).map(row => ({
    ...row,
    events: wellingMapPlayerKeys(row.events)
  }));

  wellingDataNormalised = true;
}

// Preserve inactive players in JSON for historic records, but only show the
// active squad in current player selectors and charts.
dashboardPlayers = function () {
  return (store.players || [])
    .filter(player => player && player.active === true)
    .map(playerName)
    .filter(Boolean);
};

// loadData() is already running when this file loads. Wrapping the first render
// means normalisation happens after all JSON has arrived but before anything is
// displayed. All later pages then consume display-name keyed data.
const wellingOriginalRenderOverview = renderOverview;
renderOverview = function () {
  normaliseWellingDashboardData();
  return wellingOriginalRenderOverview();
};
