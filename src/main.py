import os
import time
import re
import json
import csv
import requests

from decimal import Decimal
from typing import Optional

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from pydantic import BaseModel, Field, HttpUrl, field_validator


# ==================================================
# Configuration
# ==================================================

BASE_URL = "https://books.toscrape.com/catalogue/page-1.html"

HEADERS = {
    "User-Agent": "FlyRankInternship-A9/1.0"
}

TIMEOUT = 10
DELAY_SECONDS = 0.5
MAX_RETRIES = 1

# Optional failure-test URL.
#
# Normal run:
#   TEST_BROKEN_URL is not set.
#
# Failure test:
#   Set TEST_BROKEN_URL to a deliberately broken URL.
TEST_BROKEN_URL = os.getenv("TEST_BROKEN_URL")


# ==================================================
# Pydantic validation model
# ==================================================

class BookRecord(BaseModel):
    """
    Clean and validated book record.
    """

    title: str

    product_url: HttpUrl

    price_gbp: Decimal = Field(gt=0)

    availability_count: int = Field(ge=0)

    rating: int = Field(ge=1, le=5)

    description: Optional[str] = None

    source_page: HttpUrl

    fetched_at: str

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, value):

        value = value.strip()

        if not value:
            raise ValueError(
                "title cannot be empty"
            )

        return value


# ==================================================
# Cleaning functions
# ==================================================

def clean_price(price_text):
    """
    Convert text such as £51.77 into Decimal('51.77').
    """

    if not price_text:
        return None

    match = re.search(
        r"\d+(?:\.\d+)?",
        price_text
    )

    if not match:
        return None

    return Decimal(
        match.group(0)
    )


def clean_availability(availability_text):
    """
    Convert text such as:
    'In stock (22 available)'
    into integer 22.
    """

    if not availability_text:
        return None

    match = re.search(
        r"\((\d+)\s+available\)",
        availability_text
    )

    if not match:
        return None

    return int(
        match.group(1)
    )


def clean_rating(rating_text):
    """
    Convert rating words into numbers.
    """

    rating_map = {
        "One": 1,
        "Two": 2,
        "Three": 3,
        "Four": 4,
        "Five": 5
    }

    if not rating_text:
        return None

    return rating_map.get(
        rating_text
    )


# ==================================================
# Fetch and cache page
# ==================================================

