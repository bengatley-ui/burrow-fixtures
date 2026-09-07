from datetime import datetime
import json
import re
import subprocess

from bs4 import BeautifulSoup

FA_URL = (
    "https://fulltime.thefa.com/fixtures/1/50.html"
    "?selectedSeason=688737730"
    "&selectedFixtureGroupAgeGroup=0"
    "&selectedFixtureGroupKey="
    "&previousSelectedFixtureGroupAgeGroup="
    "&previousSelectedFixtureGroupKey="
    "&selectedDateCode=all"
    "&selectedRelatedFixtureOption=3"
    "&selectedClub=331632585"
    "&previousSelectedClub="
    "&selectedTeam="
    "&selectedFixtureDateStatus="
    "&selectedFixtureStatus="
)

TARGET_VENUE = "burrows field"


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def normalise_venue(text):
    value = clean(text).casefold().replace("’", "'")
    value = re.sub(r"\s+#\w+$", "", value)
    value = value.replace("'", "")
    return value


def is_target_venue(text):
    return normalise_venue(text) == TARGET_VENUE


def parse_date(text):
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", text or "")
    if not match:
        return None

    day, month, year = match.groups()
    if len(year) == 2:
        year = "20" + year

    try:
        return datetime.strptime(f"{day}/{month}/{year}", "%d/%m/%Y").date()
    except ValueError:
        return None


def curl(url, extra_headers=None):
    command = [
        "curl",
        "--silent",
        "--show-error",
        "--fail-with-body",
        "--location",
        "--user-agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "--header",
        "Accept-Language: en-GB,en;q=0.9",
    ]

    for header in extra_headers or []:
        command.extend(["--header", header])

    command.append(url)

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(clean(result.stderr or result.stdout))

    return result.stdout


def fetch_fixtures_html():
    """Use FA directly, then Jina Reader as a Cloudflare-safe fallback."""
    try:
        html = curl(FA_URL)
        if "YOU HAVE BEEN PREVENTED FROM ACCESSING THIS PAGE" not in html.upper():
            print("Fetched FA Full-Time directly.")
            return html
        print("FA Full-Time returned a Cloudflare block; using Jina Reader fallback.")
    except RuntimeError as exc:
        print(f"Direct FA request failed: {exc}; using Jina Reader fallback.")

    jina_url = "https://r.jina.ai/" + FA_URL
    html = curl(
        jina_url,
        [
            "X-Return-Format: html",
            "X-Engine: browser",
            "X-No-Cache: true",
            "X-Timeout: 60",
        ],
    )

    if "YOU HAVE BEEN PREVENTED FROM ACCESSING THIS PAGE" in html.upper():
        raise RuntimeError("Both FA Full-Time and the Jina Reader returned a Cloudflare access-block page.")

    print("Fetched FA Full-Time through Jina Reader.")
    return html


def parse_fixtures(html):
    soup = BeautifulSoup(html, "html.parser")
    fixtures = []

    for row in soup.select(".fixtures-table table tbody tr"):
        def cell_text(css_class):
            cell = row.select_one(f"td.{css_class}")
            return clean(cell.get_text(" ", strip=True)) if cell else ""

        home = cell_text("home-team")
        away = cell_text("road-team")
        if not home or not away:
            continue

        left_cells = row.select("td.left.cell-divider")
        left_text = [clean(cell.get_text(" ", strip=True)) for cell in left_cells]
        if not left_text:
            continue

        date_text = left_text[0]
        fixture_date = parse_date(date_text)
        if fixture_date is None:
            continue

        time_match = re.search(r"\b(\d{1,2}:\d{2})\b", date_text)
        fixture_type_link = row.select_one("td.bold.cell-divider a")
        fixture_type = clean(fixture_type_link.get_text(" ", strip=True)) if fixture_type_link else ""

        id_link = row.select_one('a[href*="id="]')
        id_match = re.search(r"[?&]id=(\d+)", id_link.get("href", "")) if id_link else None
        fixture_id = id_match.group(1) if id_match else ""

        fixtures.append(
            {
                "id": fixture_id,
                "type": fixture_type,
                "date": fixture_date.strftime("%d/%m/%Y"),
                "sort_date": fixture_date.isoformat(),
                "time": time_match.group(1) if time_match else "",
                "home": home,
                "away": away,
                "venue": left_text[1] if len(left_text) > 1 else "",
                "competition": left_text[2] if len(left_text) > 2 else "",
            }
        )

    return fixtures


def main():
    print("Fetching FA Full-Time fixtures...")
    html = fetch_fixtures_html()
    all_fixtures = parse_fixtures(html)
    print(f"Parsed {len(all_fixtures)} fixtures from FA Full-Time.")

    if not all_fixtures:
        raise RuntimeError("No fixtures were parsed; the FA Full-Time page layout may have changed.")

    today = datetime.now().date()
    fixtures = [
        fixture
        for fixture in all_fixtures
        if datetime.fromisoformat(fixture["sort_date"]).date() >= today
        and is_target_venue(fixture["venue"])
    ]

    unique = {}
    for fixture in fixtures:
        key = (
            fixture["sort_date"],
            fixture["time"],
            fixture["home"],
            fixture["away"],
            normalise_venue(fixture["venue"]),
        )
        unique[key] = fixture

    fixtures = sorted(
        unique.values(),
        key=lambda fixture: (fixture["sort_date"], fixture["time"], fixture["home"]),
    )

    for fixture in fixtures:
        fixture.pop("sort_date", None)

    with open("fixtures.json", "w", encoding="utf-8") as output:
        json.dump(fixtures, output, indent=2, ensure_ascii=False)
        output.write("\n")

    print(f"Saved {len(fixtures)} upcoming fixtures at Burrow's Field.")


if __name__ == "__main__":
    main()
