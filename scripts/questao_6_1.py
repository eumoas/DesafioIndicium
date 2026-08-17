#!/usr/bin/env python3
"""Questão 6.1: cria e avalia o baseline mensal de média móvel."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from statistics import fmean
from typing import Optional, Sequence, Tuple

import pandas as pd


TARGET_PRODUCT = "Bússola de Bordo 702"
TRAIN_END_MONTH = pd.Timestamp("2025-12-01")
TEST_START_MONTH = pd.Timestamp("2026-01-01")
TEST_END_MONTH = pd.Timestamp("2026-03-01")
TEST_END_EXCLUSIVE = pd.Timestamp("2026-04-01")
MOVING_AVERAGE_WINDOW = 3


class ForecastError(Exception):
    """Erro esperado na preparação dos dados ou na previsão."""


def require_unique_key(data: pd.DataFrame, column: str, source_name: str) -> None:
    if data[column].isna().any():
        raise ForecastError(f"{source_name}.{column} possui valor nulo")

    duplicated = data.loc[data[column].duplicated(), column]
    if not duplicated.empty:
        examples = duplicated.head(3).tolist()
        raise ForecastError(f"{source_name}.{column} não é único; exemplos: {examples}")


def read_sources(
    input_directory: Path,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    source_paths = {
        "products": input_directory / "products.csv",
        "product_variants": input_directory / "product_variants.csv",
        "orders": input_directory / "orders.csv",
        "order_items": input_directory / "order_items.csv",
    }

    missing_files = [str(path) for path in source_paths.values() if not path.is_file()]
    if missing_files:
        raise ForecastError(f"arquivos não encontrados: {', '.join(missing_files)}")

    products = pd.read_csv(
        source_paths["products"],
        usecols=["id", "name"],
        dtype={"id": "int64", "name": "string"},
    )
    variants = pd.read_csv(
        source_paths["product_variants"],
        usecols=["id", "product_id", "sku"],
        dtype={"id": "int64", "product_id": "int64", "sku": "string"},
    )
    orders = pd.read_csv(
        source_paths["orders"],
        usecols=["id", "placed_at", "status", "channel"],
        dtype={"id": "int64", "status": "string", "channel": "string"},
    )
    order_items = pd.read_csv(
        source_paths["order_items"],
        usecols=["id", "order_id", "product_variant_id", "quantity"],
        dtype={
            "id": "int64",
            "order_id": "int64",
            "product_variant_id": "int64",
            "quantity": "int64",
        },
    )

    try:
        orders["placed_at"] = pd.to_datetime(orders["placed_at"], errors="raise")
    except (TypeError, ValueError) as error:
        raise ForecastError(
            f"orders.placed_at contém data inválida: {error}"
        ) from error

    for source_name, data in (
        ("products", products),
        ("product_variants", variants),
        ("orders", orders),
        ("order_items", order_items),
    ):
        require_unique_key(data, "id", source_name)

    return products, variants, orders, order_items


def build_unified_dataset(
    products: pd.DataFrame,
    variants: pd.DataFrame,
    orders: pd.DataFrame,
    order_items: pd.DataFrame,
    target_product: str,
) -> pd.DataFrame:
    # A igualdade exata evita incluir, por exemplo, "Bússola de Bordo 7024".
    target_products = products.loc[products["name"].eq(target_product)].rename(
        columns={"id": "product_id", "name": "product_name"}
    )
    if target_products.empty:
        raise ForecastError(f"produto não encontrado: {target_product!r}")

    target_variants = variants.loc[
        variants["product_id"].isin(target_products["product_id"])
    ].rename(columns={"id": "product_variant_id"})
    if target_variants.empty:
        raise ForecastError(f"nenhuma variante encontrada para {target_product!r}")

    relevant_items = order_items.loc[
        order_items["product_variant_id"].isin(target_variants["product_variant_id"])
    ].rename(columns={"id": "order_item_id"})
    if relevant_items.empty:
        raise ForecastError(f"nenhuma venda encontrada para {target_product!r}")

    order_columns = orders.rename(columns={"id": "order_id"})[
        ["order_id", "placed_at", "status", "channel"]
    ]

    unified = relevant_items.merge(
        target_variants[["product_variant_id", "product_id", "sku"]],
        on="product_variant_id",
        how="left",
        validate="many_to_one",
    )
    unified = unified.merge(
        target_products[["product_id", "product_name"]],
        on="product_id",
        how="left",
        validate="many_to_one",
    )
    unified = unified.merge(
        order_columns,
        on="order_id",
        how="left",
        validate="many_to_one",
    )

    if unified["placed_at"].isna().any():
        missing_orders = unified.loc[unified["placed_at"].isna(), "order_id"]
        raise ForecastError(
            f"itens apontam para pedidos inexistentes: {missing_orders.head(3).tolist()}"
        )

    unified["month"] = unified["placed_at"].dt.to_period("M").dt.to_timestamp()
    return unified[
        [
            "order_item_id",
            "order_id",
            "placed_at",
            "month",
            "status",
            "channel",
            "product_id",
            "product_name",
            "product_variant_id",
            "sku",
            "quantity",
        ]
    ].sort_values(["placed_at", "order_item_id"], ignore_index=True)


def build_monthly_series(
    unified: pd.DataFrame,
    analysis_start: pd.Timestamp,
    analysis_end: pd.Timestamp,
) -> pd.DataFrame:
    start_month = analysis_start.to_period("M").to_timestamp()
    end_month = analysis_end.to_period("M").to_timestamp()
    calendar = pd.date_range(start=start_month, end=end_month, freq="MS")

    monthly_sales = unified.groupby("month", sort=True)["quantity"].sum()
    monthly_sales = monthly_sales.reindex(calendar, fill_value=0)

    return pd.DataFrame(
        {
            "month": calendar,
            "units_sold": monthly_sales.to_numpy(dtype="int64"),
        }
    )


def split_train_test(
    monthly_series: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    train = monthly_series.loc[monthly_series["month"].le(TRAIN_END_MONTH)].copy()
    test = monthly_series.loc[
        monthly_series["month"].between(TEST_START_MONTH, TEST_END_MONTH)
    ].copy()

    expected_test_months = list(
        pd.date_range(TEST_START_MONTH, TEST_END_MONTH, freq="MS")
    )
    if test["month"].tolist() != expected_test_months:
        raise ForecastError("o conjunto de teste não contém janeiro a março de 2026")
    if len(train) < MOVING_AVERAGE_WINDOW:
        raise ForecastError("histórico insuficiente para a média móvel de 3 meses")

    return train, test


def forecast_walk_forward(
    train: pd.DataFrame,
    test: pd.DataFrame,
    window: int = MOVING_AVERAGE_WINDOW,
) -> pd.DataFrame:
    history = train["units_sold"].astype(float).tolist()
    predictions = []

    if window <= 0:
        raise ForecastError("a janela da média móvel deve ser positiva")
    if len(history) < window:
        raise ForecastError(f"histórico insuficiente para uma janela de {window} meses")

    for row in test.itertuples(index=False):
        prediction = fmean(history[-window:])
        actual = float(row.units_sold)
        predictions.append(
            {
                "month": row.month,
                "prediction": prediction,
                "actual": int(row.units_sold),
                "absolute_error": abs(prediction - actual),
            }
        )

        # O realizado só entra no histórico depois que o mês foi previsto.
        history.append(actual)

    return pd.DataFrame(predictions)


def mean_absolute_error(forecasts: pd.DataFrame) -> float:
    if forecasts.empty:
        raise ForecastError("não há previsões para calcular o MAE")
    return fmean(forecasts["absolute_error"].astype(float))


def write_outputs(
    output_directory: Path,
    unified: pd.DataFrame,
    monthly_series: pd.DataFrame,
    forecasts: pd.DataFrame,
) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)

    unified.to_csv(
        output_directory / "questao_6_dataset_unificado.csv",
        index=False,
        date_format="%Y-%m-%d %H:%M:%S",
    )

    monthly_output = monthly_series.copy()
    monthly_output["period"] = monthly_output["month"].map(
        lambda month: "train" if month <= TRAIN_END_MONTH else "test"
    )
    monthly_output["month"] = monthly_output["month"].dt.strftime("%Y-%m")
    monthly_output.to_csv(
        output_directory / "questao_6_vendas_mensais.csv",
        index=False,
    )

    forecast_output = forecasts.copy()
    forecast_output["month"] = forecast_output["month"].dt.strftime("%Y-%m")
    forecast_output.to_csv(
        output_directory / "questao_6_previsoes.csv",
        index=False,
        float_format="%.6f",
    )


def parse_arguments(arguments: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Avalia uma média móvel mensal para um produto."
    )
    parser.add_argument(
        "input_directory",
        nargs="?",
        type=Path,
        default=Path("."),
        help="diretório com os quatro CSVs (padrão: diretório atual)",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        help="diretório de saída (padrão: <input_directory>/outputs)",
    )
    parser.add_argument(
        "--target-product",
        default=TARGET_PRODUCT,
        help=f"nome exato do produto (padrão: {TARGET_PRODUCT})",
    )
    return parser.parse_args(arguments)


def main(arguments: Optional[Sequence[str]] = None) -> int:
    options = parse_arguments(arguments)
    output_directory = options.output_directory or options.input_directory / "outputs"

    try:
        products, variants, orders, order_items = read_sources(options.input_directory)
        unified = build_unified_dataset(
            products,
            variants,
            orders,
            order_items,
            options.target_product,
        )
        # Dados posteriores ao teste ficam fora até mesmo do arquivo de modelagem.
        unified = unified.loc[unified["placed_at"].lt(TEST_END_EXCLUSIVE)].copy()
        monthly_series = build_monthly_series(
            unified,
            orders["placed_at"].min(),
            TEST_END_MONTH,
        )
        train, test = split_train_test(monthly_series)
        forecasts = forecast_walk_forward(train, test)
        mae = mean_absolute_error(forecasts)
        write_outputs(output_directory, unified, monthly_series, forecasts)

    except (ForecastError, OSError, ValueError, pd.errors.ParserError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1

    product_ids = sorted(unified["product_id"].unique().tolist())
    if len(product_ids) > 1:
        print(
            f"Atenção: o nome exato corresponde aos product_id {product_ids}; "
            "todos foram consolidados."
        )

    display = forecasts.copy()
    display["month"] = display["month"].dt.strftime("%Y-%m")
    print(display.to_string(index=False, float_format=lambda value: f"{value:.2f}"))
    print(f"MAE: {mae:.2f} unidades")
    print(f"Arquivos gerados em: {output_directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
