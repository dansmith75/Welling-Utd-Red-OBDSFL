// Final UI refinements: Fixtures naming and richer player profiles.
(() => {
  store.bios = store.bios || [];

  function playerRecord(displayName) {
    return (store.players || []).find(player =>
      String(player?.displayName || "").trim() === String(displayName || "").trim()
    ) || null;
  }

  function bioRecord(displayName) {
    return (store.bios || []).find(player =>
      String(player?.displayName || "").trim() === String(displayName || "").trim()
    ) || null;
  }

  function fallbackBio(position) {
    const p = String(position || "").toLowerCase();
    if (/keeper|goalkeeper|\bgk\b/.test(p)) return "Goalkeeper. Keeps the ball out, organises the defence and reserves the right to shout at everybody while doing it.";
    if (/wing|wide/.test(p)) return "Wide player. There to stretch the pitch, attack defenders and make full-backs question their career choices.";
    if (/striker|forward|\bcf\b/.test(p)) return "Forward. Lives around the penalty area, survives on chances and is permanently convinced the next one is going in.";
    if (/mid|\bcm\b|\bdm\b|\bam\b/.test(p)) return "Midfielder. Wins it, keeps it, moves it and somehow gets asked to do the same thing again thirty seconds later.";
    if (/back|def|\bcb\b|\blb\b|\brb\b/.test(p)) return "Defender. Happy in a duel, happier after a clean sheet and happiest when the striker stops enjoying himself.";
    return "Versatile squad player. Position: wherever the manager has created a problem that needs solving.";
  }

  function fallbackStrapline(position) {
    const p = String(position || "").toLowerCase();
    if (/keeper|goalkeeper|\bgk\b/.test(p)) return "Hands like glue. Volume control still under development.";
    if (/wing|wide/.test(p)) return "One mission: get at the full-back until one of them needs a sit down.";
    if (/striker|forward|\bcf\b/.test(p)) return "Shoots on sight. Definition of sight may vary.";
    if (/mid|\bcm\b|\bdm\b|\bam\b/.test(p)) return "Covers every blade of grass, including a few that aren't technically on the pitch.";
    if (/back|def|\bcb\b|\blb\b|\brb\b/.test(p)) return "Built for tackles, headers and insisting it was definitely all ball.";
    return "Position: yes. Job: whatever needs doing.";
  }

  // The page contains both upcoming fixtures and completed results, so the
  // top-level destination is simply Fixtures.
  const coreRenderResults = renderResults;
  renderResults = function () {
    coreRenderResults();
    const title = document.getElementById("resultsTitle");
    if (title && !activeResultsFilter?.label) title.textContent = "Fixtures";
  };

  // Do not auto-open the first player. Profiles remain hidden until somebody
  // deliberately selects a player button.
  renderPlayers = function () {
    renderPlayerButtons();
    const profile = document.getElementById("playerProfile");
    if (!profile) return;

    if (!selectedPlayer) {
      profile.innerHTML = "";
      return;
    }

    renderPlayerProfile(selectedPlayer);
  };

  const coreRenderPlayerProfile = renderPlayerProfile;
  renderPlayerProfile = function (player) {
    coreRenderPlayerProfile(player);

    const profileHeader = document.querySelector("#playerProfile .profile-header");
    if (!profileHeader) return;

    const squad = playerRecord(player) || {};
    const bio = bioRecord(player) || {};
    const position = bio.position || squad.position || "Squad Player";
    const bioText = bio.bio || fallbackBio(position);
    const strapLine = bio.strapLine || fallbackStrapline(position);

    const oldSubtitle = profileHeader.querySelector(".profile-subtitle");
    if (oldSubtitle) oldSubtitle.remove();

    profileHeader.insertAdjacentHTML("beforeend", `
      <div class="player-position">${position}</div>
      <p class="player-bio">${bioText}</p>
      <div class="player-strapline">“${strapLine}”</div>
    `);
  };

  const style = document.createElement("style");
  style.textContent = `
    .player-position {
      display:inline-block;
      margin-top:8px;
      padding:5px 10px;
      border-radius:999px;
      background:rgba(56,189,248,.12);
      border:1px solid var(--line);
      color:var(--text);
      font-size:12px;
      font-weight:bold;
    }
    .player-bio {
      margin:14px 0 8px;
      color:var(--muted);
      line-height:1.55;
      max-width:850px;
    }
    .player-strapline {
      color:var(--text);
      font-weight:bold;
      font-style:italic;
      line-height:1.45;
    }
  `;
  document.head.appendChild(style);

  fetch("data/bios.json", { cache: "no-store" })
    .then(response => response.ok ? response.json() : [])
    .then(rows => {
      store.bios = Array.isArray(rows) ? rows : [];
      if (selectedPlayer && document.getElementById("players")?.classList.contains("active")) {
        renderPlayerProfile(selectedPlayer);
      }
    })
    .catch(() => {
      store.bios = [];
    });
})();
