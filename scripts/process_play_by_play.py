import json
import csv
import glob
import os

SEASONS = range(2021, 2028)

INPUT_DIR = "raw/game_summaries"
OUTPUT_DIR = "exports"


def process_game(file_path, season):
    records = []

    with open(file_path) as f:
        data = json.load(f)

    game_id = os.path.splitext(
        os.path.basename(file_path)
    )[0]

    header = data.get("header", {})
    competition = header.get("competitions", [{}])[0]

    competitors = competition.get("competitors", [])

    home_team = {}
    away_team = {}

    for competitor in competitors:
        if competitor.get("homeAway") == "home":
            home_team = competitor.get("team", {})
        elif competitor.get("homeAway") == "away":
            away_team = competitor.get("team", {})

    for play in data.get("plays", []):
        period = play.get("period", {})
        clock = play.get("clock", {})
        event_type = play.get("type", {})
        team = play.get("team", {})
        coordinate = play.get("coordinate", {})

        participants = []

        for participant in play.get("participants", []):
            athlete = participant.get("athlete", {})
            athlete_id = athlete.get("id")

            if athlete_id:
                participants.append(str(athlete_id))

        records.append({
            "game_id": game_id,
            "season": season,
            "event_id": play.get("id"),
            "sequence_number": play.get("sequenceNumber"),
            "period_number": period.get("number"),
            "period_name": period.get("displayValue"),
            "clock": clock.get("displayValue"),
            "event_type_id": event_type.get("id"),
            "event_type": event_type.get("text"),
            "description": play.get("text"),
            "short_description": play.get("shortDescription"),
            "home_team": home_team.get("displayName"),
            "away_team": away_team.get("displayName"),
            "home_team_id": home_team.get("id"),
            "away_team_id": away_team.get("id"),
            "event_team_id": team.get("id"),
            "home_score": play.get("homeScore"),
            "away_score": play.get("awayScore"),
            "scoring_play": play.get("scoringPlay"),
            "score_value": play.get("scoreValue"),
            "points_attempted": play.get("pointsAttempted"),
            "shooting_play": play.get("shootingPlay"),
            "participant_ids": "|".join(participants),
            "wallclock": play.get("wallclock"),
            "coordinate_x": coordinate.get("x"),
            "coordinate_y": coordinate.get("y"),
        })

    return records


def main():
    print("\nPROCESSING NBA PLAY-BY-PLAY DATA")
    print("=" * 60)

    total_records = 0
    errors = []

    for season in SEASONS:
        season_dir = os.path.join(INPUT_DIR, str(season))
        files = glob.glob(os.path.join(season_dir, "*.json"))

        print(f"\nSeason {season - 1}-{str(season)[-2:]}")

        season_records = []
        processed = 0

        for file_path in files:
            try:
                records = process_game(file_path, season)
                season_records.extend(records)
                processed += 1

            except Exception as error:
                errors.append({
                    "season": season,
                    "file": file_path,
                    "error": str(error)
                })

        output_dir = os.path.join(OUTPUT_DIR, str(season))
        os.makedirs(output_dir, exist_ok=True)

        json_path = os.path.join(
            output_dir, "play_by_play.json"
        )

        csv_path = os.path.join(
            output_dir, "play_by_play.csv"
        )

        with open(json_path, "w") as f:
            json.dump(season_records, f)

        if season_records:
            columns = list(season_records[0].keys())

            with open(csv_path, "w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=columns,
                    extrasaction="ignore"
                )

                writer.writeheader()
                writer.writerows(season_records)

        total_records += len(season_records)

        print(f"Games processed: {processed:,}")
        print(f"Play-by-play events: {len(season_records):,}")

        del season_records

    error_path = "logs/play_by_play_processing_errors.json"

    with open(error_path, "w") as f:
        json.dump(errors, f, indent=2)

    print("\n" + "=" * 60)
    print("PLAY-BY-PLAY PROCESSING COMPLETE")
    print(f"Total events: {total_records:,}")
    print(f"Processing errors: {len(errors)}")
    print(f"Error log: {error_path}")


if __name__ == "__main__":
    main()
