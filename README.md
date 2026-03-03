# finserv-issueflow-demo

A demo repository simulating a FinServ engineering codebase — used to showcase automated issue triage and resolution via the IssueFlow system powered by Devin AI.

## Overview

This repo contains small, realistic bugs across financial utility modules. Each bug corresponds to a GitHub Issue and is covered by a failing test. The IssueFlow automation picks up these issues, dispatches Devin to fix them, and opens a PR — without manual engineering effort.

## Structure

```
finserv-issueflow-demo/
├── app/
│   ├── calculator.py   # Interest, division, discount calculations
│   ├── auth.py         # Email normalization, account masking, password validation
│   └── utils.py        # Currency formatting, date parsing, name truncation
├── tests/
│   ├── test_calculator.py
│   ├── test_auth.py
│   └── test_utils.py
├── requirements.txt
└── README.md
```

## Setup

```bash
pip install -r requirements.txt
```

## Running Tests

```bash
pytest
```

To see which tests are currently failing (i.e., open bugs):

```bash
pytest -v
```

## Known Bugs (Open Issues)

| Issue | File | Bug Description |
|-------|------|----------------|
| #1 | `calculator.py` | `divide()` crashes with `ZeroDivisionError` instead of raising `ValueError` |
| #2 | `calculator.py` | `calculate_interest()` accepts negative principal/rate |
| #3 | `calculator.py` | `apply_discount()` allows discount > 100% or negative |
| #4 | `auth.py` | `normalize_email()` doesn't lowercase the address |
| #5 | `auth.py` | `mask_account_number()` crashes on strings shorter than 4 chars |
| #6 | `utils.py` | `format_currency()` doesn't format to 2 decimal places |
| #7 | `utils.py` | `truncate_name()` crashes when passed `None` |

## How IssueFlow Works

1. GitHub Issues are classified by the IssueFlow service (complexity, risk, auto-fix eligibility)
2. Eligible issues are dispatched to Devin via the Devin API
3. Devin clones the repo, implements the fix, runs tests, and opens a PR
4. The team reviews and merges — or sets up auto-merge for low-risk fixes

## Contributing

This is a demo repo. Issues are intentional for automation testing purposes.
