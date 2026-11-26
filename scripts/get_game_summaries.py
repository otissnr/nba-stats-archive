import requests
import json
import time
from pathlib import Path

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"

SEASONS = range(2021, 2028)


def collect_summaries():
    total = 0
    completed = 0
    skipped = 0
    failed = []

    for season in SEASONS:
        season_name = f"{season - 1}-{str(season)[-2:]}"

        games_file = Path("raw") / "games" / f"{season}.json"

        with open(games_file, "r") as file:
            games = json.load(file)

        output_dir = Path("raw") / "game_summaries" / str(season)
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'=' * 55}")
        print(f"SEASON: {season_name}")
        print(f"Games in index: {len(games)}")
        print(f"{'=' * 55}")

        total += len(games)

        for index, game in enumerate(games, start=1):
            game_id = game.get("id")

            if not game_id:
                continue

            output_file = output_dir / f"{game_id}.json"

            # Skip summaries already downloaded
            if output_file.exists():
                skipped += 1
                continue

            try:
                response = requests.get(
                    BASE_URL,
                    params={"event": game_id},
                    timeout=30
                )

                response.raise_for_status()

                data = response.json()

                # Confirm that ESPN returned the expected game data
                if not data.get("header") or not data.get("boxscore"):
                    raise ValueError("Missing game header or boxscore")

                with open(output_file, "w") as file:
                    json.dump(data, file, indent=2)

                completed += 1

                print(
                    f"[{index}/{len(games)}] "
                    f"{game_id} | Downloaded"
                )

            except Exception as error:
                failed.append({
                    "season": season_name,
                    "game_id": game_id,
                    "error": str(error)
                })

                print(
                    f"[{index}/{len(games)}] "
                    f"{game_id} | FAILED: {error}"
                )

            time.sleep(0.2)

        print(f"\nSeason {season_name} complete.")

    # Save failure log
    failure_file = Path("logs") / "game_summary_failures.json"

    with open(failure_file, "w") as file:
        json.dump(failed, file, indent=2)

    print("\n" + "=" * 55)
    print("GAME SUMMARY COLLECTION COMPLETE")
    print("=" * 55)
    print(f"Games in index: {total}")
    print(f"New summaries downloaded: {completed}")
    print(f"Existing summaries skipped: {skipped}")
    print(f"Failed downloads: {len(failed)}")
    print(f"Failure log: {failure_file}")


if __name__ == "__main__":
    collect_summaries()
