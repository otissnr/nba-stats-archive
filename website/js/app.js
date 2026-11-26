// NBA Stats Archive - Dashboard Application

document.addEventListener("DOMContentLoaded", () => {
    loadWeeklyDashboard();
});

async function loadWeeklyDashboard() {
    const status = document.getElementById("dashboard-status");
    const content = document.getElementById("dashboard-content");

    try {
        const response = await fetch(
            `data/weekly_dashboard.json?t=${Date.now()}`
        );

        if (!response.ok) {
            throw new Error("Dashboard data could not be loaded.");
        }

        const data = await response.json();

        renderDashboard(data);

        status.hidden = true;
        content.hidden = false;

    } catch (error) {
        status.textContent =
            "Weekly statistics are temporarily unavailable. Please try again later.";

        status.classList.add("error");
        console.error("Dashboard error:", error);
    }
}

function renderDashboard(data) {
    renderReportingPeriod(data);
    renderSummary(data.summary);
    renderPlayerLeaders(data.player_leaders);
    renderDailyScoring(data.daily_scoring);
    renderTeamForm(data.team_form);
    renderLatestResults(data.games);
    setupLeaderTabs(data.player_leaders);
}

function renderReportingPeriod(data) {
    const start = formatDate(data.reporting_period.start);
    const end = formatDate(data.reporting_period.end);

    document.getElementById("dashboard-period").textContent =
        `${start} – ${end} · ${data.season} Season`;
}

function renderSummary(summary) {
    document.getElementById("weekly-games").textContent =
        summary.games_played.toLocaleString();

    document.getElementById("weekly-points").textContent =
        Math.round(summary.total_points).toLocaleString();

    document.getElementById("weekly-average").textContent =
        summary.average_points_per_game.toFixed(1);

    document.getElementById("weekly-players").textContent =
        summary.players_in_action.toLocaleString();
}

function setupLeaderTabs(leaders) {
    const tabs = document.querySelectorAll(".leader-tab");

    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(item => item.classList.remove("active"));
            tab.classList.add("active");

            renderPlayerLeaders(leaders, tab.dataset.stat);
        });
    });
}

function renderPlayerLeaders(leaders, category = "points") {
    const container = document.getElementById("player-leaders");
    const players = leaders[category] || [];

    container.replaceChildren();

    players.forEach((player, index) => {
        const row = document.createElement("div");
        row.className = "leader-row";

        const rank = document.createElement("span");
        rank.className = "leader-rank";
        rank.textContent = index + 1;

        const identity = document.createElement("div");

        const name = document.createElement("span");
        name.className = "leader-name";
        name.textContent = player.player_name;

        const games = document.createElement("span");
        games.className = "leader-games";
        games.textContent =
            `${player.team} · ${player.games} games`;

        identity.append(name, games);

        const value = document.createElement("span");
        value.className = "leader-value";
        value.textContent = Math.round(player[category]).toLocaleString();

        row.append(rank, identity, value);
        container.appendChild(row);
    });
}

function renderDailyScoring(days) {
    const container = document.getElementById("daily-scoring");
    container.replaceChildren();

    const maximum = Math.max(
        ...days.map(day => day.total_points),
        1
    );

    days.forEach(day => {
        const column = document.createElement("div");
        column.className = "scoring-day";

        const total = document.createElement("span");
        total.className = "scoring-total";
        total.textContent = Math.round(day.total_points).toLocaleString();

        const bar = document.createElement("div");
        bar.className = "scoring-bar";
        bar.style.height =
            `${Math.max(5, (day.total_points / maximum) * 125)}px`;

        bar.title =
            `${day.games} games · ${day.total_points.toLocaleString()} points`;

        const date = document.createElement("span");
        date.className = "scoring-date";
        date.textContent = formatShortDate(day.date);

        column.append(total, bar, date);
        container.appendChild(column);
    });
}

function renderTeamForm(teams) {
    const container = document.getElementById("team-form");
    container.replaceChildren();

    teams.forEach(team => {
        const row = document.createElement("tr");

        const difference = team.points_for - team.points_against;

        const values = [
            team.team,
            team.wins,
            team.losses,
            team.points_for,
            team.points_against,
            difference > 0 ? `+${difference}` : difference
        ];

        values.forEach((value, index) => {
            const cell = document.createElement("td");
            cell.textContent = index >= 3
                ? Number(value).toLocaleString()
                : value;

            if (index === 0) {
                cell.className = "team-name";
            }

            if (index === 5) {
                cell.className =
                    difference >= 0 ? "positive-diff" : "negative-diff";
            }

            row.appendChild(cell);
        });

        container.appendChild(row);
    });
}

function renderLatestResults(games) {
    const container = document.getElementById("latest-results");
    container.replaceChildren();

    const sortedGames = [...games].sort((a, b) =>
        b.local_date.localeCompare(a.local_date) ||
        b.game_id.localeCompare(a.game_id)
    );

    sortedGames.forEach(game => {
        const card = document.createElement("div");
        card.className = "result-card";

        const date = document.createElement("div");
        date.className = "result-date";
        date.textContent = formatDate(game.local_date);

        const away = createResultTeam(
            game.away_team,
            game.away_score,
            game.away_winner
        );

        const home = createResultTeam(
            game.home_team,
            game.home_score,
            game.home_winner
        );

        card.append(date, away, home);
        container.appendChild(card);
    });
}

function createResultTeam(name, score, winner) {
    const row = document.createElement("div");
    row.className = "result-team";

    if (winner) {
        row.classList.add("winner");
    }

    const team = document.createElement("span");
    team.textContent = name;

    const points = document.createElement("strong");
    points.textContent = score;

    row.append(team, points);

    return row;
}

function formatDate(value) {
    const date = new Date(`${value}T00:00:00`);

    return date.toLocaleDateString("en-AU", {
        day: "numeric",
        month: "short",
        year: "numeric"
    });
}

function formatShortDate(value) {
    const date = new Date(`${value}T00:00:00`);

    return date.toLocaleDateString("en-AU", {
        weekday: "short",
        day: "numeric"
    });
}
