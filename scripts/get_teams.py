import requests
import json
from pathlib import Path

URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"

def get_teams():
    print("Retrieving NBA teams from ESPN...")

    response = requests.get(URL, timeout=30)
    response.raise_for_status()

    data = response.json()
    teams = data["sports"][0]["leagues"][0]["teams"]

    team_list = []

    for item in teams:
        team = item["team"]

        team_list.append({
            "id": team["id"],
            "abbreviation": team["abbreviation"],
            "name": team["displayName"]
        })

    output = Path("raw") / "nba_teams.json"

    with open(output, "w") as file:
        json.dump(team_list, file, indent=2)

    print(f"\nSuccessfully saved {len(team_list)} NBA teams.")
    print(f"File: {output}")

if __name__ == "__main__":
    get_teams()
