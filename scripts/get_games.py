import requests
import json
import time
from pathlib import Path

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"

# ESPN season year: 2021 = 2020-21 season
SEASONS = range(2021, 2028)


def get_season_calendar(season):
    response = requests.get(
        BASE_URL,
        params={"dates": str(season), "limit": 1000},
        timeout=30
    )
    response.raise_for_status()

    data = response.json()
    league = data["leagues"][0]

    return league["calendar"]


def collect_games():
    all_games = {}
    failures = []

    for season in SEASONS:
        season_name = f"{season - 1}-{str(season)[-2:]}"

        print(f"\n{'=' * 50}")
        print(f"SEASON: {season_name}")
        print(f"{'=' * 50}")

        try:
            calendar = get_season_calendar(season)
            print(f"Calendar dates found: {len(calendar)}")

        except Exception as error:
            print(f"FAILED to retrieve calendar: {error}")
            failures.append({
                "season": season_name,
                "date": None,
                "error": str(error)
            })
            continue

        season_games = {}

        for index, calendar_date in enumerate(calendar, start=1):
            date = calendar_date[:10].replace("-", "")

            try:
                response = requests.get(
                    BASE_URL,
                    params={"dates": date, "limit": 1000},
                    timeout=30
                )
                response.raise_for_status()

                data = response.json()

                for event in data.get("events", []):
                    game_id = event.get("id")

                    if game_id:
                        season_games[game_id] = event

                print(
                    f"[{index}/{len(calendar)}] "
                    f"{date} | "
                    f"Games found: {len(data.get('events', []))} | "
                    f"Unique season games: {len(season_games)}"
                )

            except Exception as error:
                print(f"FAILED: {date} | {error}")
                failures.append({
                    "season": season_name,
                    "date": date,
                    "error": str(error)
                })

            time.sleep(0.2)

        output_dir = Path("raw") / "games"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"{season}.json"

        with open(output_file, "w") as file:
            json.dump(
                list(season_games.values()),
                file,
                indent=2
            )

        all_games.update(season_games)

        print(f"\nSEASON COMPLETE: {season_name}")
        print(f"Unique games collected: {len(season_games)}")
        print(f"Saved to: {output_file}")

    # Save combined game index
    output_file = Path("raw") / "games" / "all_games.json"

    with open(output_file, "w") as file:
        json.dump(
            list(all_games.values()),
            file,
            indent=2
        )

    # Save failures for later retries
    failure_file = Path("logs") / "game_collection_failures.json"

    with open(failure_file, "w") as file:
        json.dump(failures, file, indent=2)

    print("\n" + "=" * 50)
    print("GAME COLLECTION COMPLETE")
    print("=" * 50)
    print(f"Total unique games: {len(all_games)}")
    print(f"Failed requests: {len(failures)}")
    print(f"Combined index: {output_file}")
    print(f"Failure log: {failure_file}")


if __name__ == "__main__":
    collect_games()
