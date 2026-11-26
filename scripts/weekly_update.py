
import json
import csv
import time
import shutil
import argparse
import subprocess
import sys

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


# ============================================================
# NBA WEEKLY UPDATE CONFIGURATION
# ============================================================

SEASON = 2027
SEASON_NAME = "2026-27"

BASE_DIR = Path(__file__).resolve().parent.parent

RAW_DIR = BASE_DIR / "raw"
EXPORT_DIR = BASE_DIR / "exports"
LOG_DIR = BASE_DIR / "logs"
WEBSITE_DIR = BASE_DIR / "website"

GAME_INDEX = RAW_DIR / "games" / f"{SEASON}.json"
ALL_GAMES_INDEX = RAW_DIR / "games" / "all_games.json"

SUMMARY_DIR = RAW_DIR / "game_summaries" / str(SEASON)

WORKBOOK = (
    EXPORT_DIR / "workbooks" /
    f"NBA_{SEASON_NAME}.xlsx"
)

WEBSITE_WORKBOOK = (
    WEBSITE_DIR / "downloads" /
    f"NBA_{SEASON_NAME}.xlsx"
)

DASHBOARD_DIR = WEBSITE_DIR / "data"
DASHBOARD_FILE = DASHBOARD_DIR / "weekly_dashboard.json"

RUN_LOG = LOG_DIR / "weekly_update_log.json"

ESPN_SCOREBOARD = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/basketball/nba/scoreboard"
)

ESPN_SUMMARY = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/basketball/nba/summary"
)

ESPN_PLAYER_STATS = (
    "https://site.web.api.espn.com/apis/common/v3/"
    "sports/basketball/nba/athletes"
)

ESPN_TEAM_STATS = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/basketball/nba/teams"
)

LOCAL_TIMEZONE = ZoneInfo("Australia/Sydney")

# Check 14 days for late or missed game updates.
GAME_LOOKBACK_DAYS = 14

# Dashboard displays the latest seven calendar days.
DASHBOARD_DAYS = 7

REQUEST_DELAY = 0.2
REQUEST_TIMEOUT = 30


# ============================================================
# LOGGING AND FILE HELPERS
# ============================================================

def log(message):
    timestamp = datetime.now(LOCAL_TIMEZONE).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    print(f"[{timestamp}] {message}")


def load_json(path, default=None):
    path = Path(path)

    if not path.exists():
        return default

    with open(path, "r") as file:
        return json.load(file)


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_file = path.with_suffix(
        path.suffix + ".tmp"
    )

    with open(temporary_file, "w") as file:
        json.dump(data, file, indent=2)

    temporary_file.replace(path)


