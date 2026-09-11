import os
import requests

URL = "https://books.toscrape.com/catalogue/page-1.html"
CACHE_FILE = "cache/catalogue-page-1.html"

HEADERS = {
    "User-Agent": "FlyRankInternship-A9/1.0"
}


def fetch_page():
    # Check cache first
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as file:
            html = file.read()

        print(f"CACHE HIT: {len(html)} bytes")
        return html

    # Make the real request
    response = requests.get(
        URL,
        headers=HEADERS,
        timeout=10
    )

    # Check HTTP status
    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch page: HTTP {response.status_code}"
        )

    html = response.text

    # Make sure cache directory exists
    os.makedirs("cache", exist_ok=True)

    # Save HTML to cache
    with open(CACHE_FILE, "w", encoding="utf-8") as file:
        file.write(html)

    print(f"FETCH: {len(html)} bytes")

    return html


if __name__ == "__main__":
    fetch_page()