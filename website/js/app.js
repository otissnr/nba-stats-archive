// NBA Stats Archive - Main Application

document.addEventListener("DOMContentLoaded", () => {

    const seasonCards = document.querySelectorAll(".season-card");

    seasonCards.forEach((card, index) => {

        const season = 2021 + index;
        const seasonName = `${season - 1}-${String(season).slice(-2)}`;

        card.addEventListener("click", () => {
            openSeason(season, seasonName);
        });

        card.setAttribute("role", "button");
        card.setAttribute("tabindex", "0");

        card.addEventListener("keydown", event => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                openSeason(season, seasonName);
            }
        });

    });

});

function openSeason(season, seasonName) {

    alert(
        `NBA ${seasonName} Season\n\n` +
        `Season data will be loaded here.\n\n` +
        `Games, player statistics, team statistics and season leaders.`
    );

}
