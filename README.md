# Bank Statement Analyzer

An AI-powered financial analytics platform that transforms raw bank statements into actionable insights, spending intelligence, forecasts, and professional reports.

## Overview

Bank Statement Analyzer is a full-stack analytics application designed to process PDF and Excel bank statements, automatically categorize transactions, generate financial insights, forecast future spending patterns, and produce downloadable reports.

The system supports multi-statement analysis, merchant intelligence, category learning, forecasting, and financial health monitoring through an interactive dashboard.

## Key Features

### Statement Processing
- PDF statement upload
- Excel statement upload
- Multi-statement support
- Password-protected PDF handling
- Duplicate statement detection
- Statement replacement and merge workflows

### Dashboard
- Financial KPIs
- Income tracking
- Expense tracking
- Savings analysis
- Monthly trends
- Spending breakdowns
- Recent transaction monitoring

### Transaction Management
- Advanced filtering
- Search functionality
- Category editing
- Rule-based categorization
- Merchant identification
- Transaction audit view

### Analytics Engine
- Category analysis
- Merchant analysis
- Payment method analysis
- Spending trends
- Subscription detection
- Weekly heatmaps
- Financial insights engine

### Forecasting
- Future income projections
- Expense forecasting
- Savings forecasting
- What-if simulations
- Category-based projections
- Cash-flow predictions

### Reporting
- Summary reports
- Detailed reports
- Analytics reports
- Forecast reports
- Downloadable PDF exports

## Tech Stack

### Backend
- Python
- Flask
- SQLite

### Frontend
- HTML
- CSS
- JavaScript
- Bootstrap
- Chart.js

### Data Processing
- Pandas
- OpenPyXL
- PDF Parsing Libraries

## Project Structure

Bank-Statement-Analyzer/
│
├── app.py
├── requirements.txt
│
├── database/
│   ├── db.py
│   ├── models.py
│   └── bank_statement.db
│
├── parsers/
│   ├── pdf_parser.py
│   └── excel_parser.py
│
├── routes/
│   ├── upload_routes.py
│   ├── dashboard_routes.py
│   ├── transaction_routes.py
│   ├── analytics_routes.py
│   ├── forecast_routes.py
│   └── report_routes.py
│
├── services/
│   ├── analytics.py
│   ├── categorizer.py
│   ├── forecast.py
│   ├── insights.py
│   └── report_generator.py
│
├── templates/
├── static/
└── uploads/

## Installation

### Clone Repository

 git clone https://github.com/ManasPurnendu/Bank-Statement-Analyser.git cd Bank-Statement-Analyser 

### Create Virtual Environment

python -m venv venv 

### Activate Environment

macOS/Linux:

source venv/bin/activate 

Windows:

venv\Scripts\activate 

### Install Dependencies

pip install -r requirements.txt 

### Run Application

python app.py 

## Current Development Status

### Completed
- Project architecture
- Database layer
- Statement parsing
- Dashboard implementation
- Analytics engine
- Forecasting engine
- Report generation
- Frontend UI

### In Progress
- Advanced categorization rules
- Forecast accuracy improvements
- UI refinements
- Additional analytics modules

## Author

Manas Purnendu

Internship Project – Bank Statement Analyzer

Built using Python, Flask, SQLite, JavaScript, and modern analytics workflows.