def initialise_directories():
    directories = [
        LOG_DIR,
        SUMMARY_DIR,
        DASHBOARD_DIR,
        EXPORT_DIR / str(SEASON),
        EXPORT_DIR / "workbooks",
        WEBSITE_DIR / "downloads",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def reporting_dates():
    now = datetime.now(LOCAL_TIMEZONE)

    dashboard_start = (
        now.date() - timedelta(days=DASHBOARD_DAYS - 1)
    )

    collection_start = (
        now.date() - timedelta(days=GAME_LOOKBACK_DAYS)
    )

    return {
        "run_time": now.isoformat(),
        "run_date": now.date().isoformat(),
        "dashboard_start": dashboard_start.isoformat(),
        "dashboard_end": now.date().isoformat(),
        "collection_start": collection_start.isoformat(),
    }


def append_run_log(entry):
    history = load_json(RUN_LOG, [])

    history.append(entry)

    save_json(RUN_LOG, history)


# ============================================================
# ESPN CONNECTION AND INCREMENTAL GAME COLLECTION
# ============================================================

def espn_get(url, params=None):
    response = requests.get(
        url,
        params=params,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    return response.json()



def collect_recent_games():
    log("Checking ESPN for recent NBA games")

    existing_games = load_json(GAME_INDEX, [])

    games_by_id = {
        str(game["id"]): game
        for game in existing_games
        if game.get("id")
    }

    # ESPN game dates follow US/UTC calendar dates.
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=GAME_LOOKBACK_DAYS)

    failures = []
    dates_checked = 0
    current_date = start_date

    while current_date <= today:
        date_string = current_date.strftime("%Y%m%d")

        try:
            data = espn_get(
                ESPN_SCOREBOARD,
                params={
                    "dates": date_string,
                    "limit": 1000
                }
            )

            events = data.get("events", [])

            for event in events:
                game_id = event.get("id")
                if game_id:
                    games_by_id[str(game_id)] = event

            log(f"{date_string}: {len(events)} games found")

        except Exception as error:
            failures.append({
                "date": date_string,
                "error": str(error)
            })
            log(f"FAILED {date_string}: {error}")

        dates_checked += 1
        current_date += timedelta(days=1)
        time.sleep(REQUEST_DELAY)

    updated_games = sorted(
        games_by_id.values(),
        key=lambda game: game.get("date", "")
    )

    save_json(GAME_INDEX, updated_games)

    # Merge into the complete archive by ID.
    all_games = load_json(ALL_GAMES_INDEX, [])

    combined = {
        str(game["id"]): game
        for game in all_games
        if game.get("id")
    }

    for game in updated_games:
        combined[str(game["id"])] = game

    save_json(
        ALL_GAMES_INDEX,
        sorted(
            combined.values(),
            key=lambda game: game.get("date", "")
        )
    )

    log(f"Dates checked: {dates_checked}")
    log(f"Current season games indexed: {len(updated_games)}")
    log(f"Collection failures: {len(failures)}")

    return failures


# ============================================================
# GAME SUMMARY AND BOX SCORE COLLECTION
# ============================================================

def collect_recent_summaries():
    log("Collecting recent completed game summaries")

    games = load_json(GAME_INDEX, [])

    cutoff = (
        datetime.now(LOCAL_TIMEZONE).date()
        - timedelta(days=GAME_LOOKBACK_DAYS)
    )

    downloaded = 0
    refreshed = 0
    skipped = 0
    failures = []

    session = requests.Session()

    for game in games:
        game_id = game.get("id")

        if not game_id:
            continue

        status = (
            game.get("status", {})
            .get("type", {})
        )

        if not status.get("completed", False):
            skipped += 1
            continue

        game_date = game.get("date")

        if not game_date:
            continue

        try:
            game_day = (
                datetime.fromisoformat(
                    game_date.replace("Z", "+00:00")
                )
                .astimezone(LOCAL_TIMEZONE)
                .date()
            )
        except (ValueError, TypeError):
            continue

        output_file = SUMMARY_DIR / f"{game_id}.json"
        existed_before = output_file.exists()

        # Only refresh recent games. Older existing summaries

        # remain untouched.
        is_recent = game_day >= cutoff

        if output_file.exists() and not is_recent:
            skipped += 1
            continue

        try:
            response = session.get(
                ESPN_SUMMARY,
                params={"event": game_id},
                timeout=REQUEST_TIMEOUT
            )

            response.raise_for_status()
            data = response.json()

            if not data.get("header"):
                raise ValueError("Missing game header")

            if not data.get("boxscore"):
                raise ValueError("Missing box score")

            # Write to a temporary file first. The previous
            # valid summary remains safe if writing fails.
            temporary_file = output_file.with_suffix(
                ".json.tmp"
            )

            with open(temporary_file, "w") as file:
                json.dump(data, file, indent=2)

            temporary_file.replace(output_file)

            if existed_before:
                refreshed += 1
            else:
                downloaded += 1

            log(f"Game {game_id}: summary saved")

        except Exception as error:
            failures.append({
                "game_id": game_id,
                "error": str(error)
            })

            log(f"Game {game_id}: FAILED: {error}")

        time.sleep(REQUEST_DELAY)

    session.close()

    log(f"New summaries: {downloaded}")
    log(f"Recent summaries refreshed: {refreshed}")
    log(f"Games skipped: {skipped}")
    log(f"Summary failures: {len(failures)}")

    return failures


# ============================================================
# CURRENT SEASON GAME AND BOX SCORE PROCESSING
# ============================================================

def process_current_season():
    log("Processing current-season game summaries")

    # Reuse the existing, tested parser.
    sys.path.insert(0, str(BASE_DIR / "scripts"))

    from process_game_summaries import process_game

    games = []
    players = []
    teams = []
    errors = []

    summary_files = sorted(SUMMARY_DIR.glob("*.json"))

    for index, file_path in enumerate(summary_files, start=1):
        try:
            game, game_players, game_teams = process_game(
                file_path,
                SEASON
            )

            games.append(game)
            players.extend(game_players)
            teams.extend(game_teams)

        except Exception as error:
            errors.append({
                "file": str(file_path),
                "error": str(error)
            })

        if index % 100 == 0:
            log(f"Processed {index:,} game summaries")

    output_dir = EXPORT_DIR / str(SEASON)
    output_dir.mkdir(parents=True, exist_ok=True)

    save_json(output_dir / "games.json", games)
    save_json(output_dir / "player_box_scores.json", players)
    save_json(output_dir / "team_game_stats.json", teams)
    save_json(output_dir / "processing_errors.json", errors)

    log(f"Games processed: {len(games):,}")
    log(f"Player box scores: {len(players):,}")
    log(f"Team game-stat records: {len(teams):,}")
    log(f"Processing errors: {len(errors)}")

    if errors:
        raise RuntimeError(
            "Game processing errors detected. "
            "Workbook generation and publishing stopped."
        )


# ============================================================
# CURRENT SEASON PLAY-BY-PLAY PROCESSING
# ============================================================

def process_current_season_play_by_play():
    log("Processing current-season play-by-play data")

    sys.path.insert(0, str(BASE_DIR / "scripts"))

    from process_play_by_play import process_game

    records = []
    errors = []

    summary_files = sorted(SUMMARY_DIR.glob("*.json"))

    for index, file_path in enumerate(summary_files, start=1):
        try:
            game_records = process_game(
                str(file_path),
                SEASON
            )
            records.extend(game_records)

        except Exception as error:
            errors.append({
                "file": str(file_path),
                "error": str(error)
            })

        if index % 100 == 0:
            log(f"Play-by-play: processed {index:,} summaries")

    output_dir = EXPORT_DIR / str(SEASON)
    output_dir.mkdir(parents=True, exist_ok=True)

    save_json(output_dir / "play_by_play.json", records)

    csv_path = output_dir / "play_by_play.csv"

    if records:
        with open(csv_path, "w", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=list(records[0].keys()),
                extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows(records)

    save_json(
        LOG_DIR / "weekly_play_by_play_errors.json",
        errors
    )

    log(f"Play-by-play events: {len(records):,}")
    log(f"Play-by-play processing errors: {len(errors)}")

    if errors:
        raise RuntimeError(
            "Play-by-play processing errors detected. "
            "Publishing stopped."
        )


# ============================================================
# CURRENT SEASON PLAYER STATISTICS PROCESSING
# ============================================================

def process_current_season_player_stats():
    log("Processing current-season player statistics")

    sys.path.insert(0, str(BASE_DIR / "scripts"))

    from process_player_stats import (
        load_player_directory,
        extract_category,
        CATEGORY_MAP
    )

    player_directory = load_player_directory()

    box_scores = load_json(
        EXPORT_DIR / str(SEASON) / "player_box_scores.json",
        []
    )

    player_ids = sorted({
        str(player["player_id"])
        for player in box_scores
        if player.get("player_id")
    })

    output_records = {
        "averages": [],
        "totals": [],
        "advanced": []
    }

    errors = []

    for index, player_id in enumerate(player_ids, start=1):
        player_file = (
            RAW_DIR / "player_stats" /
            str(SEASON) / f"{player_id}.json"
        )

        if not player_file.exists():
            errors.append({
                "player_id": player_id,
                "error": "Player statistics file missing"
            })
            continue

        player_info = player_directory.get(player_id, {})

        player = {
            "player_id": player_id,
            "player_name": player_info.get("name", "Unknown")
        }

        try:
            data = load_json(player_file, {})

            for category in data.get("categories", []):
                category_name = category.get("displayName")
                output_name = CATEGORY_MAP.get(category_name)

                if not output_name:
                    continue

                records = extract_category(
                    category,
                    player,
                    SEASON
                )

                output_records[output_name].extend(records)

        except Exception as error:
            errors.append({
                "player_id": player_id,
                "error": str(error)
            })

        if index % 100 == 0:
            log(f"Player statistics processed: {index:,}")

    output_dir = EXPORT_DIR / str(SEASON)

    for category, records in output_records.items():
        save_json(
            output_dir / f"player_{category}.json",
            records
        )

        csv_path = output_dir / f"player_{category}.csv"

        if records:
            columns = list(dict.fromkeys(
                key for record in records for key in record
            ))

            with open(csv_path, "w", newline="") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=columns,
                    extrasaction="ignore"
                )
                writer.writeheader()
                writer.writerows(records)

        log(f"Player {category}: {len(records):,} records")

    save_json(
        LOG_DIR / "weekly_player_stats_errors.json",
        errors
    )

    log(f"Player statistics processing errors: {len(errors)}")


# ============================================================
# CURRENT SEASON TEAM STATISTICS PROCESSING
# ============================================================

def process_current_season_team_stats():
    log("Processing current-season team statistics")

    sys.path.insert(0, str(BASE_DIR / "scripts"))

    from process_team_stats import process_team_file

    input_dir = RAW_DIR / "team_stats" / str(SEASON)

    output_dir = EXPORT_DIR / str(SEASON)
    output_dir.mkdir(parents=True, exist_ok=True)

    records = []
    errors = []

    team_files = sorted(input_dir.glob("*.json"))

    for file_path in team_files:
        try:
            team_records = process_team_file(
                str(file_path),
                SEASON
            )
            records.extend(team_records)

        except Exception as error:
            errors.append({
                "file": str(file_path),
                "error": str(error)
            })

    save_json(
        output_dir / "team_season_stats.json",
        records
    )

    csv_path = output_dir / "team_season_stats.csv"

    if records:
        columns = list(dict.fromkeys(
            key for record in records for key in record
        ))

        with open(csv_path, "w", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=columns,
                extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows(records)

    save_json(
        LOG_DIR / "weekly_team_stats_errors.json",
        errors
    )

    log(f"Team files processed: {len(team_files)}")
    log(f"Team statistics records: {len(records):,}")
    log(f"Team processing errors: {len(errors)}")

    if errors:
        raise RuntimeError(
            "Team statistics processing errors detected. "
            "Publishing stopped."
        )


# ============================================================
# CURRENT SEASON PLAYER STATISTICS COLLECTION
# ============================================================

def collect_current_season_player_stats():
    log("Downloading current-season player statistics")

    sys.path.insert(0, str(BASE_DIR / "scripts"))

    from get_player_stats import download_player_stats

    box_scores = load_json(
        EXPORT_DIR / str(SEASON) / "player_box_scores.json",
        []
    )

    player_directory = load_json(
        EXPORT_DIR / "players.json",
        []
    )

    player_names = {
        str(player["player_id"]): player.get("name", "Unknown")
        for player in player_directory
    }
    raw_games = load_json(GAME_INDEX, [])

    regular_season_ids = {
        str(game["id"])
        for game in raw_games
        if game.get("id")
        and game.get("season", {}).get("type") == 2
    }

    player_ids = sorted({
        str(player["player_id"])
        for player in box_scores
        if player.get("player_id")
        and str(player.get("game_id")) in regular_season_ids
    })

    output_dir = RAW_DIR / "player_stats" / str(SEASON)
    output_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0"
    })

    downloaded = 0
    failures = []

    for index, player_id in enumerate(player_ids, start=1):
        output_file = output_dir / f"{player_id}.json"

        try:
            data = download_player_stats(
                session,
                player_id,
                SEASON
            )

            temporary_file = output_file.with_suffix(".json.tmp")

            with open(temporary_file, "w") as file:
                json.dump(data, file, indent=2)

            temporary_file.replace(output_file)

            downloaded += 1

        except Exception as error:
            failures.append({
                "player_id": player_id,
                "player_name": player_names.get(player_id, "Unknown"),
                "error": str(error)
            })

        if index % 50 == 0:
            log(
                f"Player statistics downloaded: "
                f"{index:,}/{len(player_ids):,}"
            )

        time.sleep(REQUEST_DELAY)

    session.close()

    save_json(
        LOG_DIR / "weekly_player_download_failures.json",
        failures
    )

    log(f"Players refreshed: {downloaded:,}")
    log(f"Player download failures: {len(failures)}")

    return failures


