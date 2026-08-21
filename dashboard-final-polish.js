// Final UI refinements: Fixtures naming and compact player profiles.
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

  // The page contains both upcoming fixtures and completed results, so the
  // top-level destination is simply Fixtures.
  const coreRenderResults = renderResults;
  renderResults = function () {
    coreRenderResults();
    const title = document.getElementById("resultsTitle");
    if (title && !activeResultsFilter?.label) title.textContent = "Fixtures";
  };

  // Player buttons act as toggles: click to open, click the selected player
  // again to close, or click another player to switch profiles.
  renderPlayerButtons = function () {
    const grid = document.getElementById("playerGrid");
    if (!grid) return;

    const players = dashboardPlayers();
    grid.innerHTML = players.map(player => `
      <button class="player-button${selectedPlayer === player ? " active" : ""}" data-player="${player}">${player}</button>
    `).join("");

    grid.querySelectorAll(".player-button").forEach(button => {
      button.addEventListener("click", () => {
        const player = button.dataset.player;
        const profile = document.getElementById("playerProfile");

        if (selectedPlayer === player) {
          selectedPlayer = null;
          grid.querySelectorAll(".player-button").forEach(item => item.classList.remove("active"));
          if (profile) profile.innerHTML = "";
          return;
        }

        selectedPlayer = player;
        grid.querySelectorAll(".player-button").forEach(item => {
          item.classList.toggle("active", item.dataset.player === player);
        });
        renderPlayerProfile(player);
      });
    });
  };

  // Profiles remain hidden until somebody deliberately selects a player.
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

    const oldSubtitle = profileHeader.querySelector(".profile-subtitle");
    if (oldSubtitle) oldSubtitle.remove();

    const heading = profileHeader.querySelector("h2");
    if (heading) {
      heading.classList.add("player-name-row");
      heading.innerHTML = `<span>${player}</span><span class="player-position">${position}</span>`;
    }

    profileHeader.insertAdjacentHTML("beforeend", `
      <p class="player-bio">${bioText}</p>
    `);
  };

  const style = document.createElement("style");
  style.textContent = `
    .player-name-row {
      display:flex;
      align-items:center;
      flex-wrap:wrap;
      gap:10px;
    }
    .player-position {
      display:inline-flex;
      align-items:center;
      padding:5px 10px;
      border-radius:999px;
      background:rgba(56,189,248,.12);
      border:1px solid var(--line);
      color:var(--text);
      font-size:12px;
      font-weight:bold;
      line-height:1;
    }
    .player-bio {
      margin:10px 0 0;
      color:var(--muted);
      line-height:1.55;
      max-width:850px;
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
