import json
import time

import requests


API_URL = "http://127.0.0.1:8000/classify"
CASES_PATH = "evals/cases.json"

DELAY_BETWEEN_CASES = 13


def main():
    with open(CASES_PATH, "r", encoding="utf-8") as file:
        cases = json.load(file)

    matches = 0
    failures = []

    for index, case in enumerate(cases):
        response = requests.post(
            API_URL,
            json={"text": case["text"]},
            timeout=35,
        )

        if response.status_code != 200:
            failures.append(
                {
                    "id": case["id"],
                    "error": f"HTTP {response.status_code}",
                }
            )
        else:
            actual = response.json()
            expected = case["expected"]

            category_match = (
                actual.get("category")
                == expected["category"]
            )

            confidence_match = (
                actual.get("confidence")
                == expected["confidence"]
            )

            if category_match and confidence_match:
                matches += 1
            else:
                failures.append(
                    {
                        "id": case["id"],
                        "expected": expected,
                        "actual": {
                            "category": actual.get("category"),
                            "confidence": actual.get("confidence"),
                        },
                    }
                )

        if index < len(cases) - 1:
            print(
                f"Waiting {DELAY_BETWEEN_CASES}s before next case..."
            )
            time.sleep(DELAY_BETWEEN_CASES)

    total = len(cases)
    percentage = (matches / total * 100) if total else 0

    print(f"Matches: {matches}/{total}")
    print(f"Score: {percentage:.1f}%")

    if failures:
        print("Failures:")
        for failure in failures:
            print(json.dumps(failure, indent=2))
    else:
        print("Failures: none")


if __name__ == "__main__":
    main()