import json
import csv
import glob
import os

SEASONS = range(2021, 2028)

INPUT_DIR = "raw/team_stats"
OUTPUT_DIR = "exports"


def process_team_file(file_path, season):
    records = []

    with open(file_path) as f:
        data = json.load(f)

    team = data.get("team", {})

    team_id = team.get("id")
    team_name = team.get("displayName")
    team_abbreviation = team.get("abbreviation")

    results = data.get("results", {})
    stats_data = results.get("stats", {})
    categories = stats_data.get("categories", [])

    for category in categories:
        category_name = category.get("displayName")

        for stat in category.get("stats", []):
            records.append({
                "season": season,
                "season_name": f"{season - 1}-{str(season)[-2:]}",
                "team_id": team_id,
                "team": team_name,
                "team_abbreviation": team_abbreviation,
                "category": category_name,
                "stat_name": stat.get("name"),
                "stat_label": stat.get("displayName"),
                "stat_abbreviation": stat.get("abbreviation"),
                "stat_value": stat.get("value"),
                "stat_display_value": stat.get("displayValue"),
                "per_game_value": stat.get("perGameValue"),
                "per_game_display_value": stat.get("perGameDisplayValue"),
            })

    return records


def main():
    print("\nPROCESSING TEAM SEASON STATISTICS")
    print("=" * 55)

    all_records = []
    errors = []

    for season in SEASONS:
        season_dir = os.path.join(INPUT_DIR, str(season))
        files = glob.glob(os.path.join(season_dir, "*.json"))

        print(f"\nSeason {season - 1}-{str(season)[-2:]}")

        processed = 0
        season_records = []

        for file_path in files:
            try:
                records = process_team_file(file_path, season)
                season_records.extend(records)
                processed += 1

            except Exception as error:
                errors.append({
                    "season": season,
                    "file": file_path,
                    "error": str(error)
                })

        all_records.extend(season_records)

        output_dir = os.path.join(OUTPUT_DIR, str(season))
        os.makedirs(output_dir, exist_ok=True)

        json_path = os.path.join(
            output_dir, "team_season_stats.json"
        )

        csv_path = os.path.join(
            output_dir, "team_season_stats.csv"
        )

        with open(json_path, "w") as f:
            json.dump(season_records, f, indent=2)

        if season_records:
            columns = list(dict.fromkeys(
                key
                for record in season_records
                for key in record
            ))

            with open(csv_path, "w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=columns,
                    extrasaction="ignore"
                )
                writer.writeheader()
                writer.writerows(season_records)

        print(f"Team files processed: {processed}")
        print(f"Statistics records: {len(season_records):,}")

    error_path = "logs/team_stats_processing_errors.json"

    with open(error_path, "w") as f:
        json.dump(errors, f, indent=2)

    print("\n" + "=" * 55)
    print("TEAM STATISTICS PROCESSING COMPLETE")
    print("Total records:", f"{len(all_records):,}")
    print("Processing errors:", len(errors))
    print("Error log:", error_path)


if __name__ == "__main__":
    main()
