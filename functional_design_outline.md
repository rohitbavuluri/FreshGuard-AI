# Functional Design — Draft Outline

## Architecture
Browser → Streamlit app (`app.py`) → SQLite (`freshguard.db`)
Streamlit app → 14-day sales average → expiry risk rules → dashboard and manager discount approval

## Screens
Dashboard, Inventory, Sales, AI Predictions, Expiry Alerts, Reports.

## Data flow
Manager enters products → database saves stock → cashier records sales → inventory decrements → forecast estimates unsold units → manager reviews alert and approves discount → subsequent sales use new price.

## Error handling
Required product name, nonnegative stock/prices, stock-availability check, protected sales history.

## Current limitations
Forecast is a historical-average baseline, not machine learning or generative AI. No user login, persistent cloud storage, or automated tests of the interface.