def fetch_page(url, cache_file):
    """
    Fetch a page from the website or use the cache.

    Network requests:
    - use identifying User-Agent
    - use timeout
    - wait 0.5 seconds
    - retry once for request errors / 5xx

    403 and 404 are not retried.
    """

    # --------------------------------------------------
    # Check cache first
    # --------------------------------------------------

    if os.path.exists(cache_file):

        with open(
            cache_file,
            "r",
            encoding="utf-8"
        ) as file:

            html = file.read()

        print(
            f"CACHE HIT: {len(html)} bytes"
        )

        return html, True

    # --------------------------------------------------
    # Real network request
    # --------------------------------------------------

    for attempt in range(
        MAX_RETRIES + 1
    ):

        time.sleep(
            DELAY_SECONDS
        )

        print(
            f"FETCH: {url}"
        )

        try:

            response = requests.get(
                url,
                headers=HEADERS,
                timeout=TIMEOUT
            )

        except requests.RequestException as error:

            print(
                f"REQUEST ERROR: {error}"
            )

            if attempt < MAX_RETRIES:

                print(
                    "Retrying once..."
                )

                continue

            raise RuntimeError(
                f"Request failed: {error}"
            )

        # --------------------------------------------------
        # 403 / 404
        # Do NOT retry
        # --------------------------------------------------

        if response.status_code in (
            403,
            404
        ):

            raise RuntimeError(
                f"HTTP {response.status_code}"
            )

        # --------------------------------------------------
        # Server errors
        # Retry once
        # --------------------------------------------------

        if response.status_code >= 500:

            if attempt < MAX_RETRIES:

                print(
                    f"HTTP {response.status_code}. "
                    f"Retrying once..."
                )

                continue

            raise RuntimeError(
                f"HTTP {response.status_code}"
            )

        # --------------------------------------------------
        # Other non-200 response
        # --------------------------------------------------

        if response.status_code != 200:

            raise RuntimeError(
                f"HTTP {response.status_code}"
            )

        # --------------------------------------------------
        # Successful response
        # --------------------------------------------------

        html = response.text

        os.makedirs(
            "cache",
            exist_ok=True
        )

        with open(
            cache_file,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(html)

        print(
            f"Saved to cache: {len(html)} bytes"
        )

        return html, False

    raise RuntimeError(
        "Unable to fetch page"
    )


# ==================================================
# Discover first 3 catalogue pages
# ==================================================

def discover_books():
    """
    Discover book URLs from the first three
    catalogue pages.
    """

    current_url = BASE_URL

    catalogue_pages = 0

    all_book_urls = []

    catalogue_cache_hits = 0

    catalogue_fetched_pages = 0

    catalogue_failed_pages = []

    while catalogue_pages < 3:

        page_number = (
            catalogue_pages + 1
        )

        print()

        print(
            f"Processing catalogue page "
            f"{page_number}: {current_url}"
        )

        cache_file = (
            f"cache/catalogue-page-"
            f"{page_number}.html"
        )

        try:

            html, from_cache = fetch_page(
                current_url,
                cache_file
            )

            if from_cache:

                catalogue_cache_hits += 1

            else:

                catalogue_fetched_pages += 1

        except RuntimeError as error:

            print()

            print(
                f"FAILED catalogue page: "
                f"{current_url}"
            )

            print(
                f"ERROR: {error}"
            )

            catalogue_failed_pages.append({
                "url": current_url,
                "error": str(error)
            })

            break

        # --------------------------------------------------
        # Parse catalogue page
        # --------------------------------------------------

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        books = soup.select(
            "article.product_pod h3 a"
        )

        print(
            f"Books found: {len(books)}"
        )

        # --------------------------------------------------
        # Extract book URLs
        # --------------------------------------------------

        for book in books:

            href = book.get(
                "href"
            )

            if not href:
                continue

            absolute_url = urljoin(
                current_url,
                href
            )

            all_book_urls.append(
                absolute_url
            )

        catalogue_pages += 1

        # --------------------------------------------------
        # Find next page
        # --------------------------------------------------

        next_link = soup.select_one(
            "li.next a"
        )

        if not next_link:
            break

        current_url = urljoin(
            current_url,
            next_link.get("href")
        )

    # --------------------------------------------------
    # Remove duplicate URLs
    # --------------------------------------------------

    unique_book_urls = list(
        dict.fromkeys(
            all_book_urls
        )
    )

    return (
        catalogue_pages,
        all_book_urls,
        unique_book_urls,
        catalogue_cache_hits,
        catalogue_fetched_pages,
        catalogue_failed_pages
    )


# ==================================================
# Extract one book
# ==================================================

def extract_book(
    html,
    product_url,
    source_page
):
    """
    Extract raw book fields from a detail page.
    """

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    # --------------------------------------------------
    # Title
    # --------------------------------------------------

    title_element = soup.select_one(
        "div.product_main h1"
    )

    title = (
        title_element.get_text(
            strip=True
        )
        if title_element
        else None
    )

    # --------------------------------------------------
    # Price
    # --------------------------------------------------

    price_element = soup.select_one(
        "div.product_main .price_color"
    )

    price_text = (
        price_element.get_text(
            strip=True
        )
        if price_element
        else None
    )

    # --------------------------------------------------
    # Availability
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Rating
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Description
    # --------------------------------------------------

    description_element = soup.select_one(
        "#product_description"
    )

    description = None

    if description_element:

        description_paragraph = (
            description_element.find_next_sibling(
                "p"
            )
        )

        if description_paragraph:

            description = (
                description_paragraph.get_text(
                    " ",
                    strip=True
                )
            )

    # --------------------------------------------------
    # Fetch time
    # --------------------------------------------------

    fetched_at = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime()
    )

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


# ==================================================
# Clean and validate one book
# ==================================================

def clean_and_validate_book(
    raw_record
):
    """
    Convert raw scraped fields into
    clean, validated fields.
    """

    cleaned_record = {

        "title": raw_record["title"],

        "product_url": raw_record[
            "product_url"
        ],

        "price_gbp": clean_price(
            raw_record["price_text"]
        ),

        "availability_count": (
            clean_availability(
                raw_record[
                    "availability_text"
                ]
            )
        ),

        "rating": clean_rating(
            raw_record["rating_text"]
        ),

        "description": raw_record[
            "description"
        ],

        "source_page": raw_record[
            "source_page"
        ],

        "fetched_at": raw_record[
            "fetched_at"
        ]
    }

    return BookRecord(
        **cleaned_record
    )


# ==================================================
# Save JSON
# ==================================================

def save_records(records):

    os.makedirs(
        "output",
        exist_ok=True
    )

    output_file = (
        "output/books.json"
    )

    data = [
        record.model_dump(
            mode="json"
        )
        for record in records
    ]

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )

    print()

    print(
        f"Saved {len(data)} records to "
        f"{output_file}"
    )


# ==================================================
# Save CSV
# ==================================================

