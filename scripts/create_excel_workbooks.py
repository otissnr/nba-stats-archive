
import csv
import ijson
import json
import os
import sys

from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter


SEASONS = (2021, 2022, 2023, 2024, 2025, 2026, 2027)

OUTPUT_DIR = Path("exports/workbooks")
EXPORT_DIR = Path("exports")

SHEET_CONFIG = [
    ("Games", "games.json", "json"),
    ("Player Box Scores", "player_box_scores.json", "json"),
    ("Team Game Stats", "team_game_stats.json", "json"),
    ("Player Averages", "player_averages.csv", "csv"),
    ("Player Totals", "player_totals.csv", "csv"),
    ("Player Advanced", "player_advanced.csv", "csv"),
    ("Team Season Stats", "team_season_stats.csv", "csv"),
    ("Play-by-Play", "play_by_play.csv", "csv"),
]

HEADER_FILL = PatternFill(
    fill_type="solid",
    fgColor="172B4D"
)

HEADER_FONT = Font(
    bold=True,
    color="FFFFFF",
    size=10
)

ID_FIELDS = {
    "id", "game_id", "player_id", "team_id",
    "sequenceNumber", "jersey"
}


def excel_value(value):
    """Convert nested or unsupported values into Excel-safe values."""

    if value is None:
        return None

    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)

    if isinstance(value, Decimal):
        return float(value)

    return value


def csv_value(value, heading):
    """Convert numeric CSV values while preserving identifiers."""

    if value is None or value == "":
        return None

    if heading in ID_FIELDS or heading.endswith("_id"):
        return value

    try:
        number = float(value)

        if number.is_integer():
            return int(number)

        return number

    except (ValueError, TypeError):
        return value


def add_header(ws, headers):
    """Write a styled header row to a write-only worksheet."""

    ws.freeze_panes = "A2"
    ws.sheet_view.showGridLines = False

    header_cells = []

    for heading in headers:
        cell = WriteOnlyCell(ws, value=heading)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center"
        )
        header_cells.append(cell)

    ws.append(header_cells)


def finish_sheet(ws, headers, count):
    """Apply filters and column widths without reading worksheet rows."""

    if not headers or headers == ["No data"]:
        return

    last_column = get_column_letter(len(headers))
    last_row = count + 1

    ws.auto_filter.ref = f"A1:{last_column}{last_row}"

    for index, heading in enumerate(headers, start=1):
        width = min(max(len(str(heading)) + 3, 13), 28)

        ws.column_dimensions[
            get_column_letter(index)
        ].width = width


def add_json_data(ws, file_path):

    count = 0
    headers = None

    with open(file_path, "rb") as file:

        for record in ijson.items(file, "item"):

            if headers is None:
                headers = list(record.keys())
                add_header(ws, headers)

            ws.append([
                excel_value(record.get(key))
                for key in headers
            ])

            count += 1

            if count % 100000 == 0:
                print(f"      {count:,} rows written")

    if headers is None:
        headers = ["No data"]
        add_header(ws, headers)

    return count, headers


