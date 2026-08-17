#!/usr/bin/env python3
"""Gera o contrato de dados agregado usado pelo dashboard da LH Nautical."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean
from typing import Any, Optional, Sequence

import pandas as pd


ELITE_MIN_CATEGORIES = 13
FORECAST_PRODUCT = "Bússola de Bordo 702"
FORECAST_WINDOW_MONTHS = 3
FORECAST_TRAIN_END = pd.Period("2025-12", freq="M")
FORECAST_TEST_MONTHS = pd.period_range("2026-01", "2026-03", freq="M")
RECOMMENDATION_PRODUCT = "Motor de Popa 1949"
RECOMMENDATION_LIMIT = 5
WEEKDAYS_PT = {
    1: "Segunda-feira",
    2: "Terça-feira",
    3: "Quarta-feira",
    4: "Quinta-feira",
    5: "Sexta-feira",
    6: "Sábado",
    7: "Domingo",
}
REQUIRED_FILES = {
    "categories.csv",
    "customers.csv",
    "order_items.csv",
    "orders.csv",
    "product_variants.csv",
    "products.csv",
}


class DashboardDataError(Exception):
    """Erro esperado na leitura ou na transformação das fontes."""


@dataclass(frozen=True)
class SourceProfile:
    """Metadados não sensíveis de um CSV."""

    file: str
    rows: int
    columns: int


@dataclass(frozen=True)
class AnalyticalSources:
    """Recorte mínimo das fontes necessário para as agregações."""

    categories: pd.DataFrame
    customers: pd.DataFrame
    order_items: pd.DataFrame
    orders: pd.DataFrame
    variants: pd.DataFrame
    products: pd.DataFrame


def _round(value: Any, digits: int = 2) -> float:
    return round(float(value), digits)


def _percentage(numerator: Any, denominator: Any) -> float:
    if not denominator:
        return 0.0
    return _round(float(numerator) * 100.0 / float(denominator), 2)


def _format_integer(value: Any) -> str:
    return f"{int(value):,}".replace(",", ".")


def _format_decimal_pt(value: Any, digits: int = 2) -> str:
    formatted = f"{float(value):,.{digits}f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def discover_source_profiles(input_directory: Path) -> list[SourceProfile]:
    """Lê a estrutura e conta registros de todos os CSVs da raiz."""

    if not input_directory.is_dir():
        raise DashboardDataError(f"diretório não encontrado: {input_directory}")

    csv_paths = sorted(
        (
            path
            for path in input_directory.iterdir()
            if path.is_file() and path.suffix.casefold() == ".csv"
        ),
        key=lambda path: (path.name.casefold(), path.name),
    )
    if not csv_paths:
        raise DashboardDataError(f"nenhum CSV encontrado em {input_directory}")

    found_files = {path.name for path in csv_paths}
    missing = sorted(REQUIRED_FILES - found_files)
    if missing:
        raise DashboardDataError(f"fontes obrigatórias ausentes: {', '.join(missing)}")

    profiles: list[SourceProfile] = []
    for path in csv_paths:
        try:
            header = pd.read_csv(path, nrows=0)
            if header.columns.empty:
                raise DashboardDataError(f"{path.name} não possui cabeçalho")
            first_column = str(header.columns[0])
            row_count = sum(
                len(chunk)
                for chunk in pd.read_csv(
                    path,
                    usecols=[first_column],
                    chunksize=100_000,
                )
            )
        except (OSError, ValueError, pd.errors.ParserError) as error:
            raise DashboardDataError(f"falha ao inspecionar {path.name}: {error}") from error

        profiles.append(
            SourceProfile(
                file=path.name,
                rows=int(row_count),
                columns=int(len(header.columns)),
            )
        )

    return profiles


def _read_csv(
    input_directory: Path,
    filename: str,
    usecols: list[str],
    dtype: dict[str, str],
) -> pd.DataFrame:
    path = input_directory / filename
    try:
        return pd.read_csv(path, usecols=usecols, dtype=dtype)
    except (OSError, ValueError, pd.errors.ParserError) as error:
        raise DashboardDataError(f"falha ao ler {filename}: {error}") from error


def load_analytical_sources(input_directory: Path) -> AnalyticalSources:
    """Carrega apenas colunas analíticas; nenhum campo pessoal é lido."""

    categories = _read_csv(
        input_directory,
        "categories.csv",
        ["id", "name"],
        {"id": "int64", "name": "string"},
    )
    customers = _read_csv(
        input_directory,
        "customers.csv",
        ["id"],
        {"id": "int64"},
    )
    order_items = _read_csv(
        input_directory,
        "order_items.csv",
        ["id", "order_id", "product_variant_id", "quantity"],
        {
            "id": "int64",
            "order_id": "int64",
            "product_variant_id": "int64",
            "quantity": "int64",
        },
    )
    orders = _read_csv(
        input_directory,
        "orders.csv",
        [
            "id",
            "customer_id",
            "channel",
            "status",
            "subtotal",
            "discount_amount",
            "total",
            "placed_at",
        ],
        {
            "id": "int64",
            "customer_id": "int64",
            "channel": "string",
            "status": "string",
            "subtotal": "float64",
            "discount_amount": "float64",
            "total": "float64",
            "placed_at": "string",
        },
    )
    variants = _read_csv(
        input_directory,
        "product_variants.csv",
        ["id", "product_id"],
        {"id": "int64", "product_id": "int64"},
    )
    products = _read_csv(
        input_directory,
        "products.csv",
        ["id", "name", "category_id"],
        {"id": "int64", "name": "string", "category_id": "int64"},
    )

    try:
        orders["placed_at"] = pd.to_datetime(orders["placed_at"], errors="raise")
    except (TypeError, ValueError) as error:
        raise DashboardDataError(f"orders.placed_at contém data inválida: {error}") from error

    return AnalyticalSources(
        categories=categories,
        customers=customers,
        order_items=order_items,
        orders=orders,
        variants=variants,
        products=products,
    )


def _require_unique_key(data: pd.DataFrame, source: str) -> None:
    if data["id"].isna().any():
        raise DashboardDataError(f"{source}.id possui valor nulo")
    if data["id"].duplicated().any():
        raise DashboardDataError(f"{source}.id possui duplicidades")


def validate_sources(sources: AnalyticalSources) -> dict[str, int]:
    """Valida chaves necessárias e retorna contagens para os checks."""

    keyed_sources = (
        (sources.categories, "categories"),
        (sources.customers, "customers"),
        (sources.order_items, "order_items"),
        (sources.orders, "orders"),
        (sources.variants, "product_variants"),
        (sources.products, "products"),
    )
    for data, name in keyed_sources:
        _require_unique_key(data, name)

    missing_core = int(
        sources.orders[["placed_at", "status", "channel", "total"]]
        .isna()
        .sum()
        .sum()
    )
    if missing_core:
        raise DashboardDataError(
            f"orders possui {missing_core} ausências em campos analíticos centrais"
        )

    orphan_item_orders = int(
        (~sources.order_items["order_id"].isin(sources.orders["id"])).sum()
    )
    orphan_item_variants = int(
        (~sources.order_items["product_variant_id"].isin(sources.variants["id"])).sum()
    )
    orphan_variant_products = int(
        (~sources.variants["product_id"].isin(sources.products["id"])).sum()
    )
    orphan_product_categories = int(
        (~sources.products["category_id"].isin(sources.categories["id"])).sum()
    )
    orphan_order_customers = int(
        (~sources.orders["customer_id"].isin(sources.customers["id"])).sum()
    )
    orphan_total = sum(
        (
            orphan_item_orders,
            orphan_item_variants,
            orphan_variant_products,
            orphan_product_categories,
            orphan_order_customers,
        )
    )
    if orphan_total:
        raise DashboardDataError(
            f"foram encontradas {orphan_total} referências órfãs nas fontes analíticas"
        )

    arithmetic_delta = (
        sources.orders["subtotal"]
        - sources.orders["discount_amount"]
        - sources.orders["total"]
    ).abs()

    return {
        "missingCoreValues": missing_core,
        "duplicatePrimaryKeys": 0,
        "orphanReferences": orphan_total,
        "orderArithmeticDifferences": int(arithmetic_delta.gt(0.01).sum()),
    }


def build_item_context(sources: AnalyticalSources) -> pd.DataFrame:
    """Relaciona itens, variantes e produtos sem trazer campos pessoais."""

    variants = sources.variants.rename(
        columns={"id": "product_variant_id"}
    )[["product_variant_id", "product_id"]]
    products = sources.products.rename(
        columns={"id": "product_id", "name": "product_name"}
    )[["product_id", "product_name", "category_id"]]

    return sources.order_items.merge(
        variants,
        on="product_variant_id",
        how="inner",
        validate="many_to_one",
    ).merge(
        products,
        on="product_id",
        how="inner",
        validate="many_to_one",
    )


def _build_breakdown(orders: pd.DataFrame, dimension: str) -> list[dict[str, Any]]:
    grouped = (
        orders.groupby(dimension, sort=False, observed=True)
        .agg(orders=("id", "size"), revenue=("total", "sum"))
        .reset_index()
    )
    grouped["average_ticket"] = grouped["revenue"] / grouped["orders"]
    grouped = grouped.sort_values(
        ["orders", dimension], ascending=[False, True], ignore_index=True
    )

    total_orders = int(grouped["orders"].sum())
    total_revenue = float(grouped["revenue"].sum())
    return [
        {
            dimension: str(row[dimension]),
            "orders": int(row["orders"]),
            "revenue": _round(row["revenue"]),
            "averageTicket": _round(row["average_ticket"]),
            "orderSharePct": _percentage(row["orders"], total_orders),
            "revenueSharePct": _percentage(row["revenue"], total_revenue),
        }
        for _, row in grouped.iterrows()
    ]


def build_sales(orders: pd.DataFrame) -> dict[str, Any]:
    working = orders.assign(month=orders["placed_at"].dt.to_period("M"))
    monthly = (
        working.groupby("month", observed=True)
        .agg(orders=("id", "size"), revenue=("total", "sum"))
        .reindex(
            pd.period_range(working["month"].min(), working["month"].max(), freq="M"),
            fill_value=0,
        )
    )
    monthly.index.name = "month"
    monthly["average_ticket"] = monthly["revenue"].div(
        monthly["orders"].where(monthly["orders"].ne(0))
    ).fillna(0.0)

    return {
        "monthly": [
            {
                "month": str(month),
                "orders": int(row["orders"]),
                "revenue": _round(row["revenue"]),
                "averageTicket": _round(row["average_ticket"]),
            }
            for month, row in monthly.iterrows()
        ],
        "statuses": _build_breakdown(orders, "status"),
        "channels": _build_breakdown(orders, "channel"),
    }


def build_customers(
    sources: AnalyticalSources,
    item_context: pd.DataFrame,
) -> dict[str, Any]:
    order_metrics = (
        sources.orders.groupby("customer_id", sort=True)
        .agg(total_revenue=("total", "sum"), frequency=("id", "size"))
        .reset_index()
    )
    order_metrics["average_ticket"] = (
        order_metrics["total_revenue"] / order_metrics["frequency"]
    )

    item_customers = item_context.merge(
        sources.orders.rename(columns={"id": "order_id"})[
            ["order_id", "customer_id"]
        ],
        on="order_id",
        how="inner",
        validate="many_to_one",
    )
    diversity = (
        item_customers.groupby("customer_id", sort=True)["category_id"]
        .nunique()
        .rename("category_diversity")
        .reset_index()
    )

    customer_metrics = sources.customers.rename(columns={"id": "customer_id"}).merge(
        order_metrics,
        on="customer_id",
        how="left",
        validate="one_to_one",
    ).merge(
        diversity,
        on="customer_id",
        how="left",
        validate="one_to_one",
    )
    customer_metrics[["total_revenue", "frequency", "average_ticket"]] = (
        customer_metrics[["total_revenue", "frequency", "average_ticket"]].fillna(0)
    )
    customer_metrics["category_diversity"] = (
        customer_metrics["category_diversity"].fillna(0).astype("int64")
    )

    eligible = customer_metrics.loc[
        customer_metrics["category_diversity"].ge(ELITE_MIN_CATEGORIES)
    ].sort_values(
        ["average_ticket", "customer_id"],
        ascending=[False, True],
        ignore_index=True,
    )
    top_ten = eligible.head(10).copy()

    elite_top_ten = [
        {
            "rank": rank,
            "customerLabel": f"Cliente elite {rank:02d}",
            "totalRevenue": _round(row["total_revenue"]),
            "frequency": int(row["frequency"]),
            "averageTicket": _round(row["average_ticket"]),
            "categoryDiversity": int(row["category_diversity"]),
        }
        for rank, (_, row) in enumerate(top_ten.iterrows(), start=1)
    ]

    top_customer_ids = set(top_ten["customer_id"].astype(int))
    elite_items = item_customers.loc[
        item_customers["customer_id"].isin(top_customer_ids)
    ]
    category_totals = (
        elite_items.groupby("category_id", sort=True)["quantity"]
        .sum()
        .rename("quantity")
        .reset_index()
        .merge(
            sources.categories.rename(
                columns={"id": "category_id", "name": "category"}
            ),
            on="category_id",
            how="inner",
            validate="one_to_one",
        )
        .sort_values(["quantity", "category_id"], ascending=[False, True])
        .reset_index(drop=True)
    )
    total_quantity = float(category_totals["quantity"].sum())
    top_categories = [
        {
            "rank": rank,
            "category": str(row["category"]),
            "quantity": int(row["quantity"]),
            "sharePct": _percentage(row["quantity"], total_quantity),
        }
        for rank, (_, row) in enumerate(category_totals.iterrows(), start=1)
    ]

    diversity_distribution = (
        customer_metrics.groupby("category_diversity", sort=True)
        .size()
        .rename("customers")
        .reset_index()
    )

    return {
        "eliteTop10": elite_top_ten,
        "eligibility": {
            "rule": f"Pelo menos {ELITE_MIN_CATEGORIES} categorias diretas",
            "minimumCategories": ELITE_MIN_CATEGORIES,
            "registeredCustomers": int(len(customer_metrics)),
            "customersWithOrders": int(customer_metrics["frequency"].gt(0).sum()),
            "eligibleCustomers": int(len(eligible)),
            "eligibleSharePct": _percentage(len(eligible), len(customer_metrics)),
            "categoryDistribution": [
                {
                    "categories": int(row["category_diversity"]),
                    "customers": int(row["customers"]),
                }
                for _, row in diversity_distribution.iterrows()
            ],
        },
        "topEliteCategories": top_categories,
    }


def build_weekday_pos(orders: pd.DataFrame) -> list[dict[str, Any]]:
    calendar = pd.date_range(
        orders["placed_at"].min().normalize(),
        orders["placed_at"].max().normalize(),
        freq="D",
    )
    pos_orders = orders.loc[orders["channel"].eq("pos")].assign(
        sale_date=lambda frame: frame["placed_at"].dt.normalize()
    )
    daily_sales = pos_orders.groupby("sale_date")["total"].sum().reindex(
        calendar,
        fill_value=0.0,
    )
    daily = pd.DataFrame(
        {
            "revenue": daily_sales.to_numpy(dtype="float64"),
            "iso_weekday": calendar.dayofweek + 1,
        }
    )
    weekday = (
        daily.groupby("iso_weekday", sort=True)
        .agg(
            average_daily_sales=("revenue", "mean"),
            calendar_days=("revenue", "size"),
            zero_sales_days=("revenue", lambda values: int(values.eq(0).sum())),
        )
        .reset_index()
    )
    lowest_iso_weekday = int(
        weekday.sort_values(["average_daily_sales", "iso_weekday"]).iloc[0][
            "iso_weekday"
        ]
    )

    return [
        {
            "isoWeekday": int(row["iso_weekday"]),
            "weekday": WEEKDAYS_PT[int(row["iso_weekday"])],
            "averageDailySales": _round(row["average_daily_sales"]),
            "calendarDays": int(row["calendar_days"]),
            "zeroSalesDays": int(row["zero_sales_days"]),
            "isLowest": int(row["iso_weekday"]) == lowest_iso_weekday,
        }
        for _, row in weekday.iterrows()
    ]


def build_forecast(
    sources: AnalyticalSources,
    item_context: pd.DataFrame,
) -> dict[str, Any]:
    matching_products = sources.products.loc[
        sources.products["name"].eq(FORECAST_PRODUCT)
    ]
    if matching_products.empty:
        raise DashboardDataError(f"produto de previsão ausente: {FORECAST_PRODUCT}")

    target_items = item_context.loc[
        item_context["product_id"].isin(matching_products["id"])
    ].merge(
        sources.orders.rename(columns={"id": "order_id"})[
            ["order_id", "placed_at"]
        ],
        on="order_id",
        how="inner",
        validate="many_to_one",
    )
    target_items["month"] = target_items["placed_at"].dt.to_period("M")

    analysis_months = pd.period_range(
        sources.orders["placed_at"].min().to_period("M"),
        FORECAST_TEST_MONTHS.max(),
        freq="M",
    )
    monthly_units = target_items.groupby("month")["quantity"].sum().reindex(
        analysis_months,
        fill_value=0,
    )
    train = monthly_units.loc[monthly_units.index <= FORECAST_TRAIN_END]
    test = monthly_units.reindex(FORECAST_TEST_MONTHS)
    if test.isna().any() or len(train) < FORECAST_WINDOW_MONTHS:
        raise DashboardDataError("histórico insuficiente para a previsão mensal")

    history = train.astype(float).tolist()
    series: list[dict[str, Any]] = []
    for month, actual_value in test.items():
        prediction = fmean(history[-FORECAST_WINDOW_MONTHS:])
        actual = int(actual_value)
        series.append(
            {
                "month": str(month),
                "prediction": _round(prediction, 6),
                "actual": actual,
                "absoluteError": _round(abs(prediction - actual), 6),
            }
        )
        history.append(float(actual))

    mae = fmean(row["absoluteError"] for row in series)
    predicted_total = sum(row["prediction"] for row in series)
    actual_total = sum(row["actual"] for row in series)

    return {
        "product": FORECAST_PRODUCT,
        "matchingProductRecords": int(len(matching_products)),
        "method": "Média móvel de 3 meses, walk-forward",
        "windowMonths": FORECAST_WINDOW_MONTHS,
        "trainPeriod": {
            "start": str(train.index.min()),
            "end": str(train.index.max()),
        },
        "testPeriod": {
            "start": str(FORECAST_TEST_MONTHS.min()),
            "end": str(FORECAST_TEST_MONTHS.max()),
        },
        "mae": _round(mae, 6),
        "predictedTotal": _round(predicted_total, 6),
        "actualTotal": int(actual_total),
        "shortfall": _round(actual_total - predicted_total, 6),
        "series": series,
    }


def build_recommendations(
    sources: AnalyticalSources,
    item_context: pd.DataFrame,
) -> dict[str, Any]:
    target_products = sources.products.loc[
        sources.products["name"].eq(RECOMMENDATION_PRODUCT)
    ]
    if len(target_products) != 1:
        raise DashboardDataError(
            f"esperado um produto chamado {RECOMMENDATION_PRODUCT!r}; "
            f"encontrados {len(target_products)}"
        )
    target_id = int(target_products.iloc[0]["id"])

    interactions = item_context[["order_id", "product_id"]].merge(
        sources.orders.rename(columns={"id": "order_id"})[
            ["order_id", "customer_id"]
        ],
        on="order_id",
        how="inner",
        validate="many_to_one",
    )[["customer_id", "product_id"]].drop_duplicates()

    target_customers = interactions.loc[
        interactions["product_id"].eq(target_id), "customer_id"
    ]
    target_support = int(target_customers.nunique())
    if not target_support:
        raise DashboardDataError("produto de referência não possui compradores")

    supports = interactions.groupby("product_id")["customer_id"].nunique()
    common = (
        interactions.loc[interactions["customer_id"].isin(target_customers)]
        .groupby("product_id")["customer_id"]
        .nunique()
    )
    candidates = sources.products.rename(
        columns={"id": "product_id", "name": "product_name"}
    )[["product_id", "product_name"]].copy()
    candidates["product_customers"] = (
        candidates["product_id"].map(supports).fillna(0).astype("int64")
    )
    candidates["common_customers"] = (
        candidates["product_id"].map(common).fillna(0).astype("int64")
    )
    candidates["similarity"] = candidates.apply(
        lambda row: (
            row["common_customers"]
            / math.sqrt(target_support * row["product_customers"])
            if row["product_customers"]
            else 0.0
        ),
        axis=1,
    )
    ranking = candidates.loc[candidates["product_id"].ne(target_id)].sort_values(
        ["similarity", "product_id"],
        ascending=[False, True],
        ignore_index=True,
    ).head(RECOMMENDATION_LIMIT)

    return {
        "targetProduct": RECOMMENDATION_PRODUCT,
        "targetCustomers": target_support,
        "method": "Similaridade do cosseno sobre interações binárias cliente-produto",
        "items": [
            {
                "rank": rank,
                "product": str(row["product_name"]),
                "similarity": _round(row["similarity"], 8),
                "commonCustomers": int(row["common_customers"]),
                "productCustomers": int(row["product_customers"]),
            }
            for rank, (_, row) in enumerate(ranking.iterrows(), start=1)
        ],
    }


def build_quality(
    sources: AnalyticalSources,
    profiles: list[SourceProfile],
    validation: dict[str, int],
) -> dict[str, Any]:
    total_rows = sum(profile.rows for profile in profiles)
    used_files = REQUIRED_FILES
    checks = [
        {
            "id": "csv-inventory",
            "label": "Inventário CSV",
            "status": "pass",
            "value": len(profiles),
            "detail": f"{_format_integer(total_rows)} registros lidos nas fontes.",
        },
        {
            "id": "required-sources",
            "label": "Fontes analíticas",
            "status": "pass",
            "value": len(used_files),
            "detail": "Todas as fontes necessárias às métricas estão presentes.",
        },
        {
            "id": "primary-keys",
            "label": "Chaves principais",
            "status": "pass",
            "value": validation["duplicatePrimaryKeys"],
            "detail": "Nenhum ID nulo ou duplicado nas seis fontes analíticas.",
        },
        {
            "id": "foreign-keys",
            "label": "Referências entre fontes",
            "status": "pass",
            "value": validation["orphanReferences"],
            "detail": "Nenhuma referência órfã na cadeia pedido-item-produto-categoria.",
        },
        {
            "id": "core-completeness",
            "label": "Completude central",
            "status": "pass",
            "value": validation["missingCoreValues"],
            "detail": "Sem ausências em data, status, canal ou total de pedidos.",
        },
        {
            "id": "order-arithmetic",
            "label": "Coerência do total",
            "status": (
                "pass" if validation["orderArithmeticDifferences"] == 0 else "warning"
            ),
            "value": validation["orderArithmeticDifferences"],
            "detail": "Diferenças acima de R$ 0,01 em subtotal - desconto = total.",
        },
        {
            "id": "privacy",
            "label": "Privacidade da saída",
            "status": "pass",
            "value": 0,
            "detail": "Sem nomes de clientes, contatos, documentos ou endereços.",
        },
    ]

    source_rows = {profile.file: profile.rows for profile in profiles}
    pipeline = [
        {
            "step": 1,
            "label": "Descobrir",
            "status": "complete",
            "detail": f"{len(profiles)} CSVs inventariados na raiz do projeto.",
        },
        {
            "step": 2,
            "label": "Validar",
            "status": "complete",
            "detail": "Chaves, completude, aritmética e relacionamentos conferidos.",
        },
        {
            "step": 3,
            "label": "Agregar",
            "status": "complete",
            "detail": (
                f"{_format_integer(source_rows['orders.csv'])} pedidos transformados "
                "sem expor o grão transacional."
            ),
        },
        {
            "step": 4,
            "label": "Modelar",
            "status": "complete",
            "detail": "Regras validadas das questões 4, 5, 6 e 7 reproduzidas.",
        },
        {
            "step": 5,
            "label": "Publicar",
            "status": "complete",
            "detail": "Contrato JSON agregado e anonimizado para consumo local.",
        },
    ]

    return {
        "checks": checks,
        "sources": [
            {
                "file": profile.file,
                "rows": profile.rows,
                "columns": profile.columns,
                "usedForMetrics": profile.file in used_files,
            }
            for profile in profiles
        ],
        "pipeline": pipeline,
    }


def build_executive(
    sources: AnalyticalSources,
    customers: dict[str, Any],
    operations: dict[str, Any],
) -> dict[str, Any]:
    orders = sources.orders
    total_revenue = float(orders["total"].sum())
    average_ticket = total_revenue / len(orders)
    eligibility = customers["eligibility"]
    lowest_weekday = next(
        row for row in operations["weekdayPos"] if row["isLowest"]
    )
    forecast = operations["forecast"]
    top_category = customers["topEliteCategories"][0]

    return {
        "cards": [
            {
                "id": "gross-sales",
                "label": "Valor bruto registrado",
                "value": _round(total_revenue),
                "format": "currency",
                "detail": "Soma de orders.total; não é receita reconhecida",
            },
            {
                "id": "orders",
                "label": "Pedidos",
                "value": int(len(orders)),
                "format": "integer",
                "detail": "Sem filtro de status ou período",
            },
            {
                "id": "average-ticket",
                "label": "Ticket médio",
                "value": _round(average_ticket),
                "format": "currency",
                "detail": "Total bruto dividido por pedidos",
            },
            {
                "id": "customers",
                "label": "Clientes cadastrados",
                "value": int(len(sources.customers)),
                "format": "integer",
                "detail": "Identificadores não publicados",
            },
            {
                "id": "products",
                "label": "Produtos",
                "value": int(len(sources.products)),
                "format": "integer",
                "detail": "Catálogo consolidado",
            },
            {
                "id": "elite-eligibility",
                "label": "Elegíveis ao grupo elite",
                "value": eligibility["eligibleSharePct"],
                "format": "percent",
                "detail": f"{_format_integer(eligibility['eligibleCustomers'])} clientes",
            },
        ],
        "insights": [
            {
                "id": "elite-selectivity",
                "tone": "attention",
                "title": "O corte elite é pouco seletivo",
                "detail": (
                    f"{_format_decimal_pt(eligibility['eligibleSharePct'])}% dos clientes "
                    f"atingem {ELITE_MIN_CATEGORIES} categorias; o ranking é dominado "
                    "pelo ticket médio."
                ),
            },
            {
                "id": "elite-category",
                "tone": "positive",
                "title": f"{top_category['category']} lidera o grupo elite",
                "detail": (
                    f"{_format_integer(top_category['quantity'])} unidades somadas nos "
                    "dez clientes selecionados."
                ),
            },
            {
                "id": "weekday-pos",
                "tone": "neutral",
                "title": f"{lowest_weekday['weekday']} tem a menor média POS",
                "detail": (
                    "A média diária é "
                    f"R$ {_format_decimal_pt(lowest_weekday['averageDailySales'])}; "
                    "valor bruto isolado não sustenta uma decisão de fechamento."
                ),
            },
            {
                "id": "forecast",
                "tone": "attention",
                "title": "O baseline subestima o trimestre",
                "detail": (
                    f"MAE de {_format_decimal_pt(forecast['mae'])} unidades e déficit "
                    f"acumulado de {_format_decimal_pt(forecast['shortfall'])} unidades."
                ),
            },
        ],
    }


def build_metadata(
    sources: AnalyticalSources,
    profiles: list[SourceProfile],
) -> dict[str, Any]:
    statuses = sorted(str(value) for value in sources.orders["status"].unique())
    period_start = sources.orders["placed_at"].min().date().isoformat()
    period_end = sources.orders["placed_at"].max().date().isoformat()

    return {
        "title": "LH Nautical — Painel executivo",
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sourcePeriod": {
            "start": period_start,
            "end": period_end,
            "field": "orders.placed_at",
        },
        "sourceFiles": int(len(profiles)),
        "totalRecords": int(sum(profile.rows for profile in profiles)),
        "orderStatuses": statuses,
        "scope": "Snapshot integral, sem filtro de status",
        "displayCurrency": {
            "code": "BRL",
            "symbol": "R$",
            "assumption": (
                "Premissa de apresentação para a operação brasileira; orders não "
                "registra a moeda explicitamente."
            ),
        },
        "privacy": (
            "Somente métricas agregadas; o ranking de clientes usa rótulos por posição."
        ),
        "assumptions": [
            {
                "id": "display-currency",
                "title": "Moeda de apresentação",
                "detail": (
                    "Os valores são exibidos em BRL/R$ como premissa do painel; a "
                    "tabela orders não possui uma coluna de moeda."
                ),
            },
            {
                "id": "status-scope",
                "title": "Todos os status",
                "detail": (
                    f"{', '.join(statuses)} entram literalmente em todas as métricas, "
                    "pois não existe regra de elegibilidade confirmada."
                ),
            },
            {
                "id": "gross-sales",
                "title": "Valor bruto registrado",
                "detail": (
                    "A soma de orders.total não representa receita reconhecida; "
                    "pagamentos, notas e devoluções não ajustam o valor."
                ),
            },
            {
                "id": "elite-rule",
                "title": "Regra de elite",
                "detail": (
                    f"Cliente elegível compra em pelo menos {ELITE_MIN_CATEGORIES} "
                    "categorias diretas; o desempate usa a chave interna crescente."
                ),
            },
            {
                "id": "mixed-units",
                "title": "Quantidades de categoria",
                "detail": (
                    "A soma segue order_items.quantity e mistura unidades de medida "
                    "como UN, PC, M e L."
                ),
            },
            {
                "id": "weekday-calendar",
                "title": "Calendário POS",
                "detail": (
                    "Todos os dias entre a primeira e a última venda são considerados; "
                    "dias sem pedido POS recebem zero."
                ),
            },
            {
                "id": "forecast-policy",
                "title": "Previsão walk-forward",
                "detail": (
                    "Cada mês de 2026 usa os três meses reais anteriores; cadastros com "
                    f"nome exato {FORECAST_PRODUCT!r} são consolidados."
                ),
            },
            {
                "id": "recommendation-policy",
                "title": "Recomendação binária",
                "detail": (
                    "Compras repetidas contam uma vez por par cliente-produto e a "
                    "similaridade é calculada pelo cosseno."
                ),
            },
        ],
    }


def build_dashboard_data(input_directory: Path) -> dict[str, Any]:
    """Executa a transformação completa e devolve somente valores JSON-safe."""

    input_directory = input_directory.resolve()
    profiles = discover_source_profiles(input_directory)
    sources = load_analytical_sources(input_directory)
    validation = validate_sources(sources)
    item_context = build_item_context(sources)

    sales = build_sales(sources.orders)
    customers = build_customers(sources, item_context)
    operations = {
        "weekdayPos": build_weekday_pos(sources.orders),
        "forecast": build_forecast(sources, item_context),
        "recommendations": build_recommendations(sources, item_context),
    }
    quality = build_quality(sources, profiles, validation)
    executive = build_executive(sources, customers, operations)
    metadata = build_metadata(sources, profiles)

    return {
        "metadata": metadata,
        "executive": executive,
        "sales": sales,
        "customers": customers,
        "operations": operations,
        "quality": quality,
    }


def write_dashboard_data(output_path: Path, dashboard_data: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as output_file:
            json.dump(
                dashboard_data,
                output_file,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            output_file.write("\n")
        temporary_path.replace(output_path)
    except (OSError, TypeError, ValueError) as error:
        temporary_path.unlink(missing_ok=True)
        raise DashboardDataError(f"falha ao gravar {output_path}: {error}") from error


def parse_arguments(arguments: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera dashboard/public/data/dashboard.json a partir dos CSVs."
    )
    parser.add_argument(
        "input_directory",
        nargs="?",
        type=Path,
        default=Path("."),
        help="diretório que contém os 24 CSVs (padrão: diretório atual)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "arquivo de saída (padrão: "
            "<input_directory>/dashboard/public/data/dashboard.json)"
        ),
    )
    return parser.parse_args(arguments)


def main(arguments: Optional[Sequence[str]] = None) -> int:
    options = parse_arguments(arguments)
    output_path = options.output or (
        options.input_directory / "dashboard" / "public" / "data" / "dashboard.json"
    )
    try:
        dashboard_data = build_dashboard_data(options.input_directory)
        write_dashboard_data(output_path, dashboard_data)
    except DashboardDataError as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1

    metadata = dashboard_data["metadata"]
    print(
        f"Dashboard gerado em {output_path}: "
        f"{metadata['sourceFiles']} CSVs e "
        f"{metadata['totalRecords']} registros agregados."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
