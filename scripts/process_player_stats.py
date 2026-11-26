import json
import csv
import glob
import os
from collections import defaultdict

SEASONS = range(2021, 2028)

INPUT_DIR = "raw/player_stats"
OUTPUT_DIR = "exports"

CATEGORY_MAP = {
    "Regular Season Averages": "averages",
    "Regular Season Totals": "totals",
    "Regular Season Misc Totals": "advanced"
}


def load_player_directory():
    with open("exports/players.json") as f:
        players = json.load(f)

    return {
        str(player["player_id"]): player
        for player in players
    }


def extract_category(category, player, season):
    records = []

    names = category.get("names", [])
    labels = category.get("labels", [])

    for entry in category.get("statistics", []):
        entry_season = entry.get("season", {})

        if entry_season.get("year") != season:
            continue

        stats = entry.get("stats", [])

        record = {
            "player_id": player["player_id"],
            "player_name": player["player_name"],
            "season": season,
            "season_name": entry_season.get("displayName"),
            "team_id": entry.get("teamId"),
            "team_slug": entry.get("teamSlug"),
            "position": entry.get("position"),
        }

        for index, value in enumerate(stats):
            if index < len(names):
                record[names[index]] = value

        records.append(record)

    return records


def main():
    print("\nPROCESSING PLAYER SEASON STATISTICS")
    print("=" * 55)

    players = load_player_directory()

    all_records = defaultdict(list)
    errors = []

    for season in SEASONS:
        season_dir = os.path.join(INPUT_DIR, str(season))
        files = glob.glob(os.path.join(season_dir, "*.json"))

        print(f"\nSeason {season - 1}-{str(season)[-2:]}")

        processed = 0

        for file in files:
            player_id = os.path.splitext(
                os.path.basename(file)
            )[0]

            player_info = players.get(player_id, {})

            try:
                with open(file) as f:
                    data = json.load(f)

                player = {
                    "player_id": player_id,
                    "player_name": player_info.get(
                        "name", "Unknown"
                    )
                }

                for category in data.get("categories", []):
                    category_name = category.get("displayName")
                    output_name = CATEGORY_MAP.get(category_name)

                    if not output_name:
                        continue

                    records = extract_category(
                        category, player, season
                    )

                    all_records[(season, output_name)].extend(records)

                processed += 1

            except Exception as error:
                errors.append({
                    "season": season,
                    "player_id": player_id,
                    "file": file,
                    "error": str(error)
                })

        print(f"Player files processed: {processed:,}")

    for season in SEASONS:
        season_dir = os.path.join(OUTPUT_DIR, str(season))
        os.makedirs(season_dir, exist_ok=True)

        for category in ["averages", "totals", "advanced"]:
            records = all_records[(season, category)]

            json_path = os.path.join(
                season_dir,
                f"player_{category}.json"
            )

            csv_path = os.path.join(
                season_dir,
                f"player_{category}.csv"
            )

            with open(json_path, "w") as f:
                json.dump(records, f, indent=2)

            if records:
                columns = list(dict.fromkeys(
                    key
                    for record in records
                    for key in record
                ))

                with open(csv_path, "w", newline="") as f:
                    writer = csv.DictWriter(
                        f,
                        fieldnames=columns,
                        extrasaction="ignore"
                    )

                    writer.writeheader()
                    writer.writerows(records)

            print(
                f"{season} {category}: {len(records):,} records"
            )

    error_path = "logs/player_stats_processing_errors.json"

    with open(error_path, "w") as f:
        json.dump(errors, f, indent=2)

    print("\n" + "=" * 55)
    print("PLAYER STATISTICS PROCESSING COMPLETE")
    print("Processing errors:", len(errors))
    print("Error log:", error_path)


if __name__ == "__main__":
    main()