# ============================================================
# CURRENT SEASON TEAM STATISTICS COLLECTION
# ============================================================

def collect_current_season_team_stats():
    log("Downloading current-season team statistics")

    teams = load_json(RAW_DIR / "nba_teams.json", [])

    output_dir = RAW_DIR / "team_stats" / str(SEASON)
    output_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0"
    })

    downloaded = 0
    failures = []

    for team in teams:
        team_id = team["id"]
        abbreviation = team["abbreviation"]
        team_name = team["name"]

        url = f"{ESPN_TEAM_STATS}/{team_id}/statistics"

        try:
            response = session.get(
                url,
                params={
                    "season": SEASON,
                    "seasontype": 2
                },
                timeout=REQUEST_TIMEOUT
            )

            response.raise_for_status()
            data = response.json()

            if not data.get("team") or not data.get("results"):
                raise ValueError("Incomplete team statistics response")

            output_file = output_dir / f"{abbreviation}.json"
            temporary_file = output_file.with_suffix(".json.tmp")

            with open(temporary_file, "w") as file:
                json.dump(data, file, indent=2)

            temporary_file.replace(output_file)

            downloaded += 1
            log(f"{team_name}: statistics refreshed")

        except Exception as error:
            failures.append({
                "team": team_name,
                "error": str(error)
            })

            log(f"{team_name}: FAILED: {error}")

        time.sleep(REQUEST_DELAY)

    session.close()

    save_json(
        LOG_DIR / "weekly_team_download_failures.json",
        failures
    )

    log(f"Teams refreshed: {downloaded}")
    log(f"Team download failures: {len(failures)}")

    return failures


