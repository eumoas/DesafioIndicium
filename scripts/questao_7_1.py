#!/usr/bin/env python3
"""Constrói recomendações de produtos a partir de compras em comum."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Sequence, Tuple

import pandas as pd


TARGET_PRODUCT = "Motor de Popa 1949"
TOP_N = 5


class RecommendationError(Exception):
    """Erro esperado na preparação das interações ou no ranking."""


def read_sources(
    input_directory: Path,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    paths = {
        "products": input_directory / "products.csv",
        "variants": input_directory / "product_variants.csv",
        "orders": input_directory / "orders.csv",
        "items": input_directory / "order_items.csv",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise RecommendationError(f"arquivos não encontrados: {', '.join(missing)}")

    products = pd.read_csv(
        paths["products"],
        usecols=["id", "name"],
        dtype={"id": "int64", "name": "string"},
    )
    variants = pd.read_csv(
        paths["variants"],
        usecols=["id", "product_id"],
        dtype={"id": "int64", "product_id": "int64"},
    )
    orders = pd.read_csv(
        paths["orders"],
        usecols=["id", "customer_id", "status"],
        dtype={"id": "int64", "customer_id": "int64", "status": "string"},
    )
    items = pd.read_csv(
        paths["items"],
        usecols=["order_id", "product_variant_id"],
        dtype={"order_id": "int64", "product_variant_id": "int64"},
    )

    for source_name, data in (
        ("products", products),
        ("product_variants", variants),
        ("orders", orders),
    ):
        if data["id"].isna().any() or data["id"].duplicated().any():
            raise RecommendationError(f"{source_name}.id deve ser único e não nulo")

    return products, variants, orders, items


def build_interaction_matrix(
    products: pd.DataFrame,
    variants: pd.DataFrame,
    orders: pd.DataFrame,
    items: pd.DataFrame,
) -> pd.DataFrame:
    variant_keys = variants.rename(columns={"id": "product_variant_id"})[
        ["product_variant_id", "product_id"]
    ]
    order_keys = orders.rename(columns={"id": "order_id"})[
        ["order_id", "customer_id", "status"]
    ]

    interactions = items.merge(
        variant_keys,
        on="product_variant_id",
        how="left",
        validate="many_to_one",
    ).merge(
        order_keys,
        on="order_id",
        how="left",
        validate="many_to_one",
    )

    if interactions[["product_id", "customer_id"]].isna().any().any():
        raise RecommendationError("existem itens sem produto ou cliente correspondente")

    # O enunciado não define quais status representam compra, então nenhum é removido.
    # Uma compra repetida continua valendo apenas uma interação.
    unique_interactions = interactions.drop_duplicates(["customer_id", "product_id"])
    matrix = unique_interactions.assign(interaction=1).pivot(
        index="customer_id",
        columns="product_id",
        values="interaction",
    )

    customer_ids = sorted(orders["customer_id"].unique().tolist())
    product_ids = sorted(products["id"].unique().tolist())
    return (
        matrix.reindex(
            index=customer_ids,
            columns=product_ids,
            fill_value=0,
        )
        .fillna(0)
        .astype("int8")
    )


def calculate_product_similarity(matrix: pd.DataFrame) -> pd.DataFrame:
    product_vectors = matrix.T.astype("int64")
    common_customers = product_vectors.dot(product_vectors.T)
    norms = product_vectors.sum(axis=1).pow(0.5)
    norms = norms.where(norms.gt(0))

    return common_customers.div(norms, axis=0).div(norms, axis=1).fillna(0.0)


def rank_similar_products(
    products: pd.DataFrame,
    matrix: pd.DataFrame,
    similarity: pd.DataFrame,
    target_name: str = TARGET_PRODUCT,
    top_n: int = TOP_N,
) -> pd.DataFrame:
    target_rows = products.loc[products["name"].eq(target_name)]
    if len(target_rows) != 1:
        raise RecommendationError(
            f"esperado um produto com nome {target_name!r}; encontrados {len(target_rows)}"
        )

    target_id = int(target_rows.iloc[0]["id"])
    if target_id not in similarity.index:
        raise RecommendationError("produto de referência ausente na matriz")

    product_vectors = matrix.T.astype("int64")
    supports = product_vectors.sum(axis=1)
    if supports.loc[target_id] == 0:
        raise RecommendationError("produto de referência não possui compradores")
    common_customers = product_vectors.dot(product_vectors.loc[target_id])

    ranking = similarity.loc[target_id].rename("similarity").reset_index()
    ranking = ranking.loc[ranking["product_id"].ne(target_id)].merge(
        products.rename(columns={"id": "product_id", "name": "product_name"}),
        on="product_id",
        how="left",
        validate="one_to_one",
    )
    ranking["common_customers"] = ranking["product_id"].map(common_customers)
    ranking["product_customers"] = ranking["product_id"].map(supports)
    ranking["target_customers"] = int(supports.loc[target_id])

    # O ID crescente deixa o resultado determinístico caso haja empate.
    ranking = ranking.sort_values(
        ["similarity", "product_id"],
        ascending=[False, True],
        ignore_index=True,
    ).head(top_n)
    ranking.insert(0, "rank", range(1, len(ranking) + 1))
    return ranking


def write_outputs(
    output_directory: Path,
    matrix: pd.DataFrame,
    similarity: pd.DataFrame,
    ranking: pd.DataFrame,
) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    matrix.to_csv(output_directory / "questao_7_matriz_interacao.csv")
    similarity.to_csv(
        output_directory / "questao_7_similaridade_produtos.csv",
        float_format="%.8f",
    )
    ranking.to_csv(
        output_directory / "questao_7_top_5.csv",
        index=False,
        float_format="%.8f",
    )


def main(arguments: Optional[Sequence[str]] = None) -> int:
    arguments = list(arguments or sys.argv[1:])
    input_directory = Path(arguments[0]) if arguments else Path(".")
    output_directory = input_directory / "outputs"

    try:
        products, variants, orders, items = read_sources(input_directory)
        matrix = build_interaction_matrix(products, variants, orders, items)
        similarity = calculate_product_similarity(matrix)
        ranking = rank_similar_products(products, matrix, similarity)
        write_outputs(output_directory, matrix, similarity, ranking)
    except (RecommendationError, OSError, ValueError, pd.errors.ParserError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1

    print(ranking.to_string(index=False, float_format=lambda value: f"{value:.6f}"))
    print(f"Arquivos gerados em: {output_directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
