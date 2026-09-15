from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright

from report import get_report_data


BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"


def build_html(report):
    today = date.today().isoformat()

    top_books_rows = ""

    for book in report["top_books"]:
        top_books_rows += f"""
        <tr>
            <td>{book["title"]}</td>
            <td>£{book["price"]:.2f}</td>
            <td>{book["rating"]:.0f}</td>
        </tr>
        """

    rating_rows = ""

    for item in report["books_by_rating"]:
        rating_rows += f"""
        <tr>
            <td>{item["rating"]:.0f}</td>
            <td>{item["count"]}</td>
        </tr>
        """

    all_books_rows = ""

    for book in report["all_books"]:
        all_books_rows += f"""
        <tr>
            <td>{book["title"]}</td>
            <td>£{book["price"]:.2f}</td>
            <td>{book["rating"]:.0f}</td>
            <td>{book["url"]}</td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">

        <style>
            @page {{
                size: A4;
                margin: 18mm;
            }}

            body {{
                font-family: Arial, sans-serif;
                font-size: 11px;
                line-height: 1.4;
            }}

            h1 {{
                margin-bottom: 4px;
            }}

            h2 {{
                margin-top: 24px;
            }}

            .date {{
                color: #666;
                margin-bottom: 20px;
            }}

            .summary {{
                display: flex;
                gap: 40px;
                margin-bottom: 20px;
            }}

            .summary-box {{
                border: 1px solid #ccc;
                padding: 12px;
                min-width: 150px;
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }}

            th,
            td {{
                border: 1px solid #ccc;
                padding: 6px;
                text-align: left;
            }}

            thead {{
                display: table-header-group;
            }}

            tr {{
                break-inside: avoid;
            }}

            .url {{
                word-break: break-all;
                font-size: 8px;
            }}
        </style>
    </head>

    <body>
        <h1>Bookstore Report</h1>

        <div class="date">
            Generated: {today}
        </div>

        <div class="summary">
            <div class="summary-box">
                <strong>Total books</strong><br>
                {report["total_books"]}
            </div>

            <div class="summary-box">
                <strong>Average price</strong><br>
                £{report["average_price"]:.2f}
            </div>
        </div>

        <h2>Top 5 Most Expensive Books</h2>

        <table>
            <thead>
                <tr>
                    <th>Title</th>
                    <th>Price</th>
                    <th>Rating</th>
                </tr>
            </thead>

            <tbody>
                {top_books_rows}
            </tbody>
        </table>

        <h2>Books by Rating</h2>

        <table>
            <thead>
                <tr>
                    <th>Rating</th>
                    <th>Number of Books</th>
                </tr>
            </thead>

            <tbody>
                {rating_rows}
            </tbody>
        </table>

        <h2>All Books</h2>

        <table>
            <thead>
                <tr>
                    <th>Title</th>
                    <th>Price</th>
                    <th>Rating</th>
                    <th>URL</th>
                </tr>
            </thead>

            <tbody>
                {all_books_rows}
            </tbody>
        </table>
    </body>
    </html>
    """


def generate_pdf(output_path):
    report = get_report_data()
    html = build_html(report)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()

        page.set_content(html)

        page.pdf(
            path=str(output_path),
            format="A4",
            print_background=True,
        )

        browser.close()


if __name__ == "__main__":
    output = REPORTS_DIR / "test.pdf"
    generate_pdf(output)
    print(f"Generated PDF: {output}")