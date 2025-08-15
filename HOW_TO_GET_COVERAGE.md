# HOW TO GET CODE COVERAGE

## The ONE command you need:

```bash
python coverage.py
```

That's it. No flags. No confusion. No searching.

## What it does:
- Runs all tests with coverage
- Outputs to `coverage.json`
- Shows percentage in terminal
- Current coverage: ~25%

## If that doesn't work:

```bash
python -m pytest tests/ --cov=src --cov-report=json:coverage.json --cov-report=term
```

## Where to find results:
- **JSON Report**: `coverage.json`
- **Terminal**: Shows percentage when you run it

## Why this exists:
Because agents shouldn't have to search through 10 different scripts and documentation files to figure out how to get code coverage. One command. One result. Simple.