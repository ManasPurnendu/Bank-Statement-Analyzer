# Bank Statement Analyzer

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-v3.0-green.svg)](https://flask.palletsprojects.com/)
[![SQLite](https://img.shields.io/badge/sqlite-v3.0-orange.svg)](https://sqlite.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

An intelligent, full-stack financial analytics platform that transforms raw PDF and Excel bank statements into structured spending intelligence, continuous cash-flow charts, predictive forecasts, and downloadable PDF reports.

---

## 🚀 Key Capabilities

### 📄 Ingestion & In-Memory Parsing
* **Hybrid Parser Support**: Automatically handles bank statement formats (e.g. HDFC, ICICI, SBI, Axis) in both PDF and Excel formats.
* **Password-Protected PDFs**: Secure, in-memory decryption processing without saving sensitive passwords to disk.
* **Stable Timeline Ingestion**: Employs date-based stable sorting to resolve same-day transaction sequence bugs, eliminating running balance math errors.
* **Duplicate Detection**: Smart statement hash checks that prevent duplicate files, supporting merge or replace overwrite options.

### 🧠 Classification & Auto-Categorization
* **Merchant Matching**: Identifies commercial payees (e.g. Swiggy, Amazon, Uber, Netflix) using sanitizing regexes.
* **Rule-Based Engine**: Allows users to manually classify transactions and optionally register global rules mapping specific merchants or exact transaction amounts.
* **Peer-to-Peer (P2P) Intelligence**: Automatically groups personal transactions (e.g. friends, transfers) with $\ge 5$ occurrences under a custom **Peer-to-Peer** badge, while blacklisting commercial stores, restaurants, or utility billers.
* **ATM & Cash Classification**: Auto-tags physical withdrawals and ATM activities under a dedicated **Cash & ATM** category.

### 📊 Financial Analytics & Insights
* **Continuous Timeline**: Tracks complete financial history sequentially (incorporating zero-activity months to ensure gapless trends for cash-flow charting).
* **Subscriptions Tracker**: Highlights recurring spending behaviors and monitors subscription patterns.
* **Advanced KPIs**: Calculates net savings, savings rate, average monthly spend, day-of-week heatmaps, and busiest transaction days.
* **AI-Powered Insights**: Generates notifications summarizing spend anomalies, high-outflow categories, and positive saving trends.

### 🔮 Forecasting & Simulations
* **Cash-Flow Projection**: Projects future income, expense, and savings rates for subsequent months.
* **What-If Scenarios**: Interactive sliders allowing users to simulate how cutting expenses in select categories affects their projected balances.

### 📋 Professional Reporting
* Compiles dynamic cover sheets and statement metadata.
* Supports customizable date presets (e.g., all-time, last month, last 6 months) for tailoring details.
* Exports clean PDF summaries containing tables and analytics summaries.

---

## 🛠 Tech Stack

* **Backend**: Python 3.10+, Flask (routing & controllers), SQLite3 (database engine)
* **Frontend**: HTML5, Vanilla CSS3 (custom dark/light glassmorphic theme), JavaScript (ES6+ controllers), Chart.js (responsive visuals)
* **Data Processing**: Pandas (analytics aggregations), OpenPyXL (Excel engine), PyPDF2/pypdf (PDF parser)

---

## 📂 Project Directory Structure

```text
Bank-Statement-Analyzer/
├── app.py                     # Main application entry point
├── requirements.txt           # Python package dependencies
├── test_app.py                # Automated unit test suite
│
├── database/
│   ├── db.py                  # DB setup, schema creation, & category rules seeding
│   ├── models.py              # SQL queries and P2P auto-classification hooks
│   └── bank_statement.db      # SQLite3 binary database
│
├── parsers/
│   ├── pdf_parser.py          # PDF regex tokenizer, metadata extractor & stable sorter
│   └── excel_parser.py        # Excel parser and column matcher
│
├── routes/
│   ├── upload_routes.py       # Ingest statements, handle encryption, & resolve duplicates
│   ├── dashboard_routes.py    # Fetch KPI metrics, monthly overviews, & recent txns
│   ├── analytics_routes.py    # Aggregate categories, heatmaps, & top merchants
│   ├── forecast_routes.py     # Projections and what-if simulation hooks
│   └── report_routes.py       # Handle PDF reporting downloads
│
├── services/
│   ├── analytics.py           # Financial metric calculators & trend generators
│   ├── categorizer.py         # Match keywords/amounts with rules & clean descriptions
│   ├── forecast.py            # Predictive forecast logic
│   ├── insights.py            # Generate financial notifications
│   └── report_generator.py    # Compile PDF reports using ReportLab
│
├── templates/                 # HTML UI layouts (landing, dashboard, analytics, etc.)
├── static/
│   ├── css/style.css          # Color variables, layout, dark-mode & category badges
│   └── js/main.js             # Theme initialization & AJAX fetch controllers
└── uploads/                   # Temporary cache directory for statement parsing
```

---

## ⚙️ Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/ManasPurnendu/Bank-Statement-Analyser.git
cd Bank-Statement-Analyser
```

### 2. Configure Virtual Environment
Create a virtual environment to isolate project dependencies:
```bash
# Create environment
python3 -m venv venv

# Activate (macOS / Linux)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Security Configuration
Copy the environment template and generate a secure secret key:
```bash
cp .env.example .env
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))" > .env
```
> **Note:** If `SECRET_KEY` is not set, a random key is generated at startup. This is fine for local development, but sessions will not persist across server restarts. Always set a fixed key in production.

### 5. Database Setup & Seeding
Initialize the SQLite schema and seed standard category lookup data:
```bash
python3 database/db.py
```

### 6. Start the Application
Run the Flask server locally:
```bash
python3 app.py
```
Open [http://127.0.0.1:5001](http://127.0.0.1:5001) in your browser to access the platform.

---

## 🧪 Testing

The codebase includes a comprehensive test suite covering parsers, database schemas, categorizers, and API controllers. Run tests using:

```bash
python3 test_app.py
```

---

## 👤 Author

* **Manas Purnendu** - [GitHub Profile](https://github.com/ManasPurnendu)
* Internship Project – *Bank Statement Analyzer Stabilization*