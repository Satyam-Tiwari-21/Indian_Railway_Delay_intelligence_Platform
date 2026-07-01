# ml/models/forecaster.py
# Prophet-based zone delay forecaster.
# One model per zone — saved as separate .pkl files.
# Falls back to trend extrapolation if Prophet isn't installed.

import joblib
import warnings
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")  # Suppress Prophet's verbose Stan output


class ZoneForecaster:
    """
    Time-series delay forecaster using Facebook Prophet.
    Trained per railway zone (NR, SR, CR, etc.).

    Prophet handles:
    - Weekly seasonality (weekends have different delay patterns)
    - Yearly seasonality (monsoon, fog season)
    - Indian holidays (added explicitly as regressors)
    """

    def __init__(self, zone: str):
        self.zone = zone
        self.model = None
        self._is_fitted = False

    def fit(self, df_zone: pd.DataFrame) -> "ZoneForecaster":
        """
        Fit Prophet on daily avg delay for this zone.

        Args:
            df_zone: DataFrame with columns [journey_date, avg_delay]
                     One row per day for this zone.
        """
        try:
            from prophet import Prophet
            from ml.utils.indian_calendar import build_prophet_holidays
        except ImportError:
            print("  ⚠️  Prophet not installed — using trend fallback.")
            self._fit_fallback(df_zone)
            return self

        # Prophet expects columns: ds (date) and y (value)
        df_prophet = pd.DataFrame({
            "ds": pd.to_datetime(df_zone["journey_date"]),
            "y":  df_zone["avg_delay"].clip(lower=0),
        }).dropna()

        if len(df_prophet) < 30:
            print(f"  ⚠️  Zone {self.zone}: only {len(df_prophet)} days of data. Need 30+.")
            self._fit_fallback(df_zone)
            return self

        # Build Indian holiday calendar for training data years
        years = list(df_prophet["ds"].dt.year.unique())
        holidays = build_prophet_holidays(years + [max(years) + 1])

        self.model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            holidays=holidays,
            changepoint_prior_scale=0.05,  # Conservative — delays are sticky
            seasonality_prior_scale=10.0,
        )

        # Add custom Indian seasonality
        self.model.add_seasonality(
            name="monsoon",
            period=365.25,
            fourier_order=5,
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.model.fit(df_prophet)

        self._is_fitted = True
        print(f"  Prophet fitted for zone {self.zone} on {len(df_prophet)} days")
        return self

    def _fit_fallback(self, df_zone: pd.DataFrame) -> None:
        """Simple linear trend fallback when Prophet is unavailable."""
        if len(df_zone) < 2:
            self._fallback_mean = 20.0
            self._fallback_slope = 0.0
        else:
            y = df_zone["avg_delay"].fillna(20.0).values
            x = np.arange(len(y))
            coeffs = np.polyfit(x, y, 1)
            self._fallback_slope = coeffs[0]
            self._fallback_mean  = y[-1]
        self._is_fitted = True
        self.model = None

    def forecast(self, days: int = 30) -> pd.DataFrame:
        """
        Generate a day-by-day forecast.

        Returns DataFrame with columns:
            date, predicted_avg_delay, lower_80, upper_80
        """
        if not self._is_fitted:
            raise RuntimeError("Call fit() before forecast()")

        if self.model is None:
            # Fallback forecast
            return self._fallback_forecast(days)

        future = self.model.make_future_dataframe(periods=days, freq="D")
        forecast = self.model.predict(future)

        # Get only the future rows
        forecast_future = forecast.tail(days)
        return pd.DataFrame({
            "date":                  forecast_future["ds"].dt.date.values,
            "predicted_avg_delay":   forecast_future["yhat"].clip(lower=0).round(1).values,
            "lower_80":              forecast_future["yhat_lower"].clip(lower=0).round(1).values,
            "upper_80":              forecast_future["yhat_upper"].clip(lower=0).round(1).values,
        })

    def _fallback_forecast(self, days: int) -> pd.DataFrame:
        """Linear trend extrapolation with Indian seasonal multipliers."""
        from ml.utils.indian_calendar import SEASON_MAP

        SEASONAL_MULT = {
            "monsoon": 1.8, "fog": 1.6, "harvest": 1.2,
            "summer": 1.1,  "normal": 1.0,
        }

        rows = []
        for i in range(1, days + 1):
            d = date.today() + timedelta(days=i)
            trend  = self._fallback_mean + self._fallback_slope * i
            season = SEASON_MAP.get(d.month, "normal")
            mult   = SEASONAL_MULT.get(season, 1.0)
            pred   = max(0.0, round(trend * mult, 1))
            rows.append({
                "date":                 d,
                "predicted_avg_delay":  pred,
                "lower_80":             round(pred * 0.75, 1),
                "upper_80":             round(pred * 1.25, 1),
            })
        return pd.DataFrame(rows)

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        print(f"  Forecaster saved: {path}")

    @classmethod
    def load(cls, path: str) -> "ZoneForecaster":
        return joblib.load(path)

    def __repr__(self) -> str:
        engine = "Prophet" if self.model else "fallback"
        return f"<ZoneForecaster zone={self.zone} engine={engine} fitted={self._is_fitted}>"