# ============================================================
# WEEKLY DASHBOARD GENERATION
# ============================================================

def number(value):
    try:
        return float(str(value).replace(",", "").replace("+", ""))
    except (ValueError, TypeError):
        return 0.0


def generate_weekly_dashboard():
    log("Generating rolling seven-day NBA dashboard")

    dates = reporting_dates()

    start_date = datetime.fromisoformat(
        dates["dashboard_start"]
    ).date()

    end_date = datetime.fromisoformat(
        dates["dashboard_end"]
    ).date()

    season_dir = EXPORT_DIR / str(SEASON)

    all_games = load_json(season_dir / "games.json", [])
    all_players = load_json(
        season_dir / "player_box_scores.json", []
    )
    raw_games = load_json(GAME_INDEX, [])

    regular_season_ids = {
        str(game["id"])
        for game in raw_games
        if game.get("id")
        and game.get("season", {}).get("type") == 2
    }

    weekly_games = []

    for game in all_games:
        if str(game.get("game_id")) not in regular_season_ids:
            continue

        if game.get("status", "").lower() != "final":
            continue

        try:
            game_date = (
                datetime.fromisoformat(
                    game["date"].replace("Z", "+00:00")
                )
                .astimezone(LOCAL_TIMEZONE)
                .date()
            )
        except (ValueError, TypeError, KeyError):
            continue

        if start_date <= game_date <= end_date:
            game_copy = dict(game)
            game_copy["local_date"] = game_date.isoformat()
            weekly_games.append(game_copy)

    weekly_game_ids = {
        str(game["game_id"]) for game in weekly_games
    }

    player_totals = {}

    for player in all_players:
        if str(player.get("game_id")) not in weekly_game_ids:
            continue

        if player.get("did_not_play"):
            continue

        player_id = str(player.get("player_id", ""))

        if not player_id:
            continue

        if player_id not in player_totals:
            player_totals[player_id] = {
                "player_id": player_id,
                "player_name": player.get("player_name"),
                "team": player.get("team"),
                "team_abbreviation": player.get("team_abbreviation"),
                "games": 0,
                "points": 0,
                "rebounds": 0,
                "assists": 0,
                "steals": 0,
                "blocks": 0,
            }

        record = player_totals[player_id]

        record["games"] += 1
        record["points"] += number(player.get("PTS"))
        record["rebounds"] += number(player.get("REB"))
        record["assists"] += number(player.get("AST"))
        record["steals"] += number(player.get("STL"))
        record["blocks"] += number(player.get("BLK"))

    leaders = list(player_totals.values())

    for player in leaders:
        for stat in [
            "points", "rebounds", "assists", "steals", "blocks"
        ]:
            player[stat] = int(player[stat])

    points_leaders = sorted(
        leaders, key=lambda p: p["points"], reverse=True
    )[:10]

    rebound_leaders = sorted(
        leaders, key=lambda p: p["rebounds"], reverse=True
    )[:10]

    assist_leaders = sorted(
        leaders, key=lambda p: p["assists"], reverse=True
    )[:10]

    team_records = {}

    daily_games = {}

    for game in weekly_games:
        home = game.get("home_abbreviation")
        away = game.get("away_abbreviation")

        for abbreviation, name in [
            (home, game.get("home_team")),
            (away, game.get("away_team"))
        ]:
            if not abbreviation:
                continue

            team_records.setdefault(abbreviation, {
                "team": name,
                "abbreviation": abbreviation,
                "wins": 0,
                "losses": 0,
                "points_for": 0,
                "points_against": 0,
            })

        home_score = number(game.get("home_score"))
        away_score = number(game.get("away_score"))

        if home and away:
            team_records[home]["points_for"] += int(home_score)
            team_records[home]["points_against"] += int(away_score)
            team_records[away]["points_for"] += int(away_score)
            team_records[away]["points_against"] += int(home_score)

            if home_score > away_score:
                team_records[home]["wins"] += 1
                team_records[away]["losses"] += 1
            elif away_score > home_score:
                team_records[away]["wins"] += 1
                team_records[home]["losses"] += 1

        day = game["local_date"]

        daily_games.setdefault(day, {
            "date": day,
            "games": 0,
            "total_points": 0,
        })

        daily_games[day]["games"] += 1
        daily_games[day]["total_points"] += int(
            home_score + away_score
        )

    team_leaders = sorted(
        team_records.values(),
        key=lambda t: (
            t["wins"],
            t["points_for"] - t["points_against"]
        ),
        reverse=True
    )

    daily_summary = [
        daily_games[day]
        for day in sorted(daily_games)
    ]

    dashboard = {
        "season": SEASON_NAME,
        "generated_at": dates["run_time"],
        "reporting_period": {
            "start": dates["dashboard_start"],
            "end": dates["dashboard_end"],
            "timezone": "Australia/Sydney",
        },
        "summary": {
            "games_played": len(weekly_games),
            "total_points": sum(
                number(g.get("home_score"))
                + number(g.get("away_score"))
                for g in weekly_games
            ),
            "average_points_per_game": round(
                sum(
                    number(g.get("home_score"))
                    + number(g.get("away_score"))
                    for g in weekly_games
                ) / len(weekly_games), 1
            ) if weekly_games else 0,
            "players_in_action": len(leaders),
        },
        "games": sorted(
            weekly_games,
            key=lambda g: g["local_date"]
        ),
        "daily_scoring": daily_summary,
        "player_leaders": {
            "points": points_leaders,
            "rebounds": rebound_leaders,
            "assists": assist_leaders,
        },
        "team_form": team_leaders,
    }

    # Current dashboard used by the website.
    save_json(DASHBOARD_FILE, dashboard)

    # Permanent dated snapshot of this reporting period.
    history_dir = DASHBOARD_DIR / "history"
    history_dir.mkdir(parents=True, exist_ok=True)

    snapshot_file = (
        history_dir /
        f"{dates['run_date']}.json"
    )

    save_json(snapshot_file, dashboard)

    log(f"Dashboard games: {len(weekly_games)}")
    log(f"Dashboard players: {len(leaders)}")
    log(f"Dashboard snapshot: {snapshot_file}")


