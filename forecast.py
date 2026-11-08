"""Reusable baseline forecasting functions."""

def daily_average(units_sold, days_observed=14):
    if days_observed <= 0:
        raise ValueError("days_observed must be positive")
    if any(x < 0 for x in units_sold):
        raise ValueError("Sales cannot be negative")
    return round(sum(units_sold) / days_observed, 2)

def estimated_unsold(stock, sales_per_day, days_until_expiry):
    if min(stock, sales_per_day) < 0:
        raise ValueError("Stock and sales must be nonnegative")
    return max(0, int(stock - round(sales_per_day * max(0, days_until_expiry))))
