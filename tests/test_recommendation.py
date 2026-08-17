import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import questao_7_1 as recommendation  # noqa: E402


class InteractionMatrixTests(unittest.TestCase):
    def test_repeated_purchase_is_still_a_binary_interaction(self):
        products = pd.DataFrame({"id": [1, 2], "name": ["Target", "Other"]})
        variants = pd.DataFrame({"id": [10, 20], "product_id": [1, 2]})
        orders = pd.DataFrame(
            {
                "id": [100, 200],
                "customer_id": [7, 7],
                "status": ["paid", "paid"],
            }
        )
        items = pd.DataFrame(
            {
                "order_id": [100, 200, 200],
                "product_variant_id": [10, 10, 20],
            }
        )

        matrix = recommendation.build_interaction_matrix(
            products, variants, orders, items
        )

        self.assertEqual(matrix.loc[7, 1], 1)
        self.assertEqual(matrix.loc[7, 2], 1)


class SimilarityTests(unittest.TestCase):
    def test_cosine_similarity_uses_customer_vectors(self):
        matrix = pd.DataFrame(
            {
                1: [1, 1, 0],
                2: [1, 0, 1],
                3: [0, 0, 0],
            },
            index=[10, 20, 30],
        )
        matrix.index.name = "customer_id"
        matrix.columns.name = "product_id"

        similarity = recommendation.calculate_product_similarity(matrix)

        self.assertAlmostEqual(similarity.loc[1, 2], 0.5)
        self.assertEqual(similarity.loc[1, 3], 0.0)

    def test_ranking_excludes_target_and_breaks_ties_by_product_id(self):
        products = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "name": [recommendation.TARGET_PRODUCT, "B", "C"],
            }
        )
        matrix = pd.DataFrame(
            {1: [1, 0], 2: [1, 0], 3: [1, 0]},
            index=[10, 20],
        )
        matrix.index.name = "customer_id"
        matrix.columns.name = "product_id"
        similarity = recommendation.calculate_product_similarity(matrix)

        ranking = recommendation.rank_similar_products(
            products, matrix, similarity, top_n=2
        )

        self.assertEqual(ranking["product_id"].tolist(), [2, 3])

    def test_target_without_buyers_is_rejected(self):
        products = pd.DataFrame(
            {"id": [1, 2], "name": [recommendation.TARGET_PRODUCT, "B"]}
        )
        matrix = pd.DataFrame({1: [0], 2: [1]}, index=[10])
        matrix.index.name = "customer_id"
        matrix.columns.name = "product_id"
        similarity = recommendation.calculate_product_similarity(matrix)

        with self.assertRaises(recommendation.RecommendationError):
            recommendation.rank_similar_products(products, matrix, similarity)


if __name__ == "__main__":
    unittest.main()
