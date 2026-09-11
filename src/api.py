import os
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


app = FastAPI(title="A17 LLM Book Classifier")


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


@app.post("/classify", response_model=ClassifyResponse)
def classify(request: ClassifyRequest):
    if os.getenv("LLM_STUB") == "1":
        return {
            "category": "unknown",
            "confidence": "low",
            "reason": "Insufficient information to classify.",
        }

    return {
        "category": "unknown",
        "confidence": "low",
        "reason": "LLM is not enabled.",
    }