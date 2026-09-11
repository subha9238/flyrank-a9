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

    # Check HTTP status
    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch page: HTTP {response.status_code}"
        )

    html = response.text

    # Create cache directory
    os.makedirs("cache", exist_ok=True)

    # Save HTML
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

        cache_file = (
            f"cache/catalogue-page-{page_number}.html"
        )

        html = fetch_page(
            current_url,
            cache_file
        )

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        books = soup.select(
            "article.product_pod h3 a"
        )

        print(f"Books found: {len(books)}")

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

        next_link = soup.select_one(
            "li.next a"
        )

        if not next_link:
            break

        current_url = urljoin(
            current_url,
            next_link.get("href")
        )

    # Remove duplicates
    unique_book_urls = list(
        dict.fromkeys(all_book_urls)
    )

    return (
        catalogue_pages,
        all_book_urls,
        unique_book_urls
    )


# --------------------------------------------------
# Extract one book
# --------------------------------------------------

def extract_book(html, product_url, source_page):
    """
    Extract the eight required raw fields
    from one book detail page.
    """

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    # ------------------------------
    # Title
    # ------------------------------

    title_element = soup.select_one(
        "div.product_main h1"
    )

    title = (
        title_element.get_text(strip=True)
        if title_element
        else None
    )

    # ------------------------------
    # Price
    # ------------------------------

    price_element = soup.select_one(
        "div.product_main .price_color"
    )

    price_text = (
        price_element.get_text(strip=True)
        if price_element
        else None
    )

    # ------------------------------
    # Availability
    # ------------------------------

    availability_element = soup.select_one(
        "div.product_main .availability"
    )

    availability_text = (
        availability_element.get_text(
            " ",
            strip=True
        )
        if availability_element
        else None
    )

    # ------------------------------
    # Rating
    # ------------------------------

    rating_element = soup.select_one(
        "div.product_main p.star-rating"
    )

    rating_text = None

    if rating_element:

        classes = rating_element.get(
            "class",
            []
        )

        for rating in [
            "One",
            "Two",
            "Three",
            "Four",
            "Five"
        ]:

            if rating in classes:
                rating_text = rating
                break

    # ------------------------------
    # Description
    # ------------------------------

    description_element = soup.select_one(
        "#product_description"
    )

    description = None

    if description_element:

        description_paragraph = (
            description_element.find_next_sibling("p")
        )

        if description_paragraph:
            description = (
                description_paragraph.get_text(
                    " ",
                    strip=True
                )
            )

    # ------------------------------
    # Fetch time
    # ------------------------------

    fetched_at = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime()
    )

    # ------------------------------
    # Return raw record
    # ------------------------------

    return {
        "title": title,
        "product_url": product_url,
        "price_text": price_text,
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": source_page,
        "fetched_at": fetched_at
    }


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

    # ----------------------------------------------
    # Extract all 60 book records
    # ----------------------------------------------

    records = []

    for index, book_url in enumerate(
        unique_book_urls,
        start=1
    ):

        print()
        print(
            f"Processing book {index}/"
            f"{len(unique_book_urls)}"
        )

        # Create a separate cache file
        cache_file = (
            f"cache/book-{index}.html"
        )

        # Fetch book page
        html = fetch_page(
            book_url,
            cache_file
        )

        # Extract raw record
        record = extract_book(
            html,
            book_url,
            BASE_URL
        )

        records.append(record)

        print(
            f"Extracted: {record['title']}"
        )

    # ----------------------------------------------
    # Final summary
    # ----------------------------------------------

    print()
    print(
        f"detail_pages={len(records)}"
    )

    # Print the first complete record
    if records:
        print()
        print("FIRST COMPLETE RAW RECORD")
        print("--------------------------")
        print(records[0])