# ============================================================
# WEEKLY UPDATE VALIDATION
# ============================================================

def validate_weekly_outputs():
    log("Validating weekly update outputs")

    from openpyxl import load_workbook

    season_dir = EXPORT_DIR / str(SEASON)

    required_files = [
        season_dir / "games.json",
        season_dir / "player_box_scores.json",
        season_dir / "team_game_stats.json",
        season_dir / "play_by_play.json",
        season_dir / "player_averages.json",
        season_dir / "player_totals.json",
        season_dir / "player_advanced.json",
        season_dir / "team_season_stats.json",
        WORKBOOK,
        DASHBOARD_FILE,
    ]

    missing = [
        str(path) for path in required_files
        if not path.exists()
    ]

    if missing:
        raise RuntimeError(
            "Missing required outputs: " + ", ".join(missing)
        )

    for path in required_files:
        if path.stat().st_size == 0:
            raise RuntimeError(f"Empty output file: {path}")

    games = load_json(season_dir / "games.json", [])
    players = load_json(
        season_dir / "player_box_scores.json", []
    )
    play_by_play = load_json(
        season_dir / "play_by_play.json", []
    )
    dashboard = load_json(DASHBOARD_FILE, None)

    if not isinstance(games, list) or not isinstance(players, list):
        raise RuntimeError("Game or player data has an invalid format")

    if not isinstance(play_by_play, list):
        raise RuntimeError("Play-by-play data has an invalid format")

    if not isinstance(dashboard, dict):
        raise RuntimeError("Dashboard data has an invalid format")

    if len({str(g.get("game_id")) for g in games}) != len(games):
        raise RuntimeError("Duplicate game IDs detected")

    expected_sheets = {
        "Games",
        "Player Box Scores",
        "Team Game Stats",
        "Player Averages",
        "Player Totals",
        "Player Advanced",
        "Team Season Stats",
        "Play-by-Play",
        "Players",
        "Teams",
        "Season Summary",
        "Collection Log",
    }

    workbook = load_workbook(WORKBOOK, read_only=True)

    actual_sheets = set(workbook.sheetnames)
    workbook.close()

    if actual_sheets != expected_sheets:
        raise RuntimeError(
            f"Workbook worksheet mismatch: {actual_sheets}"
        )

    if dashboard.get("season") != SEASON_NAME:
        raise RuntimeError("Dashboard season mismatch")

    log("JSON validation: PASS")
    log("Game ID uniqueness: PASS")
    log("Workbook integrity: PASS")
    log("All 12 worksheets: PASS")
    log("Dashboard validation: PASS")

    return {
        "games": len(games),
        "player_box_scores": len(players),
        "play_by_play_events": len(play_by_play),
        "workbook_size_mb": round(
            WORKBOOK.stat().st_size / (1024 * 1024), 2
        ),
        "dashboard_games": dashboard["summary"]["games_played"],
    }

