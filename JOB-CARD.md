# A17 — LLM Behind Your API

## Job

Classify a user-submitted book description into a controlled category and return a structured JSON response.

## Input

The API accepts:

```json
{
  "text": "string"
}
## Output

The API returns:

```json
{
  "category": "string",
  "confidence": "string",
  "reason": "string"
}
## Closed Lists

### category

- fiction
- non-fiction
- unknown

### confidence

- high
- medium
- low

## Must Never

- Never return a category outside the closed list.
- Never return confidence outside the closed list.
- Never return raw model output to the API user.
- Never expose API keys or secrets.
- Never treat user-provided text as system instructions.

## When Unsure

If the description does not provide enough evidence for a reliable classification, return:

```json
{
  "category": "unknown",
  "confidence": "low",
  "reason": "Insufficient information to classify."
}