def add_csv_data(ws, file_path):

    count = 0

    with open(
        file_path,
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        reader = csv.DictReader(file)
        headers = reader.fieldnames or ["No data"]

        add_header(ws, headers)

        for record in reader:

            ws.append([
                csv_value(record.get(key), key)
                for key in headers
            ])

            count += 1

            if count % 100000 == 0:
                print(f"      {count:,} rows written")

    return count, headers


def add_player_directory(wb, season):

    ws = wb.create_sheet("Players")

    print("   Adding seasonal player directory...")

    count = 0
    headers = None

    with open(EXPORT_DIR / "players.json", "rb") as file:

        for player in ijson.items(file, "item"):

            if season not in player.get("seasons", []):
                continue

            if headers is None:
                headers = list(player.keys())
                add_header(ws, headers)

            ws.append([
                excel_value(player.get(key))
                for key in headers
            ])

            count += 1

    if headers is None:
        headers = ["No data"]
        add_header(ws, headers)

    finish_sheet(ws, headers, count)

    print(f"      {count:,} seasonal players")

    return count


def add_directory_sheet(wb, title, file_path):

    ws = wb.create_sheet(title)

    print(f"   Adding {title} directory...")

    count, headers = add_json_data(ws, file_path)

    finish_sheet(ws, headers, count)

    print(f"      {count:,} records")

    return count


def create_workbook(season):

    season_name = f"{season - 1}-{str(season)[-2:]}"
    season_dir = EXPORT_DIR / str(season)

    output_file = OUTPUT_DIR / f"NBA_{season_name}.xlsx"

    print("\n" + "=" * 65)
    print(f"CREATING NBA {season_name} WORKBOOK")
    print("=" * 65)

    wb = Workbook(write_only=True)

    wb.properties.title = (
        f"NBA {season_name} Statistics Archive"
    )

    wb.properties.subject = "NBA historical statistics"
    wb.properties.creator = "NBA Stats Archive"

    summary = {
        "Season": season_name,
        "Workbook": output_file.name
    }

    for sheet_name, filename, file_type in SHEET_CONFIG:

        source_file = season_dir / filename

        print(f"\n   Worksheet: {sheet_name}")

        ws = wb.create_sheet(sheet_name)

        if not source_file.exists():

            print(f"      WARNING: Missing file {source_file}")

            add_header(ws, ["Source file missing"])

            summary[sheet_name] = "Missing"
            continue

        if file_type == "json":
            count, headers = add_json_data(ws, source_file)
        else:
            count, headers = add_csv_data(ws, source_file)

        finish_sheet(ws, headers, count)

        summary[sheet_name] = count

        print(f"      Complete: {count:,} records")

    # Players who appeared in this season only

    player_count = add_player_directory(wb, season)
    summary["Players"] = player_count

    # NBA team directory

    team_count = add_directory_sheet(
        wb,
        "Teams",
        Path("raw/nba_teams.json")
    )

    summary["Teams"] = team_count

    # Season summary worksheet

    ws = wb.create_sheet("Season Summary")

    summary_headers = ["Dataset", "Records", "Season"]

    add_header(ws, summary_headers)

    summary_count = 0

    for dataset, count in summary.items():

        if dataset not in ("Season", "Workbook"):

            ws.append([
                dataset,
                count,
                season_name
            ])

            summary_count += 1

    finish_sheet(ws, summary_headers, summary_count)

    # Collection log worksheet

    ws = wb.create_sheet("Collection Log")

    log_headers = ["Item", "Details"]

    add_header(ws, log_headers)

    log_items = [
        ["Season", season_name],
        ["Workbook generated", output_file.name],
        ["Data source", "ESPN public statistics endpoints"],
        ["Generated by", "NBA Stats Archive"],
        ["Play-by-play source", "Processed game summaries"],
    ]

    if season == 2026:
        log_items.append([
            "Missing 2025-26 game summaries",
            "8 games previously recorded as HTTP 404"
        ])

    for item in log_items:
        ws.append(item)

    finish_sheet(ws, log_headers, len(log_items))

    print("\nSaving workbook...")

    wb.save(output_file)

    size_mb = output_file.stat().st_size / (1024 * 1024)

    print(f"WORKBOOK COMPLETE: {output_file}")
    print(f"File size: {size_mb:,.1f} MB")


def main():

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    selected_seasons = list(SEASONS)

    # An optional year argument allows an individual test run.

    if len(sys.argv) > 1:
        selected_seasons = [int(sys.argv[1])]

    print("\nNBA EXCEL WORKBOOK GENERATOR")
    print("=" * 65)
    print("Seasons:", len(selected_seasons))
    print("Output folder:", OUTPUT_DIR)
    print("Using streaming data processing")
    print("=" * 65)

    for season in selected_seasons:

        if season not in SEASONS:
            print(f"Invalid season: {season}")
            return

        create_workbook(season)

    print("\n" + "=" * 65)
    print("WORKBOOK GENERATION FINISHED")
    print("=" * 65)


if __name__ == "__main__":
    main()

