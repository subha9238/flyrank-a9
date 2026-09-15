import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "report.db"


def get_report_data():
    connection = sqlite3.connect(DB_PATH)

    total_books = connection.execute(
        """
        SELECT COUNT(*)
        FROM books
        """
    ).fetchone()[0]

    average_price = connection.execute(
        """
        SELECT AVG(price)
        FROM books
        """
    ).fetchone()[0]

    top_books = connection.execute(
        """
        SELECT title, price, rating, url
        FROM books
        ORDER BY price DESC
        LIMIT 5
        """
    ).fetchall()

    books_by_rating = connection.execute(
        """
        SELECT rating, COUNT(*)
        FROM books
        GROUP BY rating
        ORDER BY rating
        """
    ).fetchall()

    all_books = connection.execute(
        """
        SELECT title, price, rating, url
        FROM books
        ORDER BY id
        """
    ).fetchall()

    connection.close()

    return {
        "total_books": total_books,
        "average_price": average_price,
        "top_books": [
            {
                "title": row[0],
                "price": row[1],
                "rating": row[2],
                "url": row[3],
            }
            for row in top_books
        ],
        "books_by_rating": [
            {
                "rating": row[0],
                "count": row[1],
            }
            for row in books_by_rating
        ],
        "all_books": [
            {
                "title": row[0],
                "price": row[1],
                "rating": row[2],
                "url": row[3],
            }
            for row in all_books
        ],
    }