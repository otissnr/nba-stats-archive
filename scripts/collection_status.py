import json
from pathlib import Path

SEASONS = range(2021, 2028)

def main():
    total_games = 0
    total_downloaded = 0

    print("\n" + "=" * 65)
    print("NBA ARCHIVE - LIVE COLLECTION STATUS")
    print("=" * 65)

    for season in SEASONS:
        season_name = f"{season - 1}-{str(season)[-2:]}"
        index_file = Path("raw/games") / f"{season}.json"
        summary_dir = Path("raw/game_summaries") / str(season)

        if not index_file.exists():
            print(f"\n{season_name}: Game index not found")
            continue

        with open(index_file) as f:
            games = json.load(f)

        expected = len(games)
        downloaded = sum(
            1 for game in games
            if (summary_dir / f"{game.get('id')}.json").exists()
        )

        remaining = expected - downloaded
        percentage = downloaded / expected * 100 if expected else 0

        total_games += expected
        total_downloaded += downloaded

        print(f"\nSeason {season_name}")
        print(f"Downloaded: {downloaded:,} / {expected:,}")
        print(f"Remaining:  {remaining:,}")
        print(f"Progress:   {percentage:.1f}%")

    overall = total_downloaded / total_games * 100 if total_games else 0

    print("\n" + "-" * 65)
    print(f"OVERALL: {total_downloaded:,} / {total_games:,}")
    print(f"COMPLETION: {overall:.1f}%")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
