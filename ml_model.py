
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

def predict_daily_sales(sales_data, product_id):
    """
    Predict daily sales for one product.
    Returns: (prediction, method, validation_mae)
    """
    df = sales_data[
        sales_data["product_id"] == product_id
    ].copy()

    if df.empty:
        return 0.0, "No sales history", None

    df["sold_at"] = pd.to_datetime(df["sold_at"])
    df["day"] = df["sold_at"].dt.normalize()

    daily = (
        df.groupby("day")["quantity"]
        .sum()
        .sort_index()
    )

    # Include days with zero recorded sales.
    full_dates = pd.date_range(
        daily.index.min(),
        daily.index.max(),
        freq="D"
    )
    daily = daily.reindex(full_dates, fill_value=0)

    if len(daily) < 14:
        return (
            float(daily.tail(7).mean()),
            "Historical average",
            None
        )

    data = pd.DataFrame({
        "sales": daily.values,
        "day_of_week": daily.index.dayofweek,
        "lag_1": daily.shift(1).values,
        "lag_7": daily.shift(7).values,
        "rolling_7": daily.shift(1).rolling(7).mean().values
    }).dropna()

    features = [
        "day_of_week",
        "lag_1",
        "lag_7",
        "rolling_7"
    ]

    if len(data) < 10:
        return (
            float(daily.tail(7).mean()),
            "Historical average",
            None
        )

    split = max(1, len(data) - 4)
    train = data.iloc[:split]
    test = data.iloc[split:]

    model = RandomForestRegressor(
        n_estimators=100,
        random_state=42,
        min_samples_leaf=2
    )

    model.fit(train[features], train["sales"])

    mae = None

    if not test.empty:
        test_predictions = model.predict(test[features])
        mae = float(
            mean_absolute_error(test["sales"], test_predictions)
        )

    # Retrain using all available observations.
    model.fit(data[features], data["sales"])

    next_day = daily.index.max() + pd.Timedelta(days=1)

    next_features = pd.DataFrame([{
        "day_of_week": next_day.dayofweek,
        "lag_1": float(daily.iloc[-1]),
        "lag_7": float(daily.iloc[-7]),
        "rolling_7": float(daily.iloc[-7:].mean())
    }])

    prediction = float(model.predict(next_features)[0])

    return max(0.0, prediction), "Random Forest", mae