def rebuild_player_directory():
    log("Refreshing the complete NBA player directory")

    script = BASE_DIR / "scripts" / "build_player_directory.py"

    subprocess.run(
        [sys.executable, str(script)],
        check=True,
        cwd=BASE_DIR
    )

    log("Player directory refreshed successfully")

# ============================================================
# CURRENT SEASON WORKBOOK GENERATION
# ============================================================

def generate_current_season_workbook():
    log("Generating current-season Excel workbook")

    backup_file = WORKBOOK.with_suffix(".xlsx.backup")

    if WORKBOOK.exists():
        shutil.copy2(WORKBOOK, backup_file)
        log("Previous workbook backed up")

    try:
        script = (
            BASE_DIR / "scripts" /
            "create_excel_workbooks.py"
        )

        subprocess.run(
            [sys.executable, str(script), str(SEASON)],
            check=True,
            cwd=BASE_DIR
        )

        if not WORKBOOK.exists():
            raise RuntimeError("Workbook was not created")

        if WORKBOOK.stat().st_size == 0:
            raise RuntimeError("Generated workbook is empty")

        log("New workbook generated successfully")

    except Exception:
        if backup_file.exists():
            shutil.copy2(backup_file, WORKBOOK)
            log("Previous workbook restored")

        raise


# ============================================================
# WEBSITE DOWNLOAD PREPARATION
# ============================================================

