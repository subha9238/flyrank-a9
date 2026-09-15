import json
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
BOOKS_PATH = BASE_DIR.parent / "output" / "books.json"
DB_PATH = BASE_DIR / "report.db"


def main():
    with open(BOOKS_PATH, "r", encoding="utf-8") as file:
        books = json.load(file)

    connection = sqlite3.connect(DB_PATH)

    connection.execute("DROP TABLE IF EXISTS books")

    connection.execute(
        """
        CREATE TABLE books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            price REAL NOT NULL,
            rating REAL NOT NULL,
            url TEXT NOT NULL
        )
        """
    )

    for book in books:
        connection.execute(
            """
            INSERT INTO books (title, price, rating, url)
            VALUES (?, ?, ?, ?)
            """,
            (
                book["title"],
                float(book["price_gbp"]),
                book["rating"],
                book["product_url"],
            ),
        )

    connection.commit()

    count = connection.execute(
        "SELECT COUNT(*) FROM books"
    ).fetchone()[0]

    connection.close()

    print(f"Inserted {count} books into report.db")


if __name__ == "__main__":
    main()