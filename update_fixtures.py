from datetime import datetime
import json
import re
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

FA_URL = (
    "https://fulltime.thefa.com/fixtures.html"
    "?selectedSeason=688737730"
    "&selectedFixtureGroupAgeGroup=0"
    "&selectedFixtureGroupKey="
    "&selectedDateCode=all"
    "&selectedClub=331632585"
    "&selectedTeam="
    "&selectedRelatedFixtureOption=3"
    "&selectedFixtureDateStatus="
    "&selectedFixtureStatus="
    "&previousSelectedFixtureGroupAgeGroup="
    "&previousSelectedFixtureGroupKey="
    "&previousSelectedClub="
    "&itemsPerPage=25"
)

TARGET_VENUE = "burrow's field"


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def normalise_venue(text):
    return clean(text).casefold().replace("’", "'")


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


def extract_fixtures(page):
    fixtures = []

    for table in page.locator("table").all():
        headers = [clean(th.inner_text()) for th in table.locator("thead th").all()]
        if not headers:
            continue

        indexes = {
            "venue": next((i for i, h in enumerate(headers) if "venue" in h.casefold()), None),
            "date": next((i for i, h in enumerate(headers) if "date" in h.casefold()), None),
            "home": next((i for i, h in enumerate(headers) if "home team" in h.casefold()), None),
            "away": next((i for i, h in enumerate(headers) if "away team" in h.casefold()), None),
            "competition": next((i for i, h in enumerate(headers) if "competition" in h.casefold()), None),
        }

        if indexes["venue"] is None or indexes["date"] is None:
            continue

        for row in table.locator("tbody tr").all():
            cells = [clean(td.inner_text()) for td in row.locator("td").all()]
            if len(cells) <= max(indexes["venue"], indexes["date"]):
                continue

            date_text = cells[indexes["date"]]
            fixture_date = parse_date(date_text)
            if fixture_date is None:
                continue

            time_match = re.search(r"\b(\d{1,2}:\d{2})\b", date_text)
            home_index = indexes["home"]
            away_index = indexes["away"]
            competition_index = indexes["competition"]

            fixtures.append({
                "date": fixture_date.strftime("%d/%m/%Y"),
                "sort_date": fixture_date.isoformat(),
                "time": time_match.group(1) if time_match else "",
                "home": cells[home_index] if home_index is not None and home_index < len(cells) else "",
                "away": cells[away_index] if away_index is not None and away_index < len(cells) else "",
                "venue": cells[indexes["venue"]],
                "competition": cells[competition_index] if competition_index is not None and competition_index < len(cells) else "",
            })

    return fixtures


def discover_page_urls(page):
    page_urls = {page.url}

    for link in page.locator("a").all():
        try:
            text = clean(link.inner_text())
            href = link.get_attribute("href")
            if href and text.isdigit():
                page_urls.add(urljoin(page.url, href))
        except Exception:
            continue

    return page_urls


def main():
    all_fixtures = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            print("Opening FA fixtures...")
            page.goto(FA_URL, wait_until="networkidle", timeout=120000)
            page.wait_for_timeout(3000)

            page_urls = discover_page_urls(page)
            print(f"Found {len(page_urls)} fixture pages.")

            for url in sorted(page_urls):
                try:
                    print("Reading:", url)
                    page.goto(url, wait_until="networkidle", timeout=120000)
                    page.wait_for_timeout(1500)
                    all_fixtures.extend(extract_fixtures(page))
                except Exception as exc:
                    print(f"Could not read page {url}: {exc}")
        finally:
            browser.close()

    today = datetime.now().date()
    upcoming = [
        fixture for fixture in all_fixtures
        if datetime.fromisoformat(fixture["sort_date"]).date() >= today
    ]

    fixtures = [
        fixture for fixture in upcoming
        if normalise_venue(fixture["venue"]) == TARGET_VENUE
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

    print(f"Collected {len(all_fixtures)} total fixtures.")
    print(f"Saved {len(fixtures)} upcoming fixtures at Burrow's Field.")


if __name__ == "__main__":
    main()
