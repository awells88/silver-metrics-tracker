# CLAUDE.md - Silver Metrics Tracker

## Project Overview

Self-hosted Python dashboard that tracks silver market normalization indicators. Monitors physical supply tightness vs. paper trading through 5 key metrics: lease rates, physical premiums, COMEX inventory, margin stability, and Shanghai premium. Data is fetched from multiple sources, stored in SQLite, normalized into a composite score (0-5), and exported as JSON for a static GitHub Pages dashboard.

## Tech Stack

- **Language**: Python 3.10+
- **Database**: SQLite (`data/silver_metrics.db`)
- **Web Scraping**: requests, BeautifulSoup4, lxml, Playwright (for JS-rendered pages)
- **Financial Data**: yfinance (Yahoo Finance API)
- **Data Processing**: pandas, openpyxl, xlrd
- **Frontend**: Vanilla HTML/CSS/JS with Chart.js (no build step)
- **Testing**: pytest
- **Deployment**: GitHub Pages (static site in `docs/`)

## Project Structure

```
main.py                         # Entry point / orchestrator
scripts/
├── config.py                   # Central settings, URLs, thresholds
├── db.py                       # SQLite database operations
├── fetch_spot_prices.py        # Silver spot price (Yahoo Finance, Kitco)
├── fetch_cme_stocks.py         # COMEX warehouse inventory (CME Excel)
├── fetch_cme_margins.py        # CME futures margin requirements
├── fetch_premiums.py           # Physical dealer premiums
├── fetch_lease_rates.py        # Lease rate proxy via futures curve
├── fetch_shanghai_premium.py   # Shanghai exchange premium (Playwright)
├── normalize.py                # Threshold logic, scoring, status colors
└── export_json.py              # JSON export for dashboard
tests/
└── test_normalize.py           # Unit tests for normalization logic
docs/                           # GitHub Pages static dashboard
├── index.html
├── css/style.css
├── js/charts.js
└── data/                       # Generated JSON (latest.json, historical.json, badge.json)
data/
├── silver_metrics.db           # SQLite database
├── raw/                        # Downloaded source files
└── processed/                  # Cleaned data
```

## Common Commands

```bash
# Run a single data update (fetch + normalize + export)
python main.py

# Verbose/debug mode
python main.py -v

# Continuous updates (default 60s interval)
python main.py --continuous
python main.py --continuous --interval 300

# Partial runs
python main.py --fetch-only      # Fetch data only, skip export
python main.py --export-only     # Export existing data only
python main.py --init-db         # Initialize database schema only

# Run tests
pytest tests/test_normalize.py -v

# Serve dashboard locally
cd docs && python -m http.server 8000
```

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium    # Required for Shanghai premium scraping
```

## Architecture

### Data Pipeline Flow

```
Fetch Phase → Store Phase → Normalize Phase → Export Phase → Serve Phase
```

1. **Fetch**: `main.py:fetch_all_data()` calls each fetcher independently. Individual failures don't block the pipeline.
2. **Store**: Each fetcher writes to its own SQLite table via `scripts/db.py`.
3. **Normalize**: `scripts/normalize.py` applies threshold logic from `scripts/config.py` to produce green/yellow/red status per metric.
4. **Export**: `scripts/export_json.py` writes `latest.json`, `historical.json`, and `badge.json` to `docs/data/`.
5. **Serve**: GitHub Pages hosts the static dashboard from `docs/`.

### Database Tables

- `spot_prices` - Silver spot price history
- `premiums` - Physical premium over spot
- `inventory` - COMEX warehouse stocks (registered + eligible)
- `margins` - CME futures margin requirements
- `lease_rates` - Lease rate proxy values
- `shanghai_premium` - Shanghai vs Western spot differential
- `metrics_snapshot` - Normalized composite scores over time

### Status Color System

- **Green** = normalizing (market stress easing)
- **Yellow** = caution (elevated but not extreme)
- **Red** = stressed (high stress / supply tightness)

Composite score counts how many of the 5 metrics are green (0-5 scale).

## Configuration

All thresholds and data source URLs are centralized in `scripts/config.py`. Key sections:

- `THRESHOLDS` dict: Defines normal/watch/stressed/extreme ranges for each metric
- `COMPOSITE_THRESHOLDS`: Maps composite score ranges to overall status
- `REQUEST_HEADERS`: Browser-mimicking headers for web scraping
- Data source URLs: CME, Kitco, Yahoo Finance, papervsphysical.com, MetalpriceAPI

### Environment Variables

- `METALPRICEAPI_KEY` - API key for Shanghai premium data (optional, free tier: 100 req/month)
- `LOG_LEVEL` - Logging level override (default: INFO)

## Testing

Tests are in `tests/test_normalize.py` using pytest. They cover:

- **TestNormalization**: Verifies green/yellow/red classification for each metric at various values
- **TestThresholds**: Validates threshold configuration exists and is properly ordered
- **TestDetermineStatus**: Tests the `determine_status()` helper for both "higher_is_worse" and "lower_is_worse" metrics

Tests use a session-scoped fixture that initializes the database. All tests are pure unit tests with no network calls.

Run tests: `pytest tests/test_normalize.py -v`

## Key Conventions

- Each data source has its own fetch module in `scripts/` with a single public function
- Fetchers return `dict` on success or `None` on failure; errors are logged, not raised
- Sanity checks validate numeric ranges (e.g., silver price must be 15-200 USD/oz)
- All modules use Python logging; never use `print()` for operational output
- Type hints are used in function signatures
- Docstrings on all public functions
- Configuration changes go in `scripts/config.py`, not inline in fetchers
- The `docs/data/` directory contains generated JSON files; do not edit them manually

## Important Notes

- The SQLite database (`data/silver_metrics.db`) is committed to the repo for persistence across CI runs
- Raw downloaded files (XLS, HTML) in `data/raw/` are gitignored
- `.env` files are gitignored; never commit API keys
- Playwright requires Chromium to be installed (`playwright install chromium`) for Shanghai premium scraping
- The dashboard frontend has no build step; edit `docs/index.html`, `docs/css/style.css`, and `docs/js/charts.js` directly
