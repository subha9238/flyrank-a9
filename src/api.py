import json
import os
import re
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, ValidationError


load_dotenv()

app = FastAPI(title="A17 LLM Book Classifier")


PROMPT_VERSION = "classify_v1"

PROMPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "prompts"
    / "classify_v1.txt"
)

MODEL = "gemini-3.6-flash"


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


def extract_json_object(text: str) -> dict:
    text = text.strip()

    # Remove Markdown code fences if the model added them.
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    # Find the first JSON object in the response.
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)

    if not match:
        raise ValueError("No JSON object found in model output.")

    return json.loads(match.group(0))


def validate_model_output(text: str) -> ClassifyResponse:
    data = extract_json_object(text)
    return ClassifyResponse.model_validate(data)


def call_gemini(user_text: str, prompt: str) -> str:
    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options=types.HttpOptions(
            timeout=30000,
        ),
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=user_text,
        config=types.GenerateContentConfig(
            system_instruction=prompt,
            max_output_tokens=300,
            thinking_config=types.ThinkingConfig(
                thinking_level="minimal",
            ),
        ),
    )

    return response.text


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

    response = client.models.generate_content(
        model=MODEL,
        contents=repair_prompt,
        config=types.GenerateContentConfig(
            system_instruction=prompt,
            max_output_tokens=300,
            thinking_config=types.ThinkingConfig(
                thinking_level="minimal",
            ),
        ),
    )

    return response.text


@app.post("/classify", response_model=ClassifyResponse)
def classify(request: ClassifyRequest):
    if os.getenv("LLM_STUB") == "1":
        return {
            "category": "unknown",
            "confidence": "low",
            "reason": "Insufficient information to classify.",
        }

    prompt = load_prompt()

    try:
        model_output = call_gemini(request.text, prompt)

        try:
            result = validate_model_output(model_output)
            return result.model_dump()

        except (ValueError, json.JSONDecodeError, ValidationError) as exc:
            validation_error = str(exc)

            # Exactly one repair attempt.
            repaired_output = repair_output(
                model_output,
                validation_error,
                prompt,
            )

            try:
                repaired_result = validate_model_output(repaired_output)
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
                        "error": "Model output could not be validated."
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
                "error": "LLM request failed."
            },
        )