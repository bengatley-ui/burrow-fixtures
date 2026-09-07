from playwright.sync_api import sync_playwright
from datetime import datetime
import json
import re
from urllib.parse import urljoin

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

def clean(text):
return re.sub(r"\s+", " ", text or "").strip()

def parse_date(text):
match = re.search(r"(\d{2})/(\d{2})/(\d{2,4})", text)
if not match:
return None

day, month, year = match.groups()

if len(year) == 2:
    year = "20" + year

return datetime.strptime(
    f"{day}/{month}/{year}",
    "%d/%m/%Y"
).date()


def extract_fixtures(page):
fixtures = []

tables = page.locator("table").all()

for table in tables:
    headers = [
        clean(x.inner_text())
        for x in table.locator("thead th").all()
    ]

    if not headers:
        continue

    header_text = " ".join(headers).lower()

    if "venue" not in header_text:
        continue

    venue_index = next(
        (i for i, h in enumerate(headers)
         if "venue" in h.lower()),
        None
    )

    date_index = next(
        (i for i, h in enumerate(headers)
         if "date" in h.lower()),
        None
    )

    home_index = next(
        (i for i, h in enumerate(headers)
         if "home team" in h.lower()),
        None
    )

    away_index = next(
        (i for i, h in enumerate(headers)
         if "away team" in h.lower()),
        None
    )

    competition_index = next(
        (i for i, h in enumerate(headers)
         if "competition" in h.lower()),
        None
    )

    if venue_index is None or date_index is None:
        continue

    rows = table.locator("tbody tr").all()

    for row in rows:
        cells = [
            clean(x.inner_text())
            for x in row.locator("td").all()
        ]

        if len(cells) <= venue_index:
            continue

        venue = cells[venue_index]

        if "burrow" not in venue.lower():
            continue

        date_text = (
            cells[date_index]
            if date_index < len(cells)
            else ""
        )

        fixture_date = parse_date(date_text)

        if fixture_date is None:
            continue

        if fixture_date < datetime.now().date():
            continue

        home = (
            cells[home_index]
            if home_index is not None and home_index < len(cells)
            else ""
        )

        away = (
            cells[away_index]
            if away_index is not None and away_index < len(cells)
            else ""
        )

        competition = (
            cells[competition_index]
            if competition_index is not None
            and competition_index < len(cells)
            else ""
        )

        time_match = re.search(
            r"\b(\d{1,2}:\d{2})\b",
            date_text
        )

        time = time_match.group(1) if time_match else ""

        fixtures.append({
            "date": fixture_date.strftime("%d/%m/%Y"),
            "sort_date": fixture_date.isoformat(),
            "time": time,
            "home": home,
            "away": away,
            "venue": venue,
            "competition": competition
        })

return fixtures


with sync_playwright() as p:
browser = p.chromium.launch(headless=True)
page = browser.new_page()

print("Opening FA fixtures...")
page.goto(FA_URL, wait_until="networkidle", timeout=120000)

page.wait_for_timeout(3000)

all_fixtures = []

# Collect the fixture pages currently offered by the FA.
links = page.locator("a").all()

page_urls = {page.url}

for link in links:
    try:
        text = clean(link.inner_text())

        if text.isdigit():
            href = link.get_attribute("href")

            if href:
                page_urls.add(urljoin(page.url, href))
    except Exception:
        pass

print(f"Found {len(page_urls)} fixture pages.")

for url in sorted(page_urls):
    try:
        print("Reading:", url)

        page.goto(url, wait_until="networkidle", timeout=120000)
        page.wait_for_timeout(1500)

        all_fixtures.extend(extract_fixtures(page))

    except Exception as e:
        print("Could not read page:", e)

browser.close()

Remove duplicates.

unique = {}

for fixture in all_fixtures:
key = (
fixture["sort_date"],
fixture["time"],
fixture["home"],
fixture["away"],
fixture["venue"]
)

unique[key] = fixture


fixtures = list(unique.values())

fixtures.sort(
key=lambda x: (
x["sort_date"],
x["time"],
x["venue"]
)
)

for fixture in fixtures:
fixture.pop("sort_date", None)

with open("fixtures.json", "w", encoding="utf-8") as f:
json.dump(
fixtures,
f,
indent=2,
ensure_ascii=False
)

print(f"Saved {len(fixtures)} Burrow fixtures.")
