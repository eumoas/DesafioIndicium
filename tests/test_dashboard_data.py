import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIRECTORY = PROJECT_ROOT / "data" / "raw"
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import build_dashboard_data as dashboard  # noqa: E402


class DashboardDataIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = dashboard.build_dashboard_data(RAW_DATA_DIRECTORY)

    def card(self, card_id):
        return next(
            card for card in self.data["executive"]["cards"] if card["id"] == card_id
        )

    def test_contract_shape_is_complete(self):
        self.assertEqual(
            set(self.data),
            {"metadata", "executive", "sales", "customers", "operations", "quality"},
        )
        self.assertEqual(set(self.data["executive"]), {"cards", "insights"})
        self.assertEqual(
            set(self.data["sales"]), {"monthly", "statuses", "channels"}
        )
        self.assertEqual(
            set(self.data["customers"]),
            {"eliteTop10", "eligibility", "topEliteCategories"},
        )
        self.assertEqual(
            set(self.data["operations"]),
            {"weekdayPos", "forecast", "recommendations"},
        )
        self.assertEqual(
            set(self.data["quality"]), {"checks", "sources", "pipeline"}
        )

    def test_source_inventory_and_central_counts_are_recalculated(self):
        metadata = self.data["metadata"]

        self.assertEqual(metadata["sourceFiles"], 24)
        self.assertEqual(metadata["totalRecords"], 433_424)
        self.assertEqual(metadata["sourcePeriod"]["start"], "2020-01-01")
        self.assertEqual(metadata["sourcePeriod"]["end"], "2026-12-31")
        self.assertEqual(metadata["displayCurrency"]["code"], "BRL")
        self.assertIn("Premissa", metadata["displayCurrency"]["assumption"])
        self.assertEqual(self.card("orders")["value"], 48_998)
        self.assertEqual(self.card("customers")["value"], 2_000)
        self.assertEqual(self.card("products")["value"], 500)
        self.assertAlmostEqual(self.card("gross-sales")["value"], 1_406_487_201.80)
        self.assertAlmostEqual(self.card("average-ticket")["value"], 28_704.99)

        source_rows = {
            source["file"]: source["rows"] for source in self.data["quality"]["sources"]
        }
        self.assertEqual(source_rows["orders.csv"], 48_998)
        self.assertEqual(source_rows["customers.csv"], 2_000)
        self.assertEqual(source_rows["products.csv"], 500)

    def test_sales_include_every_literal_status_and_reconcile(self):
        statuses = {
            row["status"]: row["orders"] for row in self.data["sales"]["statuses"]
        }

        self.assertEqual(
            statuses,
            {
                "paid": 34_365,
                "confirmed": 7_335,
                "cancelled": 4_847,
                "draft": 2_451,
            },
        )
        self.assertEqual(set(self.data["metadata"]["orderStatuses"]), set(statuses))
        self.assertEqual(sum(statuses.values()), 48_998)
        self.assertEqual(
            sum(row["orders"] for row in self.data["sales"]["channels"]),
            48_998,
        )
        self.assertEqual(
            sum(row["orders"] for row in self.data["sales"]["monthly"]),
            48_998,
        )
        self.assertEqual(len(self.data["sales"]["monthly"]), 84)
        self.assertAlmostEqual(
            sum(row["revenue"] for row in self.data["sales"]["monthly"]),
            self.card("gross-sales")["value"],
            places=2,
        )

    def test_elite_customer_metrics_match_the_validated_analysis(self):
        customers = self.data["customers"]
        eligibility = customers["eligibility"]

        self.assertEqual(len(customers["eliteTop10"]), 10)
        self.assertEqual(eligibility["minimumCategories"], 13)
        self.assertEqual(eligibility["eligibleCustomers"], 1_971)
        self.assertEqual(eligibility["eligibleSharePct"], 98.55)
        self.assertEqual(
            eligibility["categoryDistribution"],
            [
                {"categories": 11, "customers": 2},
                {"categories": 12, "customers": 27},
                {"categories": 13, "customers": 200},
                {"categories": 14, "customers": 1_771},
            ],
        )
        self.assertEqual(customers["eliteTop10"][0]["averageTicket"], 41_839.94)
        self.assertEqual(customers["topEliteCategories"][0]["category"], "Hélices")
        self.assertEqual(customers["topEliteCategories"][0]["quantity"], 492)

    def test_weekday_forecast_and_recommendations_match_validated_results(self):
        operations = self.data["operations"]
        lowest_weekday = next(
            row for row in operations["weekdayPos"] if row["isLowest"]
        )

        self.assertEqual(len(operations["weekdayPos"]), 7)
        self.assertEqual(
            sum(row["calendarDays"] for row in operations["weekdayPos"]), 2_557
        )
        self.assertEqual(lowest_weekday["weekday"], "Quinta-feira")
        self.assertAlmostEqual(lowest_weekday["averageDailySales"], 157_154.32)

        forecast = operations["forecast"]
        self.assertEqual(
            [row["actual"] for row in forecast["series"]], [79, 68, 60]
        )
        self.assertAlmostEqual(forecast["mae"], 19.444444)
        self.assertAlmostEqual(forecast["predictedTotal"], 148.666667)
        self.assertEqual(forecast["actualTotal"], 207)

        recommendations = operations["recommendations"]
        self.assertEqual(recommendations["targetCustomers"], 397)
        self.assertEqual(
            [row["product"] for row in recommendations["items"]],
            [
                "Motor de Popa 5331",
                "Cabo Náutico 2105",
                "Vela Mestra 1913",
                "Cabo Náutico 9048",
                "GPS Plotter 6249",
            ],
        )
        self.assertAlmostEqual(
            recommendations["items"][0]["similarity"], 0.25655258
        )

    def test_output_contains_no_customer_pii_or_raw_customer_identifier(self):
        forbidden_keys = {
            "customerId",
            "legalName",
            "tradeName",
            "taxId",
            "stateRegistration",
            "email",
            "phone",
            "address",
            "postalCode",
        }

        def collect_keys(value):
            if isinstance(value, dict):
                for key, nested in value.items():
                    yield key
                    yield from collect_keys(nested)
            elif isinstance(value, list):
                for nested in value:
                    yield from collect_keys(nested)

        keys = set(collect_keys(self.data))
        self.assertTrue(forbidden_keys.isdisjoint(keys))
        self.assertNotIn("@", json.dumps(self.data, ensure_ascii=False))
        self.assertTrue(
            all(
                row["customerLabel"] == f"Cliente elite {row['rank']:02d}"
                for row in self.data["customers"]["eliteTop10"]
            )
        )

    def test_quality_checks_and_json_serialization(self):
        self.assertTrue(
            all(check["status"] == "pass" for check in self.data["quality"]["checks"])
        )
        self.assertTrue(
            all(
                stage["status"] == "complete"
                for stage in self.data["quality"]["pipeline"]
            )
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "nested" / "dashboard.json"
            dashboard.write_dashboard_data(output, self.data)

            with output.open(encoding="utf-8") as output_file:
                restored = json.load(output_file)

        self.assertEqual(restored, self.data)


if __name__ == "__main__":
    unittest.main()
