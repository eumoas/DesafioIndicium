import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import questao_6_1 as forecast  # noqa: E402


class UnifiedDatasetTests(unittest.TestCase):
    def test_exact_name_includes_all_matching_product_ids(self):
        products = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "name": [
                    forecast.TARGET_PRODUCT,
                    forecast.TARGET_PRODUCT,
                    f"{forecast.TARGET_PRODUCT}4",
                ],
            }
        )
        variants = pd.DataFrame(
            {
                "id": [10, 20, 30],
                "product_id": [1, 2, 3],
                "sku": ["A", "B", "C"],
            }
        )
        orders = pd.DataFrame(
            {
                "id": [100, 200, 300],
                "placed_at": pd.to_datetime(["2025-01-10", "2025-02-10", "2025-03-10"]),
                "status": ["paid", "paid", "paid"],
                "channel": ["pos", "pos", "pos"],
            }
        )
        items = pd.DataFrame(
            {
                "id": [1000, 2000, 3000],
                "order_id": [100, 200, 300],
                "product_variant_id": [10, 20, 30],
                "quantity": [2, 3, 100],
            }
        )

        unified = forecast.build_unified_dataset(
            products,
            variants,
            orders,
            items,
            forecast.TARGET_PRODUCT,
        )

        self.assertEqual(set(unified["product_id"]), {1, 2})
        self.assertEqual(unified["quantity"].sum(), 5)


class MonthlySeriesTests(unittest.TestCase):
    def test_month_without_sales_is_filled_with_zero(self):
        unified = pd.DataFrame(
            {
                "month": pd.to_datetime(["2025-01-01", "2025-03-01"]),
                "quantity": [5, 7],
            }
        )

        monthly = forecast.build_monthly_series(
            unified,
            pd.Timestamp("2025-01-15"),
            pd.Timestamp("2025-03-01"),
        )

        self.assertEqual(monthly["units_sold"].tolist(), [5, 0, 7])

    def test_split_respects_the_temporal_boundaries(self):
        monthly = pd.DataFrame(
            {
                "month": pd.date_range("2025-10-01", "2026-04-01", freq="MS"),
                "units_sold": [1, 2, 3, 4, 5, 6, 7],
            }
        )

        train, test = forecast.split_train_test(monthly)

        self.assertEqual(train["month"].max(), pd.Timestamp("2025-12-01"))
        self.assertEqual(
            test["month"].tolist(),
            list(pd.date_range("2026-01-01", "2026-03-01", freq="MS")),
        )


class ForecastTests(unittest.TestCase):
    def test_walk_forward_uses_only_values_observed_before_each_month(self):
        train = pd.DataFrame(
            {
                "month": pd.date_range("2025-10-01", periods=3, freq="MS"),
                "units_sold": [10, 20, 30],
            }
        )
        test = pd.DataFrame(
            {
                "month": pd.date_range("2026-01-01", periods=3, freq="MS"),
                "units_sold": [60, 90, 120],
            }
        )

        result = forecast.forecast_walk_forward(train, test)

        self.assertAlmostEqual(result.loc[0, "prediction"], 20.0)
        self.assertAlmostEqual(result.loc[1, "prediction"], 110 / 3)
        self.assertAlmostEqual(result.loc[2, "prediction"], 60.0)

    def test_mae_uses_unrounded_predictions(self):
        predictions = pd.DataFrame(
            {"absolute_error": [40 + 1 / 3, 14 + 1 / 3, 3 + 2 / 3]}
        )

        mae = forecast.mean_absolute_error(predictions)

        self.assertAlmostEqual(mae, 19 + 4 / 9)

    def test_window_larger_than_history_is_rejected(self):
        train = pd.DataFrame({"units_sold": [10, 20]})
        test = pd.DataFrame(
            {
                "month": [pd.Timestamp("2026-01-01")],
                "units_sold": [30],
            }
        )

        with self.assertRaises(forecast.ForecastError):
            forecast.forecast_walk_forward(train, test, window=3)


if __name__ == "__main__":
    unittest.main()