def prepare_website_download():
    log("Preparing website workbook download")

    if not WORKBOOK.exists():
        raise RuntimeError("Source workbook does not exist")

    WEBSITE_WORKBOOK.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temporary_file = WEBSITE_WORKBOOK.with_suffix(
        ".xlsx.tmp"
    )

    shutil.copy2(WORKBOOK, temporary_file)
    temporary_file.replace(WEBSITE_WORKBOOK)

    if (
        not WEBSITE_WORKBOOK.exists()
        or WEBSITE_WORKBOOK.stat().st_size != WORKBOOK.stat().st_size
    ):
        raise RuntimeError(
            "Website workbook copy failed integrity check"
        )

    log("Website workbook prepared successfully")


# ============================================================
# GITHUB WEBSITE PUBLISHING
# ============================================================

def publish_website():
    log("Publishing NBA Stats Archive website")

    paths = [
        "website/data",
        f"website/downloads/{WEBSITE_WORKBOOK.name}",
    ]

    subprocess.run(
        ["git", "add"] + paths,
        check=True,
        cwd=BASE_DIR
    )

    changes = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=BASE_DIR
    )

    if changes.returncode == 0:
        log("No website changes to publish")
        return

    if changes.returncode != 1:
        raise RuntimeError("Unable to inspect staged Git changes")

    run_date = datetime.now(LOCAL_TIMEZONE).strftime("%Y-%m-%d")

    subprocess.run(
        [
            "git",
            "commit",
            "-m",
            f"Update NBA weekly dashboard and {SEASON_NAME} data ({run_date})"
        ],
        check=True,
        cwd=BASE_DIR
    )

    subprocess.run(
        ["git", "push"],
        check=True,
        cwd=BASE_DIR
    )

    log("Website successfully pushed to GitHub")


