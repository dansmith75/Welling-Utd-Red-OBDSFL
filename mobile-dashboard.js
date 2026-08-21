// Mobile-first dashboard refinements.
// Keeps desktop behaviour intact while making the main iPhone views obvious and usable.
(() => {
  function isMobile() {
    return window.matchMedia("(max-width: 650px)").matches;
  }

  function allCompletedMatches() {
    return (store.matches || [])
      .filter(match => ["Win", "Draw", "Loss"].includes(match.result))
      .sort((a, b) => String(a.date || "").localeCompare(String(b.date || "")));
  }

  // Form guide now means actual recent form, including friendlies.
  renderFormGuide = function () {
    const lastFive = allCompletedMatches().slice(-5);
    const container = document.getElementById("formGuide");
    if (!container) return;

    container.innerHTML = lastFive.map(match => {
      const letter = match.result === "Win" ? "W" : match.result === "Draw" ? "D" : "L";
      const cls = match.result === "Win" ? "form-win" : match.result === "Draw" ? "form-draw" : "form-loss";
      const comp = match.competition ? ` · ${match.competition}` : "";

      return `
        <div
          class="form-pill ${cls}"
          title="${formatDateUK(match.date)} v ${match.opposition}${comp}"
          onclick="drillToResults('${formatDateUK(match.date)} vs ${match.opposition}', m => m.date === '${match.date}' && m.opposition === '${match.opposition}')"
        >${letter}</div>
      `;
    }).join("");
  };

  function horizontalPlayerBar(name, canvasId, labels, data, colour) {
    destroyChart(name);
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const box = canvas.closest(".chart-box");
    if (box) {
      box.classList.add("mobile-horizontal-player-chart");
      box.style.height = `${Math.max(420, labels.length * 30 + 70)}px`;
      box.style.minWidth = "0";
    }

    const maxValue = Math.max(...data, 0);

    charts[name] = new Chart(canvas, {
      type: "bar",
      data: {
        labels,
        datasets: [{
          data,
          backgroundColor: colour,
          borderRadius: 8
        }]
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          duration: 700,
          easing: "easeOutQuart"
        },
        layout: {
          padding: { right: 26, top: 8, bottom: 8 }
        },
        plugins: {
          legend: { display: false }
        },
        scales: {
          x: {
            beginAtZero: true,
            suggestedMax: maxValue + 1,
            ticks: {
              color: chartTextColour(),
              precision: 0
            },
            grid: { color: chartGridColour() }
          },
          y: {
            ticks: {
              color: chartTextColour(),
              autoSkip: false,
              font: { size: 11 }
            },
            grid: { display: false }
          }
        }
      }
    });
  }

  const coreRenderGoals = renderGoals;
  renderGoals = function () {
    if (!isMobile()) {
      document.querySelectorAll("#goals .chart-box").forEach(box => {
        box.classList.remove("mobile-horizontal-player-chart");
        box.style.height = "";
        box.style.minWidth = "";
      });
      coreRenderGoals();
      return;
    }

    setDrillLabel("goalsDrillLabel", activeGoalsDrillLabel);
    const filteredGoals = store.goals.filter(goalFilters);
    const filteredAssists = store.assists.filter(goalFilters);
    const players = dashboardPlayers();

    horizontalPlayerBar(
      "goalsByPlayer",
      "goalsByPlayerChart",
      players,
      goalTotals(filteredGoals),
      "rgba(37,99,235,.78)"
    );

    horizontalPlayerBar(
      "assistsByPlayer",
      "assistsByPlayerChart",
      players,
      assistTotals(filteredAssists),
      "rgba(56,189,248,.82)"
    );
  };

  function addMobileHints() {
    const resultsWrap = document.querySelector("#results .results-table-wrap");
    if (resultsWrap && !document.getElementById("resultsSwipeHint")) {
      const hint = document.createElement("div");
      hint.id = "resultsSwipeHint";
      hint.className = "mobile-swipe-hint";
      hint.textContent = "↔ Swipe left or right to see all match information";
      resultsWrap.parentNode.insertBefore(hint, resultsWrap);
    }

    const formCopy = document.querySelector("#overview .form-guide")?.closest(".card")?.querySelector(".executive");
    if (formCopy) formCopy.textContent = "Last 5 fixtures · friendlies included";
  }

  const style = document.createElement("style");
  style.textContent = `
    .mobile-swipe-hint {
      display:none;
      margin:0 0 10px;
      color:var(--muted);
      font-size:12px;
      font-weight:bold;
    }

    @media (max-width:650px) {
      .tabs {
        display:grid !important;
        grid-template-columns:repeat(4,minmax(0,1fr));
        gap:8px;
        overflow:visible !important;
        padding-bottom:0 !important;
      }

      .tab-btn {
        min-width:0;
        padding:10px 5px;
        font-size:12px;
        white-space:normal !important;
        text-align:center;
      }

      .mobile-swipe-hint {
        display:block;
      }

      #results .results-table-wrap {
        position:relative;
        border-right:2px solid rgba(56,189,248,.45);
        -webkit-overflow-scrolling:touch;
      }

      #goals .chart-scroll {
        overflow-x:visible;
        padding-bottom:4px;
      }

      #goals .chart-box.mobile-horizontal-player-chart {
        width:100%;
        min-width:0 !important;
      }
    }
  `;
  document.head.appendChild(style);

  window.addEventListener("DOMContentLoaded", addMobileHints, { once: true });
  window.addEventListener("resize", () => {
    const goalsPage = document.getElementById("goals");
    if (goalsPage?.classList.contains("active")) renderGoals();
  });
})();
