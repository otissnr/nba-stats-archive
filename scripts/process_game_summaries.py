import json
from pathlib import Path
from collections import defaultdict

SEASONS = range(2021, 2028)

def safe_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

def process_game(file_path, season):
    with open(file_path) as f:
        data = json.load(f)

    header = data.get("header", {})
    competition = header.get("competitions", [{}])[0]

    game_id = header.get("id")
    if not game_id:
        game_id = file_path.stem

    game = {
        "game_id": game_id,
        "season": season,
        "date": competition.get("date"),
        "status": competition.get("status", {}).get("type", {}).get("description"),
        "venue": competition.get("venue", {}).get("fullName"),
        "attendance": competition.get("attendance"),
    }

    for competitor in competition.get("competitors", []):
        side = competitor.get("homeAway")
        team = competitor.get("team", {})
        prefix = "home" if side == "home" else "away"

        game[f"{prefix}_team_id"] = team.get("id")
        game[f"{prefix}_team"] = team.get("displayName")
        game[f"{prefix}_abbreviation"] = team.get("abbreviation")
        game[f"{prefix}_score"] = safe_int(competitor.get("score"))
        game[f"{prefix}_winner"] = competitor.get("winner")

    players = []
    teams = []

    for team_group in data.get("boxscore", {}).get("players", []):
        team_info = team_group.get("team", {})
        team_id = team_info.get("id")
        team_name = team_info.get("displayName")
        abbreviation = team_info.get("abbreviation")

        for stat_group in team_group.get("statistics", []):
            labels = stat_group.get("labels", [])

            for entry in stat_group.get("athletes", []):
                athlete = entry.get("athlete", {})
                values = entry.get("stats", [])

                player = {
                    "game_id": game_id,
                    "season": season,
                    "team_id": team_id,
                    "team": team_name,
                    "team_abbreviation": abbreviation,
                    "player_id": athlete.get("id"),
                    "player_name": athlete.get("displayName"),
                    "short_name": athlete.get("shortName"),
                    "position": athlete.get("position", {}).get("abbreviation"),
                    "jersey": athlete.get("jersey"),
                    "headshot": athlete.get("headshot", {}).get("href"),
                    "starter": entry.get("starter"),
                    "did_not_play": entry.get("didNotPlay"),
                    "dnp_reason": entry.get("reason"),
                    "ejected": entry.get("ejected"),
                }

                for label, value in zip(labels, values):
                    player[label] = value

                players.append(player)

    for team_group in data.get("boxscore", {}).get("teams", []):
        team_info = team_group.get("team", {})

        for stat in team_group.get("statistics", []):
            teams.append({
                "game_id": game_id,
                "season": season,
                "team_id": team_info.get("id"),
                "team": team_info.get("displayName"),
                "team_abbreviation": team_info.get("abbreviation"),
                "category": "Team Game Stats",
                "stat_name": stat.get("name"),
                "stat_label": stat.get("label"),
                "stat_value": stat.get("value"),
                "stat_display_value": stat.get("displayValue"),
            })

    return game, players, teams


def main():
    for season in SEASONS:
        season_name = f"{season - 1}-{str(season)[-2:]}"
        source_dir = Path("raw") / "game_summaries" / str(season)

        if not source_dir.exists():
            print(f"Missing source directory: {source_dir}")
            continue

        games = []
        players = []
        teams = []
        errors = []

        files = sorted(source_dir.glob("*.json"))

        print(f"\nPROCESSING {season_name}")
        print(f"Summary files found: {len(files)}")

        for index, file_path in enumerate(files, start=1):
            try:
                game, game_players, game_teams = process_game(file_path, season)
                games.append(game)
                players.extend(game_players)
                teams.extend(game_teams)
            except Exception as error:
                errors.append({
                    "file": file_path.name,
                    "error": str(error)
                })

            if index % 100 == 0:
                print(f"Processed {index}/{len(files)}")

        output_dir = Path("exports") / str(season)
        output_dir.mkdir(parents=True, exist_ok=True)

        datasets = {
            "games": games,
            "player_box_scores": players,
            "team_game_stats": teams,
            "processing_errors": errors,
        }

        for name, records in datasets.items():
            output_file = output_dir / f"{name}.json"
            with open(output_file, "w") as f:
                json.dump(records, f, indent=2)

        print(f"Games processed: {len(games)}")
        print(f"Player records: {len(players)}")
        print(f"Team stat records: {len(teams)}")
        print(f"Errors: {len(errors)}")
        print(f"Saved to: {output_dir}")


if __name__ == "__main__":
    main()
