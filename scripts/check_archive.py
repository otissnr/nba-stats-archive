import json
from pathlib import Path

SEASONS = range(2021, 2028)

def check_archive():
    total_games = 0
    total_found = 0
    total_missing = 0
    total_invalid = 0
    missing_records = []
    invalid_records = []

    print("=" * 60)
    print("NBA ARCHIVE INTEGRITY CHECK")
    print("=" * 60)

    for season in SEASONS:
        season_name = f"{season - 1}-{str(season)[-2:]}"
        index_file = Path("raw") / "games" / f"{season}.json"
        summary_dir = Path("raw") / "game_summaries" / str(season)

        if not index_file.exists():
            print(f"\n{season_name}: GAME INDEX MISSING")
            continue

        with open(index_file) as f:
            games = json.load(f)

        found = 0
        missing = 0
        invalid = 0

        for game in games:
            game_id = game.get("id")

            if not game_id:
                continue

            summary_file = summary_dir / f"{game_id}.json"

            if not summary_file.exists():
                missing += 1
                missing_records.append({
                    "season": season,
                    "game_id": game_id
                })
                continue

            try:
                with open(summary_file) as f:
                    data = json.load(f)

                if not data.get("header") or not data.get("boxscore"):
                    raise ValueError("Missing header or boxscore")

                found += 1

            except Exception as error:
                invalid += 1
                invalid_records.append({
                    "season": season,
                    "game_id": game_id,
                    "error": str(error)
                })

        total_games += len(games)
        total_found += found
        total_missing += missing
        total_invalid += invalid

        print(f"\nSEASON: {season_name}")
        print(f"Games in index: {len(games)}")
        print(f"Valid summaries: {found}")
        print(f"Missing summaries: {missing}")
        print(f"Invalid summaries: {invalid}")

    print("\n" + "=" * 60)
    print("OVERALL RESULTS")
    print("=" * 60)
    print(f"Games indexed: {total_games}")
    print(f"Valid summaries: {total_found}")
    print(f"Missing summaries: {total_missing}")
    print(f"Invalid summaries: {total_invalid}")

    report = {
        "games_indexed": total_games,
        "valid_summaries": total_found,
        "missing_summaries": total_missing,
        "invalid_summaries": total_invalid,
        "missing_games": missing_records,
        "invalid_games": invalid_records
    }

    output_dir = Path("logs")
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / "archive_integrity_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print("\nReport saved to logs/archive_integrity_report.json")


if __name__ == "__main__":
    check_archive()
