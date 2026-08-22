// Show the next unplayed fixture alongside the form guide.
(() => {
  function nextFixture() {
    return (store.matches || [])
      .filter(match => !match.postponed)
      .filter(match => match.goalsFor == null && match.goalsAgainst == null && !match.result)
      .slice()
      .sort((a, b) => String(a.date || "").localeCompare(String(b.date || "")))[0] || null;
  }

  function renderNextMatch() {
    const formGuide = document.getElementById("formGuide");
    const card = formGuide?.closest(".card");
    if (!formGuide || !card) return;

    let layout = card.querySelector(".form-next-layout");
    if (!layout) {
      const intro = card.querySelector(".executive");
      layout = document.createElement("div");
      layout.className = "form-next-layout";

      const formSide = document.createElement("div");
      formSide.className = "form-side";
      if (intro) formSide.appendChild(intro);
      formSide.appendChild(formGuide);

      const nextSide = document.createElement("div");
      nextSide.className = "next-match-side";
      nextSide.id = "nextMatchCard";

      layout.appendChild(formSide);
      layout.appendChild(nextSide);
      card.appendChild(layout);
    }

    const target = document.getElementById("nextMatchCard");
    if (!target) return;

    const match = nextFixture();
    if (!match) {
      target.innerHTML = `<div class="next-match-label">Next Match</div><div class="next-match-none">No upcoming fixture</div>`;
      target.onclick = null;
      return;
    }

    const venue = match.homeAway || match.venue || "";
    const competition = match.competition || "";
    target.innerHTML = `
      <div class="next-match-label">Next Match</div>
      <div class="next-match-opposition">${match.opposition || "TBC"}</div>
      <div class="next-match-meta">${formatDateUK(match.date)}${venue ? ` · ${venue}` : ""}</div>
      ${competition ? `<div class="next-match-competition">${competition}</div>` : ""}
      <div class="next-match-hint">View fixture →</div>
    `;
    target.onclick = () => drillToResults(
      `Next Match — ${formatDateUK(match.date)} vs ${match.opposition}`,
      m => m.id === match.id
    );
  }

  const coreRenderOverviewNextMatch = renderOverview;
  renderOverview = function () {
    coreRenderOverviewNextMatch();
    renderNextMatch();
  };

  const style = document.createElement("style");
  style.textContent = `
    .form-next-layout{display:grid;grid-template-columns:minmax(0,1fr) minmax(300px,.85fr);gap:28px;align-items:center}
    .form-side{min-width:0}
    .next-match-side{border-left:1px solid var(--line);padding:8px 8px 8px 28px;cursor:pointer;min-height:108px;display:flex;flex-direction:column;justify-content:center}
    .next-match-side:hover .next-match-opposition{color:#38bdf8}
    .next-match-label{font-size:12px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);font-weight:800;margin-bottom:6px}
    .next-match-opposition{font-size:24px;font-weight:800;line-height:1.15;color:var(--text);transition:color .15s ease}
    .next-match-meta{font-size:15px;color:var(--text);margin-top:7px}
    .next-match-competition{font-size:13px;color:var(--muted);margin-top:4px}
    .next-match-hint{font-size:12px;color:#38bdf8;margin-top:9px;font-weight:700}
    .next-match-none{font-size:16px;color:var(--muted)}
    @media(max-width:650px){
      .form-next-layout{grid-template-columns:1fr;gap:18px}
      .next-match-side{border-left:0;border-top:1px solid var(--line);padding:18px 0 0;min-height:0}
      .next-match-opposition{font-size:21px}
    }
  `;
  document.head.appendChild(style);
})();
