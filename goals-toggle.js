(() => {
  let mode = "goals";

  function applyMode() {
    document.querySelectorAll(".goals-mode").forEach(button => {
      button.classList.toggle("active", button.dataset.goalsMode === mode);
    });

    const goals = document.getElementById("goalsChartContainer");
    const assists = document.getElementById("assistsChartContainer");
    if (goals) goals.style.display = mode === "goals" ? "block" : "none";
    if (assists) assists.style.display = mode === "assists" ? "block" : "none";

    if (document.getElementById("goals")?.classList.contains("active")) {
      setTimeout(() => {
        if (typeof renderGoals === "function") renderGoals();
      }, 30);
    }
  }

  document.querySelectorAll(".goals-mode").forEach(button => {
    button.addEventListener("click", () => {
      mode = button.dataset.goalsMode === "assists" ? "assists" : "goals";
      applyMode();
    });
  });

  const style = document.createElement("style");
  style.textContent = `
    .goals-toggle-card{padding:10px;margin-bottom:18px}
    .goals-toggle{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
    .goals-mode{border:1px solid var(--line);border-radius:12px;padding:11px 16px;background:transparent;color:var(--text);font-weight:bold;cursor:pointer}
    .goals-mode.active{background:linear-gradient(135deg,#1e3a8a,#2563eb);border-color:#2563eb;color:white}
  `;
  document.head.appendChild(style);

  applyMode();
})();
