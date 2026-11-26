import json
import time
import requests
from pathlib import Path

PLAYER_FILE = Path("exports/players.json")
OUTPUT_DIR = Path("raw/player_stats")
FAILURE_FILE = Path("logs/player_stats_failures.json")

BASE_URL = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes"

DELAY = 0.25
MAX_RETRIES = 4


def download_player_stats(session, player_id, season):
    url = f"{BASE_URL}/{player_id}/stats"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(
                url,
                params={
                    "season": season,
                    "seasontype": 2
                },
                timeout=30
            )

            response.raise_for_status()
            data = response.json()

            if not data.get("categories"):
                raise ValueError("No statistics categories returned")

            return data

        except Exception as error:
            if attempt == MAX_RETRIES:
                raise error

            time.sleep(attempt * 2)


def main():
    if not PLAYER_FILE.exists():
        print("Player directory not found:", PLAYER_FILE)
        return

    with open(PLAYER_FILE) as f:
        players = json.load(f)

    failures = []
    downloaded = 0
    skipped = 0
    total = sum(len(p.get("seasons", [])) for p in players)

    print("=" * 65)
    print("NBA PLAYER SEASON STATISTICS DOWNLOADER")
    print("=" * 65)
    print("Players:", len(players))
    print("Player-season records:", total)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0"
    })

    completed = 0

    for player in players:
        player_id = str(player["player_id"])
        player_name = player.get("name", "Unknown")

        for season in player.get("seasons", []):
            completed += 1

            output_dir = OUTPUT_DIR / str(season)
            output_dir.mkdir(parents=True, exist_ok=True)

            output_file = output_dir / f"{player_id}.json"

            if output_file.exists():
                skipped += 1
                continue

            try:
                data = download_player_stats(
                    session,
                    player_id,
                    season
                )

                with open(output_file, "w") as f:
                    json.dump(data, f, indent=2)

                downloaded += 1

                print(
                    f"[{completed}/{total}] "
                    f"{player_name} | {season} | Downloaded"
                )

            except Exception as error:
                failures.append({
                    "player_id": player_id,
                    "player_name": player_name,
                    "season": season,
                    "error": str(error)
                })

                print(
                    f"[{completed}/{total}] "
                    f"{player_name} | {season} | FAILED"
                )

            time.sleep(DELAY)

    FAILURE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(FAILURE_FILE, "w") as f:
        json.dump(failures, f, indent=2)

    print("\n" + "=" * 65)
    print("PLAYER STATISTICS COLLECTION COMPLETE")
    print("=" * 65)
    print("Downloaded:", downloaded)
    print("Already existed:", skipped)
    print("Failed:", len(failures))
    print("Failure log:", FAILURE_FILE)


if __name__ == "__main__":
    main()
