import json
import os
import random
import re
import time
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field, ValidationError


load_dotenv()

app = FastAPI(title="A17 LLM Book Classifier")


PROMPT_VERSION = "classify_v1"

PROMPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "prompts"
    / "classify_v1.txt"
)

LOG_PATH = (
    Path(__file__).resolve().parent.parent
    / "output"
    / "llm-cost.jsonl"
)

MODEL = "gemini-3.6-flash"

MAX_RETRIES = 3
BACKOFF_SECONDS = [1, 2, 4]


class ClassifyRequest(BaseModel):
    text: str = Field(min_length=1)


class ClassifyResponse(BaseModel):
    category: Literal["fiction", "non-fiction", "unknown"]
    confidence: Literal["high", "medium", "low"]
    reason: str


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    errors = exc.errors()

    if errors:
        location = errors[0].get("loc", ())
        field = str(location[-1]) if location else "body"
    else:
        field = "body"

    return JSONResponse(
        status_code=400,
        content={
            "error": "Invalid input",
            "field": field,
        },
    )


def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def fallback_response() -> dict:
    return {
        "category": "unknown",
        "confidence": "low",
        "reason": "Insufficient information to classify.",
    }


def extract_json_object(text: str) -> dict:
    text = text.strip()

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s*```$", "", text)

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)

    if not match:
        raise ValueError("No JSON object found in model output.")

    return json.loads(match.group(0))


def validate_model_output(text: str) -> ClassifyResponse:
    data = extract_json_object(text)
    return ClassifyResponse.model_validate(data)


def is_retryable_error(exc: Exception) -> bool:
    if isinstance(exc, TimeoutError):
        return True

    if isinstance(exc, errors.APIError):
        status_code = exc.code

        if status_code == 429:
            return True

        if status_code is not None and 500 <= status_code <= 599:
            return True

    return False


def get_retry_after_seconds(exc: Exception) -> float | None:
    if not isinstance(exc, errors.APIError):
        return None

    details = getattr(exc, "details", None)

    if not isinstance(details, dict):
        return None

    retry_after = details.get("retryAfter")

    if retry_after is None:
        return None

    match = re.search(
        r"(\d+(?:\.\d+)?)",
        str(retry_after),
    )

    if not match:
        return None

    return float(match.group(1))


def write_cost_log(
    input_tokens: int,
    output_tokens: int,
    duration_ms: int,
    repair_count: int,
):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "prompt_version": PROMPT_VERSION,
        "model": MODEL,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "duration_ms": duration_ms,
        "repair_count": repair_count,
    }

    with LOG_PATH.open(
        "a",
        encoding="utf-8",
    ) as log_file:
        log_file.write(
            json.dumps(record) + "\n"
        )


def generate_content_with_retry(
    client: genai.Client,
    user_text: str,
    system_prompt: str,
    repair_count: int,
) -> str:
    for attempt in range(MAX_RETRIES + 1):
        start_time = time.perf_counter()

        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=user_text,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=300,
                    thinking_config=types.ThinkingConfig(
                        thinking_level="minimal",
                    ),
                ),
            )

            duration_ms = int(
                (time.perf_counter() - start_time) * 1000
            )

            usage = getattr(
                response,
                "usage_metadata",
                None,
            )

            input_tokens = int(
                getattr(
                    usage,
                    "prompt_token_count",
                    0,
                )
                or 0
            )

            output_tokens = int(
                getattr(
                    usage,
                    "candidates_token_count",
                    0,
                )
                or 0
            )

            write_cost_log(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=duration_ms,
                repair_count=repair_count,
            )

            return response.text

        except Exception as exc:
            if not is_retryable_error(exc):
                raise

            if attempt >= MAX_RETRIES:
                raise

            retry_after = get_retry_after_seconds(exc)

            if retry_after is not None:
                delay = retry_after
            else:
                base_delay = BACKOFF_SECONDS[
                    min(
                        attempt,
                        len(BACKOFF_SECONDS) - 1,
                    )
                ]
                delay = base_delay + random.uniform(0, 0.5)

            print(
                "LLM_RETRY "
                f"attempt={attempt + 1} "
                f"delay_seconds={delay:.2f} "
                f"error={exc}"
            )

            time.sleep(delay)


def call_gemini(
    user_text: str,
    prompt: str,
) -> str:
    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options=types.HttpOptions(
            timeout=30000,
        ),
    )

    return generate_content_with_retry(
        client,
        user_text,
        prompt,
        repair_count=0,
    )


def repair_output(
    original_output: str,
    validation_error: str,
    prompt: str,
) -> str:
    repair_prompt = f"""
You are repairing an invalid classifier response.

Return ONLY one valid JSON object with exactly these fields:

{{
  "category": "fiction | non-fiction | unknown",
  "confidence": "high | medium | low",
  "reason": "short explanation"
}}

The previous model output was:

{original_output}

The validation error was:

{validation_error}

Fix the response so it follows the required schema exactly.
Do not add Markdown or any text outside the JSON object.
"""

    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options=types.HttpOptions(
            timeout=30000,
        ),
    )

    return generate_content_with_retry(
        client,
        repair_prompt,
        prompt,
        repair_count=1,
    )


@app.post(
    "/classify",
    response_model=ClassifyResponse,
)
def classify(request: ClassifyRequest):
    llm_enabled = (
        os.getenv("LLM_ENABLED", "true").lower()
        == "true"
    )

    if not llm_enabled:
        return fallback_response()

    if os.getenv("LLM_STUB") == "1":
        return fallback_response()

    prompt = load_prompt()

    try:
        model_output = call_gemini(
            request.text,
            prompt,
        )

        try:
            result = validate_model_output(
                model_output
            )
            return result.model_dump()

        except (
            ValueError,
            json.JSONDecodeError,
            ValidationError,
        ) as exc:
            validation_error = str(exc)

            # Exactly one repair attempt.
            repaired_output = repair_output(
                model_output,
                validation_error,
                prompt,
            )

            try:
                repaired_result = validate_model_output(
                    repaired_output
                )
                return repaired_result.model_dump()

            except (
                ValueError,
                json.JSONDecodeError,
                ValidationError,
            ) as repair_exc:
                print(
                    "QUARANTINE "
                    f"prompt_version={PROMPT_VERSION} "
                    f"model={MODEL} "
                    f"error={repair_exc}"
                )

                return JSONResponse(
                    status_code=422,
                    content={
                        "error": (
                            "Model output could not "
                            "be validated."
                        )
                    },
                )

    except Exception as exc:
        print(
            "LLM_ERROR "
            f"prompt_version={PROMPT_VERSION} "
            f"model={MODEL} "
            f"error={exc}"
        )

        return JSONResponse(
            status_code=502,
            content={
                "error": "LLM request failed.",
            },
        )