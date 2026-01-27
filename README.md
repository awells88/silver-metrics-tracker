# Silver Metrics Tracker 🥈📊

A self-hosted dashboard tracking silver market normalization indicators. Monitors physical supply tightness vs paper trading through five key metrics.

## 📈 Tracked Indicators

| Indicator | What It Measures | Normal Range | Stress Signal |
|-----------|------------------|--------------|---------------|
| **Lease Rates** | Cost to borrow physical silver | 0.3-3% | >10% |
| **Physical Premiums** | Dealer prices vs spot | 3-10% | >20% |
| **COMEX Inventory** | Exchange warehouse stocks | 300-400M oz | <250M oz |
| **Margin Stability** | CME futures margin changes | Stable 30+ days | Weekly hikes |
| **Shanghai Premium** | China import demand vs West | $1-2/oz | >$5/oz |

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/silver-metrics-traker.git
cd silver-metrics-traker

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python scripts/db.py

# Run initial data fetch
python main.py
```

### Local Development

```bash
# Fetch latest data
python main.py

# View dashboard locally
cd docs && python -m http.server 8000
# Open http://localhost:8000
```

## 🏗️ Project Structure

```
silver-metrics-traker/
├── .github/workflows/     # GitHub Actions automation
├── data/
│   ├── raw/              # Downloaded source files
│   ├── processed/        # Cleaned data
│   └── silver_metrics.db # SQLite database
├── docs/                 # GitHub Pages dashboard
│   ├── index.html
│   ├── css/
│   ├── js/
│   └── data/            # JSON for frontend
├── scripts/
│   ├── config.py        # Settings & thresholds
│   ├── db.py            # Database operations
│   ├── fetch_*.py       # Data fetchers
│   ├── normalize.py     # Status calculations
│   └── export_json.py   # Frontend data export
├── main.py              # Main runner
└── requirements.txt
```

## 📊 Data Sources

- **CME Group**: Warehouse stocks, margin requirements
- **Kitco**: Spot prices, market news
- **papervsphysical.com**: Real-time dealer premiums
- **MetalpriceAPI**: Silver spot prices for premium calculations
- **Yahoo Finance**: Futures data (backup)

### Optional: MetalpriceAPI Setup

For live silver prices (used in Shanghai premium calculation):

1. Get a free API key at [metalpriceapi.com](https://metalpriceapi.com/register)
2. Set the environment variable:
   ```bash
   export METALPRICEAPI_KEY=your_key_here
   ```
3. For GitHub Actions, add `METALPRICEAPI_KEY` as a repository secret

Without an API key, the tracker uses database spot prices with observed premium values.

## ⚙️ Automation

Data updates automatically every hour via GitHub Actions:

1. Fetches latest data from all sources
2. Processes and stores in database
3. Generates JSON for dashboard
4. Commits and deploys to GitHub Pages

## 🎨 Dashboard Features

- **5-Panel Layout**: Each indicator with current value + trend chart
- **Status Indicators**: Green/Yellow/Red based on thresholds
- **Composite Score**: Overall market stress level (0-5 indicators normalizing)
- **Historical Charts**: 30/90/365 day views
- **Mobile Responsive**: Works on all devices

## 🔧 Configuration

Edit `scripts/config.py` to adjust:
- Data source URLs
- Threshold values for status determination
- Update frequency

## 📝 License

MIT License - See LICENSE file

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes
4. Submit a pull request

## ⚠️ Disclaimer

This tool is for informational purposes only. Not financial advice. Data accuracy depends on source availability.
