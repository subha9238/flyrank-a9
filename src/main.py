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
# Pydantic validation model
# --------------------------------------------------

class BookRecord(BaseModel):
    """
    Clean and validated book record.
    """

    title: str
    product_url: HttpUrl
    price: Decimal = Field(gt=0)
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
            raise ValueError("title cannot be empty")

        return value


# --------------------------------------------------
# Cleaning functions
# --------------------------------------------------

def clean_price(price_text):
    """
    Convert a scraped price such as '£51.77'
    into Decimal('51.77').
    """

    if not price_text:
        return None

    match = re.search(
        r"\d+(?:\.\d+)?",
        price_text
    )

    if not match:
        return None

    return Decimal(match.group(0))


def clean_availability(availability_text):
    """
    Convert 'In stock (22 available)' into 22.
    """

    if not availability_text:
        return None

    match = re.search(
        r"\((\d+)\s+available\)",
        availability_text
    )

    if not match:
        return None

    return int(match.group(1))


def clean_rating(rating_text):
    """
    Convert rating words into integers.
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

    return rating_map.get(rating_text)


# --------------------------------------------------
# Fetch and cache a page
# --------------------------------------------------

def fetch_page(url, cache_file):
    """
    Fetch a page from the website or read it from cache.
    """

    # Check cache first
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

        return html

    # Wait before making a real request
    time.sleep(DELAY_SECONDS)

    print(
        f"FETCH: {url}"
    )

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
    os.makedirs(
        "cache",
        exist_ok=True
    )

    # Save HTML
    with open(
        cache_file,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(html)

    print(
        f"Saved to cache: {len(html)} bytes"
    )

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

        print(
            f"Books found: {len(books)}"
        )

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
# Extract one book
# --------------------------------------------------

def extract_book(
    html,
    product_url,
    source_page
):
    """
    Extract the eight required raw fields.
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
        title_element.get_text(strip=True)
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
        price_element.get_text(strip=True)
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
            description_element.find_next_sibling("p")
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

    # --------------------------------------------------
    # Return raw record
    # --------------------------------------------------

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
# Clean and validate one book
# --------------------------------------------------

def clean_and_validate_book(raw_record):
    """
    Convert raw scraped values into clean,
    validated Pydantic data.
    """

    cleaned_record = {
        "title": raw_record["title"],
        "product_url": raw_record["product_url"],
        "price": clean_price(
            raw_record["price_text"]
        ),
        "availability_count": clean_availability(
            raw_record["availability_text"]
        ),
        "rating": clean_rating(
            raw_record["rating_text"]
        ),
        "description": raw_record["description"],
        "source_page": raw_record["source_page"],
        "fetched_at": raw_record["fetched_at"]
    }

    return BookRecord(
        **cleaned_record
    )


# --------------------------------------------------
# Save validated records to JSON
# --------------------------------------------------

def save_records(records):
    """
    Save all validated records to output/books.json.
    """

    os.makedirs(
        "output",
        exist_ok=True
    )

    output_file = "output/books.json"

    data = [
        record.model_dump(mode="json")
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


# --------------------------------------------------
# Save validated records to CSV
# --------------------------------------------------

def save_records_csv(records):
    """
    Save all validated records to output/books.csv.
    """

    os.makedirs(
        "output",
        exist_ok=True
    )

    output_file = "output/books.csv"

    fieldnames = [
        "title",
        "product_url",
        "price",
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

            writer.writerow(data)

    print()
    print(
        f"Saved {len(records)} records to "
        f"{output_file}"
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

    # --------------------------------------------------
    # Extract and validate all book records
    # --------------------------------------------------

    records = []

    validation_errors = 0

    for index, book_url in enumerate(
        unique_book_urls,
        start=1
    ):

        print()

        print(
            f"Processing book {index}/"
            f"{len(unique_book_urls)}"
        )

        cache_file = (
            f"cache/book-{index}.html"
        )

        html = fetch_page(
            book_url,
            cache_file
        )

        raw_record = extract_book(
            html,
            book_url,
            BASE_URL
        )

        try:

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

            validation_errors += 1

            print(
                f"VALIDATION ERROR: "
                f"{raw_record.get('title')}"
            )

            print(error)

    # --------------------------------------------------
    # Final summary
    # --------------------------------------------------

    print()

    print(
        f"detail_pages={len(records)}"
    )

    print(
        f"validation_errors={validation_errors}"
    )

    # --------------------------------------------------
    # Show first clean record
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
    # Save output files
    # --------------------------------------------------

    if validation_errors == 0:

        save_records(records)

        save_records_csv(records)

    else:

        print()
        print(
            "Output files were not saved because "
            "validation errors were found."
        )