# ============================================================
# MASTER WEEKLY UPDATE WORKFLOW
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="NBA Stats Archive weekly update"
    )

    parser.add_argument(
        "--no-publish",
        action="store_true",
        help="Update local files without publishing to GitHub"
    )

    args = parser.parse_args()

    initialise_directories()

    started = datetime.now(LOCAL_TIMEZONE)

    run_entry = {
        "started": started.isoformat(),
        "season": SEASON_NAME,
        "status": "running",
        "published": False,
    }

    log("=" * 60)
    log("NBA STATS ARCHIVE WEEKLY UPDATE")
    log(f"Season: {SEASON_NAME}")
    log(f"Started: {started.isoformat()}")
    log("=" * 60)

    backup_file = WORKBOOK.with_suffix(".xlsx.backup")

    try:

        # 1. Collect recent games
        failures = collect_recent_games()

        if failures:
            raise RuntimeError(
                f"Game collection failed for {len(failures)} dates"
            )

        # 2. Collect recent game summaries
        failures = collect_recent_summaries()

        if failures:
            raise RuntimeError(
                f"Game summary collection failed for "
                f"{len(failures)} games"
            )

        # 3. Refresh player directory
        rebuild_player_directory()

        # 4. Process games and box scores
        process_current_season()

        # 5. Process play-by-play
        process_current_season_play_by_play()

        # 6. Collect and process player statistics
        player_failures = collect_current_season_player_stats()

        process_current_season_player_stats()

        # 7. Collect and process team statistics
        team_failures = collect_current_season_team_stats()

        if team_failures:
            raise RuntimeError(
                f"Team statistics collection failed for "
                f"{len(team_failures)} teams"
            )

        process_current_season_team_stats()

        # 8. Generate current-season workbook
        generate_current_season_workbook()

        # 9. Generate rolling seven-day dashboard
        generate_weekly_dashboard()

        # 10. Validate all outputs
        validation = validate_weekly_outputs()

        # Keep the backup until validation succeeds.
        if backup_file.exists():
            backup_file.unlink()

        # 11. Prepare website download
        prepare_website_download()

        # 12. Publish unless manually disabled
        if args.no_publish:
            log("Publishing skipped (--no-publish)")
        else:
            publish_website()
            run_entry["published"] = True

        run_entry.update({
            "status": "success",
            "finished": datetime.now(LOCAL_TIMEZONE).isoformat(),
            "validation": validation,
            "player_download_failures": len(player_failures),
            "team_download_failures": len(team_failures),
        })

        log("=" * 60)
        log("WEEKLY UPDATE COMPLETED SUCCESSFULLY")
        log(f"Games: {validation['games']:,}")
        log(f"Player box scores: {validation['player_box_scores']:,}")
        log(f"Play-by-play events: {validation['play_by_play_events']:,}")
        log(f"Dashboard games: {validation['dashboard_games']}")
        log(f"Player download failures: {len(player_failures)}")
        log("=" * 60)

    except Exception as error:

        if backup_file.exists():
            shutil.copy2(backup_file, WORKBOOK)
            log("Previous workbook restored after failed update")

        run_entry.update({
            "status": "failed",
            "error": str(error),
            "finished": datetime.now(LOCAL_TIMEZONE).isoformat(),
        })

        log(f"WEEKLY UPDATE FAILED: {error}")

        append_run_log(run_entry)

        raise

    append_run_log(run_entry)


if __name__ == "__main__":
    main()

