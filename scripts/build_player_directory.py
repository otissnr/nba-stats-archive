import json
import csv
from pathlib import Path

SEASONS = range(2021, 2028)


def main():
    players = {}

    print("BUILDING NBA PLAYER DIRECTORY")
    print("=" * 60)

    files_checked = 0
    files_skipped = 0

    for season in SEASONS:
        summary_dir = Path("raw/game_summaries") / str(season)

        if not summary_dir.exists():
            continue

        for file in summary_dir.glob("*.json"):
            try:
                with open(file) as f:
                    data = json.load(f)

                team_groups = data.get("boxscore", {}).get("players", [])

                for group in team_groups:
                    team = group.get("team", {})

                    team_id = team.get("id", "")
                    team_name = team.get("displayName") or team.get("name", "")
                    team_abbr = team.get("abbreviation", "")

                    for stat_group in group.get("statistics", []):
                        for entry in stat_group.get("athletes", []):
                            athlete = entry.get("athlete", {})
                            player_id = athlete.get("id")

                            if not player_id:
                                continue

                            player_id = str(player_id)

                            if player_id not in players:
                                players[player_id] = {
                                    "player_id": player_id,
                                    "name": athlete.get("displayName", ""),
                                    "short_name": athlete.get("shortName", ""),
                                    "position": athlete.get("position", {}).get("abbreviation", ""),
                                    "jersey": athlete.get("jersey", ""),
                                    "headshot": athlete.get("headshot", ""),
                                    "teams": {},
                                    "seasons": set()
                                }

                            player = players[player_id]

                            if team_id:
                                player["teams"][team_id] = {
                                    "team_id": team_id,
                                    "team_name": team_name,
                                    "team_abbreviation": team_abbr
                                }

                            player["seasons"].add(season)

                files_checked += 1

            except (json.JSONDecodeError, OSError, AttributeError, TypeError):
                files_skipped += 1

        print(f"Season {season}: directory scanned")

    output_dir = Path("exports")
    output_dir.mkdir(exist_ok=True)

    output = []

    for player in players.values():
        player["teams"] = list(player["teams"].values())
        player["seasons"] = sorted(player["seasons"])
        output.append(player)

    output.sort(key=lambda p: p["name"].lower())

    json_file = output_dir / "players.json"

    with open(json_file, "w") as f:
        json.dump(output, f, indent=2)

    csv_file = output_dir / "players.csv"

    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "player_id",
                "name",
                "short_name",
                "position",
                "jersey",
                "headshot",
                "teams",
                "seasons"
            ]
        )
        writer.writeheader()

        for player in output:
            row = player.copy()
            row["teams"] = "; ".join(
                team["team_name"] for team in player["teams"]
            )
            row["seasons"] = ", ".join(
                str(season) for season in player["seasons"]
            )
            writer.writerow(row)

    print("\n" + "=" * 60)
    print(f"Unique players found: {len(output):,}")
    print(f"Game summaries scanned: {files_checked:,}")
    print(f"Files skipped: {files_skipped:,}")
    print(f"Saved: {json_file}")
    print(f"Saved: {csv_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
