# FlyRank A9 - The Polite Scraper

## Target Classification

### Target

Books to Scrape

### Website

https://books.toscrape.com/

### Purpose

Books to Scrape is a public practice sandbox for learning web scraping.

### Scope

This project will scrape only the first 3 catalogue pages.

The expected number of unique books is 60.

### Data Collected

The scraper will collect:

- title
- product URL
- price
- availability
- rating
- description
- source page
- fetch time

### Robots.txt

I checked the robots.txt file before writing the scraper.

Result:

No robots file found. The robots.txt URL returned HTTP 404 Not Found.

### Responsible Scraping

I will not reuse this code on another site without checking its rules and terms first.

---

# A17 — LLM Behind Your API

## LLM Book Classifier

This API classifies a user-submitted book description into a controlled category and returns a structured JSON response.

## Provider and Model

- Provider: Google Gemini API
- Model: `gemini-3.8-flash`
- Prompt version: `classify_v1`

## API Endpoint

POST `/classify`

### Input

```json
{
  "text": "A fantasy novel about a young wizard who discovers a hidden magical kingdom."
}