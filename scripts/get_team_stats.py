import requests
import json
import time
from pathlib import Path

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"

SEASONS = range(2021, 2028)

def get_team_stats():
    teams_file = Path("raw/nba_teams.json")

    with open(teams_file, "r") as file:
        teams = json.load(file)

    total = len(teams) * len(SEASONS)
    completed = 0
    failed = []

    print(f"Collecting statistics for {len(teams)} teams")
    print(f"Seasons: 2020-21 through 2026-27")
    print(f"Total requests planned: {total}\n")

    for team in teams:
        team_id = team["id"]
        abbreviation = team["abbreviation"]
        team_name = team["name"]

        for season in SEASONS:
            season_name = f"{season - 1}-{str(season)[-2:]}"

            url = f"{BASE_URL}/{team_id}/statistics"

            try:
                response = requests.get(
                    url,
                    params={
                        "season": season,
                        "seasontype": 2
                    },
                    timeout=30
                )

                response.raise_for_status()
                data = response.json()

                output_dir = Path("raw") / "team_stats" / str(season)
                output_dir.mkdir(parents=True, exist_ok=True)

                output_file = output_dir / f"{abbreviation}.json"

                with open(output_file, "w") as file:
                    json.dump(data, file, indent=2)

                completed += 1

                print(
                    f"[{completed}/{total}] "
                    f"{team_name} | {season_name} | Saved"
                )

            except Exception as error:
                failed.append({
                    "team": team_name,
                    "season": season_name,
                    "error": str(error)
                })

                print(
                    f"FAILED: {team_name} | {season_name} | {error}"
                )

            time.sleep(0.3)

    print("\nCOLLECTION COMPLETE")
    print(f"Successful: {completed}")
    print(f"Failed: {len(failed)}")

    if failed:
        failure_file = Path("logs") / "team_stats_failures.json"

        with open(failure_file, "w") as file:
            json.dump(failed, file, indent=2)

        print(f"Failure details saved to: {failure_file}")


if __name__ == "__main__":
    get_team_stats()