def save_records_csv(records):

    os.makedirs(
        "output",
        exist_ok=True
    )

    output_file = (
        "output/books.csv"
    )

    fieldnames = [
        "title",
        "product_url",
        "price_gbp",
        "availability_count",
        "rating",
        "description",
        "source_page",
        "fetched_at"
    ]

    with open(
        output_file,
        "w",
        encoding="utf-8",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for record in records:

            data = record.model_dump(
                mode="json"
            )

            writer.writerow(
                data
            )

    print()

    print(
        f"Saved {len(records)} records to "
        f"{output_file}"
    )


# ==================================================
# Save errors
# ==================================================

def save_errors(errors):

    os.makedirs(
        "output",
        exist_ok=True
    )

    output_file = (
        "output/errors.json"
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            errors,
            file,
            ensure_ascii=False,
            indent=2
        )

    print()

    print(
        f"Saved {len(errors)} errors to "
        f"{output_file}"
    )


# ==================================================
# Save run report
# ==================================================

def save_run_report(report):

    os.makedirs(
        "output",
        exist_ok=True
    )

    output_file = (
        "output/run-report.json"
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            ensure_ascii=False,
            indent=2
        )

    print()

    print(
        f"Saved run report to "
        f"{output_file}"
    )


# ==================================================
# Main program
# ==================================================

if __name__ == "__main__":

    start_time = time.time()

    # --------------------------------------------------
    # Discover catalogue pages
    # --------------------------------------------------

    (
        catalogue_pages,
        all_book_urls,
        unique_book_urls,
        catalogue_cache_hits,
        catalogue_fetched_pages,
        catalogue_failed_pages
    ) = discover_books()

    # --------------------------------------------------
    # Optional broken URL test
    # --------------------------------------------------

    if TEST_BROKEN_URL:

        print()

        print(
            "BROKEN URL TEST ENABLED"
        )

        print(
            f"Adding test URL: "
            f"{TEST_BROKEN_URL}"
        )

        if TEST_BROKEN_URL not in unique_book_urls:

            unique_book_urls.append(
                TEST_BROKEN_URL
            )

    # --------------------------------------------------
    # Discovery summary
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Extract and validate books
    # --------------------------------------------------

    records = []

    errors = []

    detail_cache_hits = 0

    detail_fetched_pages = 0

    for index, book_url in enumerate(
        unique_book_urls,
        start=1
    ):

        print()

        print(
            f"Processing book "
            f"{index}/"
            f"{len(unique_book_urls)}"
        )

        cache_file = (
            f"cache/book-{index}.html"
        )

        try:

            # --------------------------------------------------
            # Fetch
            # --------------------------------------------------

            html, from_cache = fetch_page(
                book_url,
                cache_file
            )

            if from_cache:

                detail_cache_hits += 1

            else:

                detail_fetched_pages += 1

            # --------------------------------------------------
            # Extract
            # --------------------------------------------------

            raw_record = extract_book(
                html,
                book_url,
                BASE_URL
            )

            # --------------------------------------------------
            # Validate
            # --------------------------------------------------

            validated_record = (
                clean_and_validate_book(
                    raw_record
                )
            )

            records.append(
                validated_record
            )

            print(
                f"Validated: "
                f"{validated_record.title}"
            )

        except Exception as error:

            print()

            print(
                f"FAILED book page: "
                f"{book_url}"
            )

            print(
                f"ERROR: {error}"
            )

            errors.append({
                "url": book_url,
                "error": str(error)
            })

    # --------------------------------------------------
    # Final statistics
    # --------------------------------------------------

    elapsed_seconds = round(
        time.time() - start_time,
        2
    )

    failed_pages = (
        catalogue_failed_pages +
        errors
    )

    # --------------------------------------------------
    # Final summary
    # --------------------------------------------------

    print()

    print(
        "=============================="
    )

    print(
        "FINAL RUN SUMMARY"
    )

    print(
        "=============================="
    )

    print(
        f"catalogue_pages={catalogue_pages}"
    )

    print(
        f"discovered={len(all_book_urls)}"
    )

    print(
        f"unique_urls={len(unique_book_urls)}"
    )

    print(
        f"detail_pages={len(records)}"
    )

    print(
        f"valid_records={len(records)}"
    )

    print(
        f"validation_errors={len(errors)}"
    )

    print(
        f"failed_pages={len(failed_pages)}"
    )

    print(
        f"elapsed_seconds={elapsed_seconds}"
    )

    # --------------------------------------------------
    # Show first validated record
    # --------------------------------------------------

    if records:

        print()

        print(
            "FIRST CLEAN VALIDATED RECORD"
        )

        print(
            "-----------------------------"
        )

        print(
            records[0].model_dump()
        )

    # --------------------------------------------------
    # Save JSON
    # --------------------------------------------------

    save_records(
        records
    )

    # --------------------------------------------------
    # Save CSV
    # --------------------------------------------------

    save_records_csv(
        records
    )

    # --------------------------------------------------
    # Save errors
    # --------------------------------------------------

    save_errors(
        failed_pages
    )

    # --------------------------------------------------
    # Build run report
    # --------------------------------------------------

    run_report = {

        "catalogue_pages":
            catalogue_pages,

        "discovered_urls":
            len(all_book_urls),

        "unique_urls":
            len(unique_book_urls),

        "detail_pages":
            len(records),

        "valid_records":
            len(records),

        "invalid_records":
            len(errors),

        "failed_pages":
            len(failed_pages),

        "catalogue_cache_hits":
            catalogue_cache_hits,

        "catalogue_fetched_pages":
            catalogue_fetched_pages,

        "detail_cache_hits":
            detail_cache_hits,

        "detail_fetched_pages":
            detail_fetched_pages,

        "total_cache_hits":
            (
                catalogue_cache_hits
                +
                detail_cache_hits
            ),

        "total_fetched_pages":
            (
                catalogue_fetched_pages
                +
                detail_fetched_pages
            ),

        "elapsed_seconds":
            elapsed_seconds
    }

    # --------------------------------------------------
    # Save run report
    # --------------------------------------------------

    save_run_report(
        run_report
    )