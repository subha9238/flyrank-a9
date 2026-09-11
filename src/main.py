import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


# --------------------------------------------------
# Configuration
# --------------------------------------------------

BASE_URL = "https://books.toscrape.com/catalogue/page-1.html"

HEADERS = {
    "User-Agent": "FlyRankInternship-A9/1.0"
}

TIMEOUT = 10
DELAY_SECONDS = 0.5


# --------------------------------------------------
# Fetch and cache a page
# --------------------------------------------------

def fetch_page(url, cache_file):
    """
    Fetch a page from the website or read it from cache.

    Real requests use:
    - identifying User-Agent
    - timeout
    - HTTP status check
    - 0.5 second delay

    Cached pages do not make a network request.
    """

    # Check cache first
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as file:
            html = file.read()

        print(f"CACHE HIT: {len(html)} bytes")
        return html

    # Wait before making a real request
    time.sleep(DELAY_SECONDS)

    print(f"FETCH: {url}")

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT
    )

    # Only HTTP 200 is accepted
    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch page: HTTP {response.status_code}"
        )

    html = response.text

    # Create cache directory if needed
    os.makedirs("cache", exist_ok=True)

    # Save HTML to cache
    with open(cache_file, "w", encoding="utf-8") as file:
        file.write(html)

    print(f"Saved to cache: {len(html)} bytes")

    return html


# --------------------------------------------------
# Discover the first 3 catalogue pages
# --------------------------------------------------

def discover_books():
    """
    Discover book URLs from the first three catalogue pages.
    """

    current_url = BASE_URL

    catalogue_pages = 0
    all_book_urls = []

    while catalogue_pages < 3:

        page_number = catalogue_pages + 1

        print()
        print(
            f"Processing catalogue page "
            f"{page_number}: {current_url}"
        )

        # Each catalogue page gets its own cache file
        cache_file = (
            f"cache/catalogue-page-{page_number}.html"
        )

        # Fetch page or use cache
        html = fetch_page(
            current_url,
            cache_file
        )

        # Parse HTML
        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        # Find all books on this page
        books = soup.select(
            "article.product_pod h3 a"
        )

        print(f"Books found: {len(books)}")

        # Convert every relative URL to an absolute URL
        for book in books:

            href = book.get("href")

            if href:
                absolute_url = urljoin(
                    current_url,
                    href
                )

                all_book_urls.append(
                    absolute_url
                )

        catalogue_pages += 1

        # Find the website's Next link
        next_link = soup.select_one(
            "li.next a"
        )

        # Stop if there is no Next link
        if not next_link:
            break

        # Convert the Next link to an absolute URL
        current_url = urljoin(
            current_url,
            next_link.get("href")
        )

    # Remove duplicate URLs
    unique_book_urls = list(
        dict.fromkeys(all_book_urls)
    )

    return (
        catalogue_pages,
        all_book_urls,
        unique_book_urls
    )


# --------------------------------------------------
# Main program
# --------------------------------------------------

if __name__ == "__main__":

    (
        catalogue_pages,
        all_book_urls,
        unique_book_urls
    ) = discover_books()

    print()
    print(
        f"catalogue_pages={catalogue_pages}"
    )

    print(
        f"discovered={len(all_book_urls)}"
    )

    print(
        f"unique_urls={len(unique_book_urls)}"
    )