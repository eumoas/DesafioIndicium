#!/usr/bin/env python3
"""Gera o resumo executivo em PDF da LH Nautical.

O gerador prioriza ``dashboard/public/data/dashboard.json`` quando disponível e
mantém um fallback reproduzível a partir dos CSVs em ``data/raw``. A saída contém
apenas agregados; clientes são apresentados por aliases de ranking, sem PII.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple

import pandas as pd
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = ROOT / "dashboard" / "public" / "data" / "dashboard.json"
DEFAULT_OUTPUT = ROOT / "deliverables" / "LH_Nautical_Resumo_Executivo.pdf"
PROFILE_PHOTO = ROOT / "docs" / "assets" / "miriam-oliveira-aguiar-sobral.jpeg"
DASHBOARD_URL = "https://desafioindicium.eumoas.workers.dev/"
REPOSITORY_URL = "https://github.com/eumoas/DesafioIndicium"
LINKEDIN_URL = "https://www.linkedin.com/in/miriamaguiarsobral"

# Proporção 16:9 em pontos PDF: 13 1/3 x 7 1/2 polegadas.
PAGE_W = 960.0
PAGE_H = 540.0
MARGIN = 48.0
TOTAL_PAGES = 10

INK = HexColor("#102A3A")
NAVY = HexColor("#071E2B")
NAVY_2 = HexColor("#0D2D3E")
DASHBOARD_NAVY = HexColor("#05073F")
DASHBOARD_BLUE = HexColor("#245BF3")
DASHBOARD_LAVENDER = HexColor("#6D70FF")
CREAM = HexColor("#F5F2EA")
PAPER = HexColor("#FFFDFC")
WHITE = HexColor("#FFFFFF")
MUTED = HexColor("#63717A")
LINE = HexColor("#D7DED9")
TEAL = HexColor("#00A9A0")
TEAL_DARK = HexColor("#087F7A")
MINT = HexColor("#7DE2D1")
ORANGE = HexColor("#F08A5D")
YELLOW = HexColor("#F3C969")
RED = HexColor("#D85B5B")
SKY = HexColor("#76BCE5")
LAVENDER = HexColor("#A8A6E8")


def register_fonts() -> Dict[str, str]:
    """Registra Lato quando disponível e devolve aliases seguros."""

    candidates = {
        "regular": Path("/usr/share/fonts/truetype/lato/Lato-Regular.ttf"),
        "medium": Path("/usr/share/fonts/truetype/lato/Lato-Medium.ttf"),
        "semibold": Path("/usr/share/fonts/truetype/lato/Lato-Semibold.ttf"),
        "bold": Path("/usr/share/fonts/truetype/lato/Lato-Bold.ttf"),
        "black": Path("/usr/share/fonts/truetype/lato/Lato-Black.ttf"),
    }
    fallback = {
        "regular": "Helvetica",
        "medium": "Helvetica",
        "semibold": "Helvetica-Bold",
        "bold": "Helvetica-Bold",
        "black": "Helvetica-Bold",
    }
    resolved = dict(fallback)
    for key, path in candidates.items():
        if path.is_file():
            name = f"LH-{key}"
            try:
                pdfmetrics.registerFont(TTFont(name, str(path)))
                resolved[key] = name
            except Exception:
                resolved[key] = fallback[key]
    return resolved


FONTS = register_fonts()


def as_number(value: Any, default: float = 0.0) -> float:
    if value is None or isinstance(value, bool):
        return default
    try:
        if isinstance(value, str):
            cleaned = value.strip().replace("R$", "").replace(" ", "")
            if "," in cleaned and "." in cleaned:
                cleaned = cleaned.replace(".", "").replace(",", ".")
            elif "," in cleaned:
                cleaned = cleaned.replace(",", ".")
            value = cleaned
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    return int(round(as_number(value, float(default))))


def br_number(value: Any, decimals: int = 0) -> str:
    number = as_number(value)
    formatted = f"{number:,.{decimals}f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def compact_value(value: Any) -> str:
    number = as_number(value)
    absolute = abs(number)
    if absolute >= 1_000_000_000:
        return f"{br_number(number / 1_000_000_000, 2)} bi"
    if absolute >= 1_000_000:
        return f"{br_number(number / 1_000_000, 1)} mi"
    if absolute >= 1_000:
        return f"{br_number(number / 1_000, 1)} mil"
    return br_number(number, 0)


def br_date(value: Any) -> str:
    if value is None:
        return "—"
    try:
        parsed = pd.to_datetime(value)
        if getattr(parsed, "tzinfo", None) is not None:
            parsed = parsed.tz_convert("America/Sao_Paulo")
        return parsed.strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(value)


def month_label(value: Any) -> str:
    try:
        parsed = pd.to_datetime(value)
        names = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
        return f"{names[parsed.month - 1]}/{str(parsed.year)[2:]}"
    except (TypeError, ValueError):
        return str(value)


def pick(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    lowered = {str(key).lower(): value for key, value in mapping.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value is not None:
            return value
    return default


def rows(value: Any) -> List[Mapping[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, Mapping)]
    if isinstance(value, Mapping):
        for key in ("items", "data", "rows", "values", "months", "ranking"):
            nested = value.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, Mapping)]
        converted: List[Mapping[str, Any]] = []
        for key, nested in value.items():
            if isinstance(nested, Mapping):
                converted.append({"name": key, **nested})
            elif isinstance(nested, (int, float)):
                converted.append({"name": key, "value": nested})
        return converted
    return []


def count_csv_records(directory: Path) -> Tuple[int, int]:
    file_count = 0
    total = 0
    for path in sorted(directory.glob("*.csv")):
        file_count += 1
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            next(reader, None)
            total += sum(1 for _ in reader)
    return file_count, total


def build_fallback_data(root: Path) -> Dict[str, Any]:
    """Calcula todos os agregados necessários sem depender do dashboard."""

    raw_data_directory = root / "data" / "raw"
    required = [
        raw_data_directory / "orders.csv",
        raw_data_directory / "order_items.csv",
        raw_data_directory / "product_variants.csv",
        raw_data_directory / "products.csv",
        raw_data_directory / "categories.csv",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("fontes obrigatórias ausentes: " + ", ".join(missing))

    orders_df = pd.read_csv(
        raw_data_directory / "orders.csv",
        usecols=[
            "id",
            "order_number",
            "channel",
            "customer_id",
            "salesperson_id",
            "status",
            "subtotal",
            "discount_amount",
            "total",
            "placed_at",
            "created_at",
        ],
        parse_dates=["placed_at", "created_at"],
    )
    items_df = pd.read_csv(
        raw_data_directory / "order_items.csv",
        usecols=["id", "order_id", "product_variant_id", "quantity"],
    ).rename(columns={"id": "order_item_id"})
    variants_df = pd.read_csv(
        raw_data_directory / "product_variants.csv", usecols=["id", "product_id"]
    ).rename(columns={"id": "product_variant_id"})
    products_df = pd.read_csv(
        raw_data_directory / "products.csv", usecols=["id", "name", "category_id"]
    ).rename(columns={"id": "product_id", "name": "product_name"})
    categories_df = pd.read_csv(
        raw_data_directory / "categories.csv", usecols=["id", "name"]
    ).rename(columns={"id": "category_id", "name": "category_name"})

    orders_df["month"] = orders_df["placed_at"].dt.to_period("M").astype(str)
    monthly_df = (
        orders_df.groupby("month", as_index=False)
        .agg(orders=("id", "size"), value=("total", "sum"))
        .sort_values("month")
    )
    status_df = (
        orders_df.groupby("status", as_index=False)
        .agg(orders=("id", "size"), value=("total", "sum"))
        .sort_values("value", ascending=False)
    )
    channel_df = (
        orders_df.groupby("channel", as_index=False)
        .agg(orders=("id", "size"), value=("total", "sum"))
        .sort_values("value", ascending=False)
    )

    enriched_items = (
        items_df.merge(
            orders_df[["id", "customer_id"]].rename(columns={"id": "order_id"}),
            on="order_id",
            how="left",
            validate="many_to_one",
        )
        .merge(variants_df, on="product_variant_id", how="left", validate="many_to_one")
        .merge(products_df, on="product_id", how="left", validate="many_to_one")
    )
    customer_orders = (
        orders_df.groupby("customer_id", as_index=False)
        .agg(value=("total", "sum"), orders=("id", "nunique"), ticket=("total", "mean"))
    )
    diversity = (
        enriched_items.groupby("customer_id")["category_id"]
        .nunique()
        .rename("categories")
        .reset_index()
    )
    customer_metrics = customer_orders.merge(diversity, on="customer_id", how="left")
    eligible = customer_metrics.loc[customer_metrics["categories"].ge(13)].copy()
    elite = eligible.sort_values(
        ["ticket", "customer_id"], ascending=[False, True]
    ).head(10)
    elite_rows = []
    for rank, record in enumerate(elite.itertuples(index=False), start=1):
        elite_rows.append(
            {
                "rank": rank,
                "alias": f"Perfil {rank:02d}",
                "value": float(record.value),
                "orders": int(record.orders),
                "ticket": float(record.ticket),
                "categories": int(record.categories),
            }
        )
    elite_categories_df = (
        enriched_items.loc[enriched_items["customer_id"].isin(elite["customer_id"])]
        .merge(categories_df, on="category_id", how="left", validate="many_to_one")
        .groupby("category_name", as_index=False)["quantity"]
        .sum()
        .sort_values("quantity", ascending=False)
    )

    pos = orders_df.loc[orders_df["channel"].eq("pos"), ["placed_at", "total"]].copy()
    pos["day"] = pos["placed_at"].dt.normalize()
    pos_daily = pos.groupby("day")["total"].sum()
    full_days = pd.date_range(
        orders_df["placed_at"].min().normalize(),
        orders_df["placed_at"].max().normalize(),
        freq="D",
    )
    pos_calendar = pos_daily.reindex(full_days, fill_value=0).rename("value").to_frame()
    pos_calendar["weekday"] = pos_calendar.index.dayofweek
    weekday_names = [
        "Segunda-feira",
        "Terça-feira",
        "Quarta-feira",
        "Quinta-feira",
        "Sexta-feira",
        "Sábado",
        "Domingo",
    ]
    weekday_rows = []
    for index, weekday_name in enumerate(weekday_names):
        subset = pos_calendar.loc[pos_calendar["weekday"].eq(index), "value"]
        weekday_rows.append(
            {
                "weekday": weekday_name,
                "average": float(subset.mean()),
                "days": int(subset.size),
                "zeroDays": int(subset.eq(0).sum()),
            }
        )

    forecast_path = root / "outputs" / "questao_6_previsoes.csv"
    forecast_rows: List[Dict[str, Any]] = []
    if forecast_path.is_file():
        forecast_df = pd.read_csv(forecast_path)
        for record in forecast_df.to_dict("records"):
            forecast_rows.append(
                {
                    "month": str(record["month"]),
                    "prediction": as_number(record["prediction"]),
                    "actual": as_number(record["actual"]),
                    "absoluteError": as_number(record["absolute_error"]),
                }
            )
    if not forecast_rows:
        forecast_rows = [
            {"month": "2026-01", "prediction": 38.666667, "actual": 79, "absoluteError": 40.333333},
            {"month": "2026-02", "prediction": 53.666667, "actual": 68, "absoluteError": 14.333333},
            {"month": "2026-03", "prediction": 56.333333, "actual": 60, "absoluteError": 3.666667},
        ]

    recommendation_path = root / "outputs" / "questao_7_top_5.csv"
    recommendation_rows: List[Dict[str, Any]] = []
    if recommendation_path.is_file():
        recommendation_df = pd.read_csv(recommendation_path)
        for record in recommendation_df.to_dict("records"):
            recommendation_rows.append(
                {
                    "rank": as_int(record.get("rank")),
                    "product": str(record.get("product_name", "Produto")),
                    "similarity": as_number(record.get("similarity")),
                    "commonCustomers": as_int(record.get("common_customers")),
                    "productCustomers": as_int(record.get("product_customers")),
                    "targetCustomers": as_int(record.get("target_customers")),
                }
            )

    csv_count, csv_records = count_csv_records(raw_data_directory)
    total_orders = len(orders_df)
    value_total = float(orders_df["total"].sum())
    semantic_status_orders = int(orders_df["status"].isin(["cancelled", "draft"]).sum())
    arithmetic_diff = (
        orders_df["subtotal"] - orders_df["discount_amount"] - orders_df["total"]
    ).abs()
    max_date = orders_df["placed_at"].max()
    future_orders = int((orders_df["placed_at"].dt.date > date.today()).sum())

    return {
        "metadata": {
            "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
            "sourcePeriod": {
                "start": orders_df["placed_at"].min().isoformat(),
                "end": max_date.isoformat(),
            },
            "sourceFiles": csv_count,
            "totalRecords": csv_records,
            "sourceMode": "csv_fallback",
        },
        "executive": {
            "orders": total_orders,
            "recordedValue": value_total,
            "customers": int(orders_df["customer_id"].nunique()),
            "averageTicket": float(orders_df["total"].mean()),
        },
        "sales": {
            "monthly": monthly_df.to_dict("records"),
            "statuses": status_df.to_dict("records"),
            "channels": channel_df.to_dict("records"),
        },
        "customers": {
            "eliteTop10": elite_rows,
            "eligibility": {
                "eligible": int(len(eligible)),
                "total": int(len(customer_metrics)),
                "percent": float(100 * len(eligible) / max(len(customer_metrics), 1)),
                "minimumCategories": 13,
            },
            "topEliteCategories": [
                {"category": str(record.category_name), "quantity": as_number(record.quantity)}
                for record in elite_categories_df.head(6).itertuples(index=False)
            ],
        },
        "operations": {
            "weekdayPos": weekday_rows,
            "forecast": {
                "target": "Bússola de Bordo 702",
                "rows": forecast_rows,
                "mae": sum(row["absoluteError"] for row in forecast_rows) / max(len(forecast_rows), 1),
            },
            "recommendations": {
                "target": "Motor de Popa 1949",
                "rows": recommendation_rows,
            },
        },
        "quality": {
            "checks": [
                {
                    "label": "Campos centrais",
                    "status": "ok" if not orders_df[["total", "created_at"]].isna().any().any() else "attention",
                    "evidence": f"{int(orders_df['total'].isna().sum())} nulos em total; {int(orders_df['created_at'].isna().sum())} em created_at",
                },
                {
                    "label": "Unicidade observada",
                    "status": "ok" if not orders_df[["id", "order_number"]].duplicated().any() else "attention",
                    "evidence": f"{int(orders_df['id'].duplicated().sum())} IDs e {int(orders_df['order_number'].duplicated().sum())} números duplicados",
                },
                {
                    "label": "Coerência aritmética",
                    "status": "ok" if not arithmetic_diff.ge(0.01).any() else "attention",
                    "evidence": f"{int(arithmetic_diff.ge(0.01).sum())} divergências de pelo menos 1 centavo",
                },
                {
                    "label": "Regra de status",
                    "status": "attention",
                    "evidence": f"{br_number(semantic_status_orders)} pedidos em draft/cancelled ({br_number(100 * semantic_status_orders / total_orders, 1)}%)",
                },
                {
                    "label": "Data de corte",
                    "status": "attention" if future_orders else "ok",
                    "evidence": (
                        f"{br_number(future_orders)} pedidos após {br_date(date.today())}"
                        if future_orders
                        else "nenhum registro posterior à data de geração"
                    ),
                },
            ],
            "semanticStatusOrders": semantic_status_orders,
            "futureOrders": future_orders,
        },
    }


def normalize_monthly(value: Any) -> List[Dict[str, Any]]:
    normalized = []
    for item in rows(value):
        month = pick(item, "month", "period", "date", "mes")
        amount = pick(
            item,
            "value",
            "revenue",
            "recordedValue",
            "registeredValue",
            "totalValue",
            "amount",
            "total",
        )
        if month is None or amount is None:
            continue
        normalized.append(
            {
                "month": str(month)[:7],
                "value": as_number(amount),
                "orders": as_int(pick(item, "orders", "orderCount", "count", "pedidos")),
            }
        )
    return sorted(normalized, key=lambda item: item["month"])


def normalize_breakdown(value: Any, dimension: str) -> List[Dict[str, Any]]:
    normalized = []
    label_keys = (dimension, "name", "label", "key")
    for item in rows(value):
        label = pick(item, *label_keys)
        amount = pick(
            item,
            "value",
            "revenue",
            "recordedValue",
            "registeredValue",
            "totalValue",
            "amount",
            "total",
        )
        if label is None or amount is None:
            continue
        normalized.append(
            {
                dimension: str(label),
                "value": as_number(amount),
                "orders": as_int(pick(item, "orders", "orderCount", "count", "pedidos")),
            }
        )
    return sorted(normalized, key=lambda item: item["value"], reverse=True)


def normalize_elite(value: Any) -> List[Dict[str, Any]]:
    normalized = []
    for rank, item in enumerate(rows(value), start=1):
        ticket = pick(item, "ticket", "averageTicket", "avgTicket", "ticketMedio")
        if ticket is None:
            continue
        normalized.append(
            {
                "rank": as_int(pick(item, "rank", "position"), rank),
                "alias": f"Perfil {rank:02d}",
                "ticket": as_number(ticket),
                "value": as_number(
                    pick(item, "value", "recordedValue", "totalValue", "totalRevenue", "total")
                ),
                "orders": as_int(pick(item, "orders", "frequency", "orderCount", "frequencia")),
                "categories": as_int(
                    pick(
                        item,
                        "categories",
                        "categoryCount",
                        "categoryDiversity",
                        "diversity",
                        "diversidade",
                    )
                ),
            }
        )
    return sorted(normalized, key=lambda item: (item["rank"], -item["ticket"]))[:10]


def normalize_categories(value: Any) -> List[Dict[str, Any]]:
    normalized = []
    for item in rows(value):
        label = pick(item, "category", "categoryName", "name", "label")
        quantity = pick(item, "quantity", "units", "value", "totalQuantity")
        if label is not None and quantity is not None:
            normalized.append({"category": str(label), "quantity": as_number(quantity)})
    return sorted(normalized, key=lambda item: item["quantity"], reverse=True)


def normalize_weekdays(value: Any) -> List[Dict[str, Any]]:
    normalized = []
    for item in rows(value):
        label = pick(item, "weekday", "weekdayName", "day", "name", "label")
        average = pick(
            item,
            "average",
            "avg",
            "averageDailySales",
            "avgRecordedValue",
            "averageValue",
            "value",
        )
        if label is None or average is None:
            continue
        normalized.append(
            {
                "weekday": str(label),
                "average": as_number(average),
                "days": as_int(pick(item, "days", "calendarDays", "dayCount")),
                "zeroDays": as_int(
                    pick(item, "zeroDays", "zeroSalesDays", "daysWithoutSales", "noSalesDays")
                ),
            }
        )
    order = {name: index for index, name in enumerate(["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"])}
    return sorted(
        normalized,
        key=lambda item: next(
            (index for name, index in order.items() if name in item["weekday"].lower()), 99
        ),
    )


def normalize_forecast(value: Any) -> Tuple[List[Dict[str, Any]], Optional[float], Optional[str]]:
    container = value if isinstance(value, Mapping) else {}
    normalized = []
    forecast_rows = container.get("series") if isinstance(container.get("series"), list) else value
    for item in rows(forecast_rows):
        month = pick(item, "month", "period", "date", "mes")
        prediction = pick(item, "prediction", "forecast", "predicted", "previsao")
        actual = pick(item, "actual", "realized", "observed", "real")
        if month is None or prediction is None or actual is None:
            continue
        pred = as_number(prediction)
        real = as_number(actual)
        normalized.append(
            {
                "month": str(month)[:7],
                "prediction": pred,
                "actual": real,
                "absoluteError": as_number(pick(item, "absoluteError", "absError", "error"), abs(real - pred)),
            }
        )
    mae = pick(container, "mae", "meanAbsoluteError") if container else None
    target = pick(container, "target", "product", "productName") if container else None
    return normalized, (as_number(mae) if mae is not None else None), (str(target) if target else None)


def normalize_recommendations(value: Any) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    container = value if isinstance(value, Mapping) else {}
    normalized = []
    for rank, item in enumerate(rows(value), start=1):
        product = pick(item, "product", "productName", "name", "label")
        similarity = pick(item, "similarity", "score", "cosineSimilarity")
        if product is None or similarity is None:
            continue
        normalized.append(
            {
                "rank": as_int(pick(item, "rank", "position"), rank),
                "product": str(product),
                "similarity": as_number(similarity),
                "commonCustomers": as_int(pick(item, "commonCustomers", "sharedCustomers", "intersection")),
                "productCustomers": as_int(pick(item, "productCustomers", "support")),
                "targetCustomers": as_int(pick(item, "targetCustomers", "targetSupport")),
            }
        )
    target = pick(container, "target", "targetProduct", "productName") if container else None
    return sorted(normalized, key=lambda item: item["rank"])[:5], (str(target) if target else None)


def overlay_dashboard(base: MutableMapping[str, Any], dashboard: Mapping[str, Any]) -> MutableMapping[str, Any]:
    """Sobrepõe dados normalizados do contrato do dashboard ao fallback."""

    metadata = dashboard.get("metadata")
    if isinstance(metadata, Mapping):
        for key in ("generatedAt", "sourcePeriod", "sourceFiles", "totalRecords", "assumptions"):
            if metadata.get(key) is not None:
                base["metadata"][key] = metadata[key]
        base["metadata"]["sourceMode"] = "dashboard_json"

    executive = dashboard.get("executive")
    if isinstance(executive, Mapping):
        direct_keys = {
            "orders": ("orders", "totalOrders", "orderCount"),
            "recordedValue": ("recordedValue", "totalRecordedValue", "totalValue"),
            "customers": ("customers", "totalCustomers", "customerCount"),
            "averageTicket": ("averageTicket", "avgTicket"),
        }
        for target_key, source_keys in direct_keys.items():
            found = pick(executive, *source_keys)
            if found is not None:
                base["executive"][target_key] = as_number(found)
        cards = rows(executive.get("cards"))
        for card in cards:
            label = str(pick(card, "label", "title", "name", default="")).lower()
            value = pick(card, "rawValue", "numericValue", "value")
            if value is None:
                continue
            if "pedido" in label:
                base["executive"]["orders"] = as_number(value, base["executive"]["orders"])
            elif "cliente" in label:
                base["executive"]["customers"] = as_number(value, base["executive"]["customers"])
            elif "ticket" in label:
                base["executive"]["averageTicket"] = as_number(value, base["executive"]["averageTicket"])
            elif "valor" in label:
                base["executive"]["recordedValue"] = as_number(value, base["executive"]["recordedValue"])

    sales = dashboard.get("sales")
    if isinstance(sales, Mapping):
        monthly = normalize_monthly(sales.get("monthly"))
        statuses = normalize_breakdown(sales.get("statuses"), "status")
        channels = normalize_breakdown(sales.get("channels"), "channel")
        if monthly:
            base["sales"]["monthly"] = monthly
        if statuses:
            base["sales"]["statuses"] = statuses
        if channels:
            base["sales"]["channels"] = channels

    customer_data = dashboard.get("customers")
    if isinstance(customer_data, Mapping):
        elite = normalize_elite(customer_data.get("eliteTop10"))
        categories = normalize_categories(customer_data.get("topEliteCategories"))
        if elite:
            base["customers"]["eliteTop10"] = elite
        if categories:
            base["customers"]["topEliteCategories"] = categories
        eligibility = customer_data.get("eligibility")
        if isinstance(eligibility, Mapping):
            normalized_eligibility = dict(base["customers"]["eligibility"])
            key_map = {
                "eligible": ("eligible", "eligibleCustomers", "count"),
                "total": ("total", "totalCustomers", "registeredCustomers", "population"),
                "percent": ("percent", "percentage", "eligiblePercent", "eligibleSharePct"),
                "minimumCategories": ("minimumCategories", "threshold", "minCategories"),
            }
            for target_key, source_keys in key_map.items():
                found = pick(eligibility, *source_keys)
                if found is not None:
                    normalized_eligibility[target_key] = as_number(found)
            base["customers"]["eligibility"] = normalized_eligibility

    operations = dashboard.get("operations")
    if isinstance(operations, Mapping):
        weekdays = normalize_weekdays(operations.get("weekdayPos"))
        forecast_rows, mae, forecast_target = normalize_forecast(operations.get("forecast"))
        recommendation_rows, recommendation_target = normalize_recommendations(operations.get("recommendations"))
        if weekdays:
            base["operations"]["weekdayPos"] = weekdays
        if forecast_rows:
            base["operations"]["forecast"]["rows"] = forecast_rows
        if mae is not None:
            base["operations"]["forecast"]["mae"] = mae
        if forecast_target:
            base["operations"]["forecast"]["target"] = forecast_target
        if recommendation_rows:
            base["operations"]["recommendations"]["rows"] = recommendation_rows
        if recommendation_target:
            base["operations"]["recommendations"]["target"] = recommendation_target

    quality = dashboard.get("quality")
    if isinstance(quality, Mapping):
        quality_checks = rows(quality.get("checks"))
        if quality_checks:
            normalized_checks = []
            for item in quality_checks:
                normalized_checks.append(
                    {
                        "label": str(pick(item, "label", "name", "check", default="Verificação")),
                        "status": str(pick(item, "status", "state", "result", default="attention")).lower(),
                        "evidence": str(pick(item, "evidence", "detail", "description", "value", default="")),
                    }
                )
            base["quality"]["checks"] = normalized_checks
    return base


def load_report_data(root: Path, dashboard_path: Path) -> Dict[str, Any]:
    data = build_fallback_data(root)
    if dashboard_path.is_file():
        try:
            with dashboard_path.open("r", encoding="utf-8") as handle:
                dashboard = json.load(handle)
            if not isinstance(dashboard, Mapping):
                raise ValueError("a raiz do JSON deve ser um objeto")
            data = dict(overlay_dashboard(deepcopy(data), dashboard))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            print(
                f"Aviso: dashboard.json não pôde ser utilizado ({error}); fallback aos CSVs.",
                file=sys.stderr,
            )
    return data


def split_lines(text: Any, font: str, size: float, max_width: float) -> List[str]:
    paragraphs = str(text).splitlines() or [""]
    lines: List[str] = []
    for paragraph in paragraphs:
        if not paragraph:
            lines.append("")
            continue
        words = paragraph.split()
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if pdfmetrics.stringWidth(candidate, font, size) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


class ExecutiveReport:
    def __init__(self, output: Path, data: Mapping[str, Any]) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        self.output = output
        self.data = data
        self.c = canvas.Canvas(str(output), pagesize=(PAGE_W, PAGE_H), pageCompression=1)
        self.c.setTitle("LH Nautical — Resumo Executivo")
        self.c.setSubject("Síntese executiva baseada em dados operacionais agregados")
        self.c.setAuthor("Miriam Oliveira de Aguiar Sobral — Cientista de Dados")
        self.page_number = 0

    def rect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        fill: Color,
        radius: float = 12,
        stroke: Optional[Color] = None,
        stroke_width: float = 0.8,
    ) -> None:
        self.c.saveState()
        self.c.setFillColor(fill)
        if stroke is None:
            self.c.setStrokeColor(fill)
            self.c.setLineWidth(0)
        else:
            self.c.setStrokeColor(stroke)
            self.c.setLineWidth(stroke_width)
        self.c.roundRect(x, y, width, height, radius, fill=1, stroke=1 if stroke else 0)
        self.c.restoreState()

    def label(
        self,
        text: Any,
        x: float,
        y: float,
        size: float = 10,
        color: Color = INK,
        font: str = "regular",
        align: str = "left",
    ) -> None:
        self.c.setFillColor(color)
        self.c.setFont(FONTS[font], size)
        value = str(text)
        if align == "right":
            self.c.drawRightString(x, y, value)
        elif align == "center":
            self.c.drawCentredString(x, y, value)
        else:
            self.c.drawString(x, y, value)

    def paragraph(
        self,
        text: Any,
        x: float,
        y: float,
        width: float,
        size: float = 10,
        leading: Optional[float] = None,
        color: Color = INK,
        font: str = "regular",
        max_lines: Optional[int] = None,
    ) -> float:
        leading = leading or size * 1.35
        lines = split_lines(text, FONTS[font], size, width)
        if max_lines is not None and len(lines) > max_lines:
            lines = lines[:max_lines]
            last = lines[-1]
            while last and pdfmetrics.stringWidth(last + "…", FONTS[font], size) > width:
                last = last[:-1]
            lines[-1] = last.rstrip() + "…"
        cursor = y
        for line in lines:
            self.label(line, x, cursor, size=size, color=color, font=font)
            cursor -= leading
        return cursor

    def lh_mark(self, x: float, y: float, size: float) -> None:
        """Desenha a marca náutica do dashboard sem depender de rasterização."""

        self.c.saveState()
        self.c.setFillColor(DASHBOARD_NAVY)
        self.c.setStrokeColor(Color(0.67, 0.89, 0.90, alpha=0.28))
        self.c.setLineWidth(0.8)
        self.c.roundRect(
            x,
            y,
            size,
            size,
            size * 0.24,
            fill=1,
            stroke=1,
        )

        center_x = x + size / 2
        center_y = y + size / 2
        self.c.setStrokeColor(Color(0.67, 0.89, 0.90, alpha=0.62))
        self.c.setLineWidth(max(0.7, size * 0.032))
        self.c.circle(center_x, center_y, size * 0.30, fill=0, stroke=1)

        tick = size * 0.12
        outer = size * 0.36
        self.c.setStrokeColor(HexColor("#BBBAFB"))
        self.c.setLineCap(1)
        self.c.line(center_x, center_y + outer, center_x, center_y + outer - tick)
        self.c.line(center_x, center_y - outer, center_x, center_y - outer + tick)
        self.c.line(center_x - outer, center_y, center_x - outer + tick, center_y)
        self.c.line(center_x + outer, center_y, center_x + outer - tick, center_y)

        pointer = self.c.beginPath()
        pointer.moveTo(x + size * 0.60, y + size * 0.69)
        pointer.lineTo(x + size * 0.54, y + size * 0.47)
        pointer.lineTo(x + size * 0.31, y + size * 0.34)
        pointer.lineTo(x + size * 0.43, y + size * 0.57)
        pointer.close()
        self.c.setFillColor(DASHBOARD_BLUE)
        self.c.setStrokeColor(WHITE)
        self.c.setLineWidth(max(0.6, size * 0.025))
        self.c.drawPath(pointer, fill=1, stroke=1)
        self.c.setFillColor(WHITE)
        self.c.circle(center_x, center_y, size * 0.046, fill=1, stroke=0)
        self.c.restoreState()

    def link_button(
        self,
        x: float,
        y: float,
        width: float,
        label: str,
        url: str,
        fill: Color = DASHBOARD_BLUE,
        text_color: Color = WHITE,
        font_size: float = 7.5,
    ) -> None:
        """Renderiza um acesso visível e cria a anotação clicável no PDF."""

        height = 30.0
        self.rect(
            x,
            y,
            width,
            height,
            fill,
            9,
            Color(1, 1, 1, alpha=0.18),
        )
        self.label(label, x + width / 2, y + 10.5, font_size, text_color, "bold", "center")
        self.c.linkURL(url, (x, y, x + width, y + height), relative=0, thickness=0)

    def profile_photo(self, x: float, y: float, size: float) -> None:
        """Aplica corte circular à fotografia preservada em docs/assets."""

        if not PROFILE_PHOTO.is_file():
            raise FileNotFoundError(f"foto de perfil ausente: {PROFILE_PHOTO}")

        self.c.saveState()
        clip = self.c.beginPath()
        clip.circle(x + size / 2, y + size / 2, size / 2)
        self.c.clipPath(clip, stroke=0, fill=0)
        self.c.drawImage(
            ImageReader(str(PROFILE_PHOTO)),
            x,
            y,
            width=size,
            height=size,
            preserveAspectRatio=True,
            anchor="c",
            mask="auto",
        )
        self.c.restoreState()
        self.c.setStrokeColor(Color(0.67, 0.89, 0.90, alpha=0.65))
        self.c.setLineWidth(2)
        self.c.circle(x + size / 2, y + size / 2, size / 2, fill=0, stroke=1)

    def start_page(self, title: str, kicker: str, insight: Optional[str] = None) -> None:
        self.page_number += 1
        self.c.setFillColor(CREAM)
        self.c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        self.label(kicker.upper(), MARGIN, 498, 9, TEAL_DARK, "bold")
        self.label(title, MARGIN, 457, 29, INK, "black")
        if insight:
            self.paragraph(insight, MARGIN, 430, 780, 11, 14, MUTED, "regular", 2)
        self.c.setStrokeColor(LINE)
        self.c.setLineWidth(0.8)
        self.c.line(MARGIN, 410, PAGE_W - MARGIN, 410)
        self.lh_mark(PAGE_W - MARGIN - 24, 480, 24)
        for index in range(3):
            self.c.setFillColor(TEAL if index == (self.page_number - 1) % 3 else LINE)
            self.c.circle(PAGE_W - MARGIN - 40 - index * 13, 492, 2.7, fill=1, stroke=0)

    def footer(self, note: str = "Dados agregados · sem PII") -> None:
        period = self.data["metadata"].get("sourcePeriod", {})
        if isinstance(period, Mapping):
            start = period.get("start")
            end = period.get("end")
            period_text = f"{br_date(start)} — {br_date(end)}"
        else:
            period_text = str(period)
        self.label(f"LH Nautical · {period_text} · {note}", MARGIN, 24, 8, MUTED, "medium")
        self.label(
            f"{self.page_number:02d} / {TOTAL_PAGES:02d}",
            PAGE_W - MARGIN,
            24,
            8,
            MUTED,
            "bold",
            "right",
        )

    def kpi_card(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        title: str,
        value: str,
        note: str,
        accent: Color = TEAL,
        dark: bool = False,
    ) -> None:
        fill = NAVY_2 if dark else PAPER
        main = WHITE if dark else INK
        secondary = MINT if dark else MUTED
        self.rect(x, y, width, height, fill, 13, None if dark else LINE)
        self.c.setFillColor(accent)
        self.c.roundRect(x, y, 5, height, 2.5, fill=1, stroke=0)
        self.label(title.upper(), x + 18, y + height - 22, 8.2, secondary, "bold")
        self.label(value, x + 18, y + height - 53, 22, main, "black")
        self.paragraph(note, x + 18, y + 13, width - 32, 7.8, 9.5, secondary, "regular", 2)

    def bullet(
        self,
        x: float,
        y: float,
        width: float,
        title: str,
        body: str,
        number: Optional[str] = None,
        color: Color = TEAL,
    ) -> float:
        self.c.setFillColor(color)
        self.c.circle(x + 9, y - 3, 9, fill=1, stroke=0)
        if number:
            self.label(number, x + 9, y - 6, 8, WHITE, "bold", "center")
        self.label(title, x + 28, y + 2, 11, INK, "bold")
        return self.paragraph(body, x + 28, y - 16, width - 28, 8.7, 11.3, MUTED, "regular", 3)

    def decision_insight_card(
        self,
        x: float,
        y: float,
        persona: str,
        topic: str,
        accent: Color,
        evidence: str,
        implication: str,
        action: str,
        caveat: str,
    ) -> None:
        width, height = 278.0, 157.0
        self.rect(x, y, width, height, PAPER, 14, LINE)
        self.rect(x, y + height - 29, width, 29, NAVY_2, 10)
        self.c.setFillColor(accent)
        self.c.circle(x + 17, y + height - 14.5, 4.5, fill=1, stroke=0)
        self.label(persona.upper(), x + 29, y + height - 18, 8.3, WHITE, "black")
        self.label(topic.upper(), x + width - 13, y + height - 18, 7.1, MINT, "bold", "right")

        self.label("EVIDÊNCIA", x + 14, y + 112, 6.5, TEAL_DARK, "bold")
        self.paragraph(evidence, x + 72, y + 113, width - 86, 8.2, 9.3, INK, "bold", 2)

        self.label("IMPLICAÇÃO", x + 14, y + 82, 6.5, TEAL_DARK, "bold")
        self.paragraph(implication, x + 72, y + 83, width - 86, 7.1, 8.4, INK, "medium", 2)

        self.label("AÇÃO", x + 14, y + 52, 6.5, TEAL_DARK, "bold")
        self.paragraph(action, x + 48, y + 53, width - 62, 7.1, 8.4, INK, "medium", 2)

        self.rect(x + 10, y + 8, width - 20, 24, HexColor("#F3F0E8"), 8)
        self.c.setFillColor(accent)
        self.c.circle(x + 20, y + 20, 3.5, fill=1, stroke=0)
        self.label("RESSALVA", x + 30, y + 17, 6.1, INK, "bold")
        self.paragraph(caveat, x + 78, y + 22, width - 94, 6.4, 7.2, MUTED, "regular", 2)

    def draw_cover(self) -> None:
        self.page_number += 1
        self.c.setFillColor(DASHBOARD_NAVY)
        self.c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

        # Campo visual inspirado em navegação, dados e na identidade do dashboard.
        self.c.saveState()
        self.c.setStrokeColor(Color(0.49, 0.89, 0.82, alpha=0.20))
        self.c.setLineWidth(0.8)
        center_x, center_y = 768, 270
        for radius in (54, 104, 154, 204):
            self.c.circle(center_x, center_y, radius, fill=0, stroke=1)
        for angle in range(0, 360, 30):
            radians = math.radians(angle)
            self.c.line(
                center_x + 42 * math.cos(radians),
                center_y + 42 * math.sin(radians),
                center_x + 204 * math.cos(radians),
                center_y + 204 * math.sin(radians),
            )
        points = [
            (681, 339, 5, TEAL),
            (764, 373, 8, MINT),
            (848, 317, 5, ORANGE),
            (872, 228, 7, SKY),
            (785, 165, 5, TEAL),
            (690, 205, 7, YELLOW),
            (755, 271, 11, WHITE),
        ]
        for x, y, radius, color in points:
            self.c.setFillColor(color)
            self.c.circle(x, y, radius, fill=1, stroke=0)
        self.c.restoreState()

        self.lh_mark(MARGIN, 454, 34)
        self.label("LH NAUTICAL  /  VISÃO DE DADOS", MARGIN + 46, 467, 10, MINT, "bold")
        self.link_button(
            445,
            456,
            257,
            "DASHBOARD · desafioindicium.eumoas.workers.dev",
            DASHBOARD_URL,
            HexColor("#111368"),
            WHITE,
            7.2,
        )
        self.link_button(
            714,
            456,
            198,
            "GITHUB · eumoas/DesafioIndicium",
            REPOSITORY_URL,
            DASHBOARD_LAVENDER,
            WHITE,
            7.2,
        )
        self.paragraph("Resumo\nexecutivo", MARGIN, 373, 540, 57, 55, WHITE, "black")
        self.paragraph(
            "Do dado operacional à próxima decisão — com premissas, limites e sinais acionáveis.",
            MARGIN,
            245,
            520,
            16,
            21,
            HexColor("#C5D8DE"),
            "regular",
            3,
        )
        self.rect(
            MARGIN,
            141,
            510,
            56,
            HexColor("#111368"),
            12,
            Color(0.49, 0.89, 0.82, alpha=0.25),
        )
        metadata = self.data["metadata"]
        source_count = metadata.get("sourceFiles", 24)
        if isinstance(source_count, list):
            source_count = len(source_count)
        period = metadata.get("sourcePeriod", {})
        if isinstance(period, Mapping):
            period_short = f"{pd.to_datetime(period.get('start')).year}—{pd.to_datetime(period.get('end')).year}"
        else:
            period_short = "2020—2026"
        self.label(period_short, MARGIN + 20, 166, 13, WHITE, "bold")
        self.label("PERÍODO NO ARQUIVO", MARGIN + 20, 151, 7.5, MINT, "bold")
        self.c.setStrokeColor(HexColor("#31515F"))
        self.c.line(MARGIN + 144, 153, MARGIN + 144, 184)
        self.label(br_number(source_count), MARGIN + 170, 166, 13, WHITE, "bold")
        self.label("FONTES CSV", MARGIN + 170, 151, 7.5, MINT, "bold")
        self.c.line(MARGIN + 270, 153, MARGIN + 270, 184)
        self.label(f"{TOTAL_PAGES} páginas", MARGIN + 296, 166, 13, WHITE, "bold")
        self.label("LEITURA EXECUTIVA", MARGIN + 296, 151, 7.5, MINT, "bold")

        generated_at = metadata.get("generatedAt")
        self.label("CIENTISTA DE DADOS", MARGIN, 103, 7.5, MINT, "bold")
        self.label("Miriam Oliveira de Aguiar Sobral", MARGIN, 84, 11, WHITE, "bold")
        self.label(
            f"Gerado em {br_date(generated_at)} · material agregado e anonimizado",
            MARGIN,
            54,
            8.5,
            HexColor("#8FAAB5"),
            "medium",
        )
        self.label(
            f"01 / {TOTAL_PAGES:02d}",
            PAGE_W - MARGIN,
            54,
            8.5,
            MINT,
            "bold",
            "right",
        )
        self.c.showPage()

    def draw_profile(self) -> None:
        self.start_page(
            "Sobre a cientista de dados",
            "09 · Autoria",
            "Uma trajetória nexialista que conecta tecnologia, políticas públicas e inteligência artificial aplicada à indústria.",
        )

        self.rect(MARGIN, 58, 244, 326, DASHBOARD_NAVY, 18)
        self.profile_photo(MARGIN + 29, 170, 186)
        self.label("Miriam Oliveira", MARGIN + 22, 139, 14, WHITE, "black")
        self.label("de Aguiar Sobral", MARGIN + 22, 120, 14, WHITE, "black")
        self.label("CIENTISTA DE DADOS", MARGIN + 22, 97, 8, MINT, "bold")
        self.link_button(
            MARGIN + 18,
            67,
            208,
            "linkedin.com/in/miriamaguiarsobral",
            LINKEDIN_URL,
            HexColor("#111368"),
            WHITE,
            7.3,
        )

        content_x = 324
        self.label("PERFIL NEXIALISTA", content_x, 376, 8.2, TEAL_DARK, "bold")
        self.paragraph(
            "Conecto campos que nem sempre conversam. O nexo é prático: aplico o rigor metodológico da avaliação de políticas públicas para desenvolver e testar soluções de IA que funcionem fora do laboratório.",
            content_x,
            352,
            588,
            10.4,
            14.2,
            INK,
            "medium",
            5,
        )

        self.label("ATUAÇÃO ATUAL", content_x, 276, 8.2, TEAL_DARK, "bold")
        self.paragraph(
            "Hoje atuo em duas frentes. Na residência de IA da UniSENAI/FIESC, desenvolvo visão computacional para detecção de defeitos com YOLOv8, CNN e SAHI, deploy em AWS, automações com LLMs e chatbots educacionais. Como pesquisadora, realizo estudos e análises em educação, segurança e saúde.",
            content_x,
            252,
            588,
            9.5,
            13.0,
            MUTED,
            "regular",
            5,
        )

        self.rect(content_x, 72, 278, 124, PAPER, 14, LINE)
        self.label("FORMAÇÃO", content_x + 17, 173, 8, TEAL_DARK, "bold")
        self.paragraph(
            "Mestrado em Gestão e Políticas Públicas — FGV\nBacharelado em Sistemas de Informação\nIA Aplicada — UniSENAI, em andamento\nInformação Quântica — SENAI CIMATEC, em andamento",
            content_x + 17,
            151,
            244,
            8.1,
            14.0,
            INK,
            "medium",
            6,
        )

        self.rect(616, 72, 296, 124, HexColor("#E8F0FF"), 14, HexColor("#C6D2FA"))
        self.label("RECONHECIMENTO", 633, 173, 8, HexColor("#3D28D9"), "bold")
        self.label("1º lugar", 633, 143, 22, DASHBOARD_NAVY, "black")
        self.paragraph(
            "Industry for Her · Accenture/VDI\nSolução de automação logística para a indústria alemã.",
            633,
            119,
            252,
            8.5,
            12.0,
            MUTED,
            "medium",
            4,
        )
        self.footer("perfil profissional · links clicáveis")
        self.c.showPage()

    def draw_decision_insights(self) -> None:
        self.start_page(
            "Insights para decisão",
            "01 · Decisão",
            "Evidência primeiro: o que cada liderança pode decidir agora, qual ação testar e onde a leitura ainda precisa de proteção.",
        )
        self.decision_insight_card(
            MARGIN,
            235,
            "Marina",
            "Segmentação",
            TEAL,
            "98,55% passam na “elite”.",
            "O corte quase não segmenta; ticket domina o ranking.",
            "Adicionar recência, frequência mínima, margem e janela.",
            "A regra cumpre o desafio; não demonstra fidelidade.",
        )
        self.decision_insight_card(
            341,
            235,
            "Marina",
            "Canais",
            SKY,
            "E-commerce: 70,19% do valor · 70,09% dos pedidos.",
            "Escala digital é clara; rentabilidade permanece desconhecida.",
            "Comparar margem, devoluções e custo de servir.",
            "Valor registrado não é receita reconhecida nem lucro.",
        )
        self.decision_insight_card(
            634,
            235,
            "Marina",
            "Recomendação",
            LAVENDER,
            "Motor de Popa 5331 #1; primeira defensa #15.",
            "Afinidade de público não prova complementaridade.",
            "Aplicar regra comercial e teste com grupo de controle.",
            "Todos os status; sem propensão individual estimada.",
        )
        self.decision_insight_card(
            MARGIN,
            64,
            "Sr. Almir",
            "Operação POS",
            ORANGE,
            "Quinta só 0,29% abaixo de domingo: 461,81.",
            "A diferença não sustenta fechar lojas.",
            "Analisar loja-dia, custos e migração de demanda.",
            "Rede agregada; sem margem ou efeito causal.",
        )
        self.decision_insight_card(
            341,
            64,
            "Sr. Almir",
            "Previsão",
            YELLOW,
            "−28,18% no trimestre · MAE 19,44 un./mês.",
            "O baseline subestima; não deve comandar compras.",
            "Testar estoque, ruptura, promoção e lead time.",
            "Apenas três meses de teste.",
        )
        self.decision_insight_card(
            634,
            64,
            "Gabriel",
            "Confiança",
            SKY,
            "24 fontes · 433.424 registros · sem órfãos.",
            "A estrutura sustenta exploração reproduzível.",
            "Aprovar status, moeda, reconhecimento e corte.",
            "Consistência técnica não certifica KPIs financeiros.",
        )
        self.footer("valor registrado · decisões com ressalvas explícitas")
        self.c.showPage()

    def draw_summary(self) -> None:
        executive = self.data["executive"]
        channels = self.data["sales"]["channels"]
        total_value = as_number(executive.get("recordedValue"))
        ecommerce = next((row for row in channels if row.get("channel", "").lower() == "ecommerce"), None)
        ecommerce_share = 100 * as_number(ecommerce.get("value") if ecommerce else 0) / max(total_value, 1)
        forecast_rows = self.data["operations"]["forecast"]["rows"]
        predicted = sum(as_number(row.get("prediction")) for row in forecast_rows)
        actual = sum(as_number(row.get("actual")) for row in forecast_rows)
        forecast_gap = actual - predicted

        self.start_page(
            "O que a diretoria precisa saber",
            "02 · Resumo",
            "A base abre boas decisões exploratórias; a regra de reconhecimento ainda precisa ser fechada antes de qualquer KPI financeiro.",
        )
        card_w = 198
        cards = [
            ("Pedidos", br_number(executive.get("orders")), "todas as linhas e status", TEAL),
            ("Valor registrado", compact_value(total_value), "soma de orders.total; sem R$", SKY),
            ("Clientes", br_number(executive.get("customers")), "somente contagem agregada", LAVENDER),
            ("Ticket médio", br_number(executive.get("averageTicket"), 2), "valor por pedido; não margem", ORANGE),
        ]
        for index, (title, value, note, accent) in enumerate(cards):
            self.kpi_card(MARGIN + index * 216, 319, card_w, 78, title, value, note, accent)

        self.rect(MARGIN, 76, 552, 224, PAPER, 14, LINE)
        self.label("SINAIS PRIORITÁRIOS", MARGIN + 20, 275, 9, TEAL_DARK, "bold")
        y = 244
        y = self.bullet(
            MARGIN + 18,
            y,
            500,
            f"Digital concentra {br_number(ecommerce_share, 1)}% do valor registrado",
            "O canal é dominante no snapshot; a comparação não informa margem nem custo de servir.",
            "1",
            TEAL,
        ) - 15
        y = self.bullet(
            MARGIN + 18,
            y,
            500,
            "Critério de cliente é pouco seletivo",
            f"{br_number(self.data['customers']['eligibility']['percent'], 2)}% da base alcança ao menos 13 categorias; ticket passa a decidir quase todo o ranking.",
            "2",
            SKY,
        ) - 15
        self.bullet(
            MARGIN + 18,
            y,
            500,
            f"Baseline ficou {br_number(forecast_gap, 2)} unidades abaixo no trimestre",
            "É um ponto de partida auditável, ainda insuficiente para automatizar compra ou reposição.",
            "3",
            ORANGE,
        )

        self.rect(624, 76, 288, 224, NAVY_2, 14)
        self.label("LIMITE DA LEITURA", 644, 275, 9, MINT, "bold")
        self.paragraph("Valor registrado ≠ receita, lucro ou caixa", 644, 241, 238, 18, 22, WHITE, "black", 3)
        self.c.setStrokeColor(HexColor("#31515F"))
        self.c.line(644, 176, 884, 176)
        self.label("INCLUI", 644, 155, 8, MINT, "bold")
        self.paragraph("paid · confirmed · cancelled · draft", 644, 137, 236, 9, 12, HexColor("#C5D8DE"), "medium", 2)
        self.label("PRÓXIMO GATE", 644, 104, 8, ORANGE, "bold")
        self.label("Confirmar status + data de corte", 737, 104, 8.5, WHITE, "bold")
        self.footer()
        self.c.showPage()

    def draw_confidence(self) -> None:
        checks = self.data["quality"]["checks"]
        future_orders = as_int(self.data.get("quality", {}).get("futureOrders"))
        cutoff_risk = (
            "o arquivo alcança 31/12/2026; há datas posteriores à geração."
            if future_orders
            else "a data máxima do snapshot ainda requer confirmação formal."
        )
        self.start_page(
            "Confiabilidade condicional",
            "03 · Confiança",
            "A estrutura observada é consistente para exploração; regras de negócio pendentes impedem uma leitura financeira certificada.",
        )
        self.rect(MARGIN, 304, 555, 88, NAVY_2, 14)
        self.label("VEREDITO", MARGIN + 20, 367, 8.5, MINT, "bold")
        self.label("Útil para decidir perguntas.", MARGIN + 20, 339, 22, WHITE, "black")
        self.label("Ainda não para declarar receita.", MARGIN + 20, 316, 14, HexColor("#C5D8DE"), "semibold")
        self.rect(624, 304, 288, 88, HexColor("#FFF4D9"), 14, HexColor("#E9D29A"))
        self.label("NÍVEL DE ATENÇÃO", 646, 365, 8, HexColor("#826323"), "bold")
        self.c.setFillColor(YELLOW)
        self.c.circle(655, 333, 9, fill=1, stroke=0)
        self.label("AMARELO", 674, 326, 24, INK, "black")

        display_checks = list(checks[:4])
        while len(display_checks) < 4:
            display_checks.append({"label": "Verificação", "status": "attention", "evidence": "não informada"})
        card_width = 207
        for index, check in enumerate(display_checks):
            x = MARGIN + index * 216
            self.rect(x, 204, card_width, 82, PAPER, 12, LINE)
            status = str(check.get("status", "attention")).lower()
            ok = status in {"ok", "pass", "passed", "success", "green", "true"}
            color = TEAL if ok else ORANGE
            symbol = "OK" if ok else "!"
            self.rect(x + 13, 253, 28, 20, color, 7)
            self.label(symbol, x + 27, 259, 8.2, WHITE, "bold", "center")
            self.paragraph(check.get("label", "Verificação"), x + 49, 259, 140, 9.5, 11, INK, "bold", 2)
            self.paragraph(check.get("evidence", ""), x + 14, 232, 178, 7.7, 9.5, MUTED, "regular", 3)

        self.rect(MARGIN, 66, 548, 120, PAPER, 14, LINE)
        self.label("RISCOS QUE MUDAM A DECISÃO", MARGIN + 20, 163, 9, TEAL_DARK, "bold")
        risks = [
            ("Status", "draft e cancelled foram mantidos por leitura literal."),
            ("Corte", cutoff_risk),
            ("Semântica", "moeda e reconhecimento de orders.total não estão documentados."),
        ]
        for index, (title, detail) in enumerate(risks):
            y = 136 - index * 28
            self.c.setFillColor(ORANGE if index < 2 else YELLOW)
            self.c.circle(MARGIN + 27, y + 2, 4.5, fill=1, stroke=0)
            self.label(title, MARGIN + 42, y - 2, 8.5, INK, "bold")
            self.label(detail, MARGIN + 104, y - 2, 7.8, MUTED, "regular")

        self.rect(616, 66, 296, 120, HexColor("#E8F4F2"), 14, HexColor("#BFDDD8"))
        self.label("GATE DE GOVERNANÇA", 636, 163, 9, TEAL_DARK, "bold")
        gates = ["status reconhecidos", "moeda e regra contábil", "data de extração", "fuso da operação"]
        for index, item in enumerate(gates):
            y = 137 - index * 21
            self.rect(636, y - 7, 15, 15, WHITE, 4, HexColor("#9BC7C1"))
            self.label(item, 662, y - 2, 8.5, INK, "semibold")
        self.footer("qualidade observada, não certificação")
        self.c.showPage()

    def draw_monthly_line(self, x: float, y: float, width: float, height: float, monthly: Sequence[Mapping[str, Any]]) -> None:
        self.rect(x, y, width, height, PAPER, 14, LINE)
        self.label("VALOR REGISTRADO POR MÊS", x + 18, y + height - 25, 9, TEAL_DARK, "bold")
        self.label("escala em milhões", x + width - 18, y + height - 25, 8, MUTED, "medium", "right")
        plot_x, plot_y = x + 49, y + 40
        plot_w, plot_h = width - 72, height - 82
        values = [as_number(row.get("value")) / 1_000_000 for row in monthly]
        if not values:
            self.label("Série indisponível", x + width / 2, y + height / 2, 10, MUTED, "medium", "center")
            return
        y_max = max(values) * 1.12 or 1
        for index in range(5):
            grid_y = plot_y + index * plot_h / 4
            self.c.setStrokeColor(LINE)
            self.c.setLineWidth(0.6)
            self.c.line(plot_x, grid_y, plot_x + plot_w, grid_y)
            self.label(br_number(index * y_max / 4, 0), plot_x - 8, grid_y - 3, 7, MUTED, "regular", "right")
        point_count = len(values)
        coordinates = []
        for index, value in enumerate(values):
            px = plot_x + (index / max(point_count - 1, 1)) * plot_w
            py = plot_y + (value / y_max) * plot_h
            coordinates.append((px, py))
        self.c.setStrokeColor(TEAL)
        self.c.setLineWidth(2.3)
        path = self.c.beginPath()
        path.moveTo(*coordinates[0])
        for coordinate in coordinates[1:]:
            path.lineTo(*coordinate)
        self.c.drawPath(path, fill=0, stroke=1)
        for index, (px, py) in enumerate(coordinates):
            if index == len(coordinates) - 1 or index == 0:
                self.c.setFillColor(ORANGE if index == len(coordinates) - 1 else TEAL)
                self.c.circle(px, py, 3.8, fill=1, stroke=0)
        used_years = set()
        for index, row in enumerate(monthly):
            month = str(row.get("month", ""))
            if len(month) >= 4:
                year = month[:4]
                if year not in used_years and (month.endswith("-01") or not used_years):
                    px = plot_x + (index / max(point_count - 1, 1)) * plot_w
                    self.label(year, px, plot_y - 19, 7.5, MUTED, "medium", "center")
                    used_years.add(year)

    def draw_commercial(self) -> None:
        executive = self.data["executive"]
        monthly = self.data["sales"]["monthly"]
        channels = self.data["sales"]["channels"]
        statuses = self.data["sales"]["statuses"]
        total_value = as_number(executive.get("recordedValue"))
        total_orders = as_number(executive.get("orders"))
        top_status = statuses[0] if statuses else {"status": "—", "value": 0, "orders": 0}
        self.start_page(
            "Comercial: escala e composição",
            "04 · Comercial",
            "O snapshot registra expansão de volume, mas toda leitura permanece bruta: valores incluem quatro status e não equivalem a receita reconhecida.",
        )
        self.kpi_card(MARGIN, 319, 176, 76, "Valor no arquivo", compact_value(total_value), "orders.total acumulado", TEAL)
        self.kpi_card(238, 319, 176, 76, "Pedidos", br_number(total_orders), "2020 a 2026", SKY)
        self.kpi_card(
            428,
            319,
            176,
            76,
            "Status dominante",
            str(top_status.get("status", "—")),
            f"{br_number(100 * as_number(top_status.get('orders')) / max(total_orders, 1), 1)}% dos pedidos",
            LAVENDER,
        )
        self.kpi_card(618, 319, 294, 76, "Leitura correta", "Valor registrado", "não usar receita, lucro ou faturamento líquido", ORANGE, True)

        self.draw_monthly_line(MARGIN, 66, 566, 235, monthly)
        self.rect(632, 176, 280, 125, PAPER, 14, LINE)
        self.label("CANAIS", 650, 277, 9, TEAL_DARK, "bold")
        max_channel = max((as_number(row.get("value")) for row in channels), default=1)
        for index, row in enumerate(channels[:3]):
            yy = 242 - index * 48
            label = str(row.get("channel", "canal"))
            value = as_number(row.get("value"))
            self.label(label, 650, yy + 9, 9.2, INK, "bold")
            self.label(compact_value(value), 892, yy + 9, 8.5, MUTED, "bold", "right")
            self.rect(650, yy - 8, 242, 8, HexColor("#E5EBE8"), 4)
            self.rect(650, yy - 8, 242 * value / max(max_channel, 1), 8, TEAL if index == 0 else SKY, 4)

        self.rect(632, 66, 280, 96, NAVY_2, 14)
        self.label("STATUS · PEDIDOS", 650, 139, 8.5, MINT, "bold")
        palette = [TEAL, SKY, ORANGE, LAVENDER]
        cursor_x = 650.0
        track_width = 242.0
        for index, row in enumerate(statuses[:4]):
            share = as_number(row.get("orders")) / max(total_orders, 1)
            segment = track_width * share
            self.c.setFillColor(palette[index % len(palette)])
            self.c.rect(cursor_x, 116, segment, 9, fill=1, stroke=0)
            cursor_x += segment
        for index, row in enumerate(statuses[:4]):
            col = index % 2
            row_idx = index // 2
            lx = 650 + col * 121
            ly = 92 - row_idx * 19
            self.c.setFillColor(palette[index % len(palette)])
            self.c.circle(lx + 3, ly + 3, 3, fill=1, stroke=0)
            self.label(str(row.get("status", "—")), lx + 12, ly, 7.5, WHITE, "medium")
            self.label(br_number(row.get("orders")), lx + 108, ly, 7.5, HexColor("#C5D8DE"), "bold", "right")
        self.footer("todos os status · valores sem moeda documentada")
        self.c.showPage()

    def draw_clients(self) -> None:
        elite = self.data["customers"]["eliteTop10"]
        eligibility = self.data["customers"]["eligibility"]
        categories = self.data["customers"]["topEliteCategories"]
        self.start_page(
            "Clientes: ranking com ressalva",
            "05 · Clientes",
            "O top 10 segue exatamente a regra pedida, mas o corte de diversidade aprova quase toda a base e não caracteriza fidelidade sozinho.",
        )
        self.rect(MARGIN, 74, 590, 318, PAPER, 14, LINE)
        self.label("TOP 10 POR TICKET MÉDIO · ALIASES ANÔNIMOS", MARGIN + 20, 366, 9, TEAL_DARK, "bold")
        max_ticket = max((as_number(row.get("ticket")) for row in elite), default=1)
        for index, row in enumerate(elite[:10]):
            y = 336 - index * 25.5
            alias = f"Perfil {index + 1:02d}"
            ticket = as_number(row.get("ticket"))
            self.label(alias, MARGIN + 20, y, 8.3, INK, "bold")
            self.rect(MARGIN + 92, y - 2, 345, 7, HexColor("#E5EBE8"), 3.5)
            self.rect(MARGIN + 92, y - 2, 345 * ticket / max(max_ticket, 1), 7, TEAL if index < 3 else SKY, 3.5)
            self.label(br_number(ticket, 2), MARGIN + 451, y - 1, 8.1, INK, "bold", "right")
            self.label(f"{as_int(row.get('orders'))} ped.", MARGIN + 548, y - 1, 7.5, MUTED, "medium", "right")

        self.rect(658, 264, 254, 128, NAVY_2, 14)
        self.label("SELETIVIDADE", 678, 366, 8.5, MINT, "bold")
        percent = as_number(eligibility.get("percent"))
        self.label(f"{br_number(percent, 2)}%", 678, 329, 30, WHITE, "black")
        self.paragraph(
            f"{br_number(eligibility.get('eligible'))} de {br_number(eligibility.get('total'))} clientes passam no corte de ≥ {as_int(eligibility.get('minimumCategories'), 13)} categorias.",
            678,
            304,
            208,
            8.7,
            11,
            HexColor("#C5D8DE"),
            "regular",
            3,
        )
        self.rect(678, 281, 208, 8, HexColor("#31515F"), 4)
        self.rect(678, 281, 208 * min(percent, 100) / 100, 8, ORANGE, 4)

        leader = categories[0] if categories else {"category": "—", "quantity": 0}
        self.rect(658, 148, 254, 100, HexColor("#E8F4F2"), 14, HexColor("#BFDDD8"))
        self.label("CATEGORIA LÍDER NO TOP 10", 678, 222, 8, TEAL_DARK, "bold")
        self.paragraph(leader.get("category", "—"), 678, 196, 208, 18, 21, INK, "black", 2)
        self.label(f"{br_number(leader.get('quantity'))} na soma de quantity", 678, 165, 8.5, MUTED, "medium")

        self.rect(658, 74, 254, 58, HexColor("#FFF4D9"), 12, HexColor("#E9D29A"))
        self.label("LEITURA", 678, 109, 8, HexColor("#826323"), "bold")
        self.paragraph("Frequência é exibida, mas não filtra nem ordena o ranking.", 678, 92, 208, 7.8, 9.5, INK, "medium", 2)
        self.footer("sem nomes, e-mails, documentos ou IDs de clientes")
        self.c.showPage()

    def draw_pos(self) -> None:
        weekday_rows = self.data["operations"]["weekdayPos"]
        valid = [row for row in weekday_rows if as_number(row.get("average")) >= 0]
        lowest = min(valid, key=lambda row: as_number(row.get("average"))) if valid else {"weekday": "—", "average": 0}
        sunday = next((row for row in valid if "domingo" in str(row.get("weekday", "")).lower()), None)
        delta_sunday = abs(as_number(lowest.get("average")) - as_number(sunday.get("average") if sunday else 0))
        delta_pct = 100 * delta_sunday / max(as_number(sunday.get("average") if sunday else 0), 1)
        self.start_page(
            "POS: calendário muda a média",
            "06 · Operação física",
            "Ao incluir dias sem registro como zero, quinta-feira tem a menor média — uma diferença pequena demais para sustentar fechamento de lojas.",
        )
        self.rect(MARGIN, 84, 602, 308, PAPER, 14, LINE)
        self.label("MÉDIA DIÁRIA DE VALOR REGISTRADO · REDE POS", MARGIN + 20, 366, 9, TEAL_DARK, "bold")
        plot_x, plot_y = MARGIN + 47, 140
        plot_w, plot_h = 525, 185
        maximum = max((as_number(row.get("average")) for row in valid), default=1) * 1.12
        for index in range(5):
            yy = plot_y + index * plot_h / 4
            self.c.setStrokeColor(LINE)
            self.c.setLineWidth(0.6)
            self.c.line(plot_x, yy, plot_x + plot_w, yy)
            self.label(compact_value(index * maximum / 4), plot_x - 8, yy - 3, 7, MUTED, "regular", "right")
        bar_width = 48
        gap = (plot_w - bar_width * max(len(valid), 1)) / max(len(valid) - 1, 1)
        for index, row in enumerate(valid):
            value = as_number(row.get("average"))
            bx = plot_x + index * (bar_width + gap)
            bh = value / max(maximum, 1) * plot_h
            is_lowest = row is lowest
            self.rect(bx, plot_y, bar_width, bh, ORANGE if is_lowest else TEAL, 7)
            self.label(compact_value(value), bx + bar_width / 2, plot_y + bh + 8, 7.2, INK, "bold", "center")
            short = str(row.get("weekday", ""))[:3].lower()
            self.label(short, bx + bar_width / 2, plot_y - 19, 7.8, MUTED, "bold", "center")
            self.label(f"{as_int(row.get('zeroDays'))} zeros", bx + bar_width / 2, plot_y - 35, 6.8, MUTED, "regular", "center")

        self.rect(674, 280, 238, 112, NAVY_2, 14)
        self.label("MENOR MÉDIA", 694, 365, 8.5, MINT, "bold")
        self.paragraph(lowest.get("weekday", "—"), 694, 335, 198, 20, 23, WHITE, "black", 2)
        self.label(br_number(lowest.get("average"), 2), 694, 299, 13, ORANGE, "bold")

        self.rect(674, 166, 238, 96, HexColor("#E8F4F2"), 14, HexColor("#BFDDD8"))
        self.label("CONTEXTO", 694, 238, 8, TEAL_DARK, "bold")
        self.label(f"{br_number(delta_sunday, 2)}", 694, 211, 19, INK, "black")
        self.paragraph(f"de diferença para domingo ({br_number(delta_pct, 2)}%).", 694, 192, 198, 8.2, 10, MUTED, "medium", 2)

        self.rect(674, 84, 238, 64, HexColor("#FFF4D9"), 12, HexColor("#E9D29A"))
        self.label("NÃO CONCLUIR", 694, 124, 8, HexColor("#826323"), "bold")
        self.paragraph("Menor valor agregado não significa prejuízo nem justifica fechar lojas.", 694, 106, 198, 7.9, 9.6, INK, "medium", 3)
        self.footer("calendário completo · POS agregado · todos os status")
        self.c.showPage()

    def draw_forecast(self) -> None:
        forecast = self.data["operations"]["forecast"]
        series = forecast.get("rows", [])
        predicted_total = sum(as_number(row.get("prediction")) for row in series)
        actual_total = sum(as_number(row.get("actual")) for row in series)
        mae = as_number(forecast.get("mae"))
        if not mae and series:
            mae = sum(abs(as_number(row.get("actual")) - as_number(row.get("prediction"))) for row in series) / len(series)
        gap = predicted_total - actual_total
        self.start_page(
            "Previsão: baseline antes de automação",
            "07 · Demanda",
            "A média móvel de três meses é auditável e útil como referência; no teste, subestimou todos os meses e não deve comandar compras sozinha.",
        )
        self.kpi_card(MARGIN, 319, 176, 76, "MAE", f"{br_number(mae, 2)} un.", "erro absoluto médio mensal", ORANGE)
        self.kpi_card(238, 319, 176, 76, "Previsto", f"{br_number(predicted_total, 2)} un.", "soma jan–mar/2026", SKY)
        self.kpi_card(428, 319, 176, 76, "Realizado", f"{br_number(actual_total)} un.", "holdout histórico", TEAL)
        self.kpi_card(618, 319, 294, 76, "Viés trimestral", f"{br_number(gap, 2)} un.", "negativo = subestimação", ORANGE, True)

        self.rect(MARGIN, 72, 566, 228, PAPER, 14, LINE)
        self.label("PREVISÃO × REALIZADO", MARGIN + 20, 275, 9, TEAL_DARK, "bold")
        plot_x, plot_y, plot_w, plot_h = MARGIN + 55, 118, 465, 116
        maximum = max(
            [as_number(row.get("prediction")) for row in series]
            + [as_number(row.get("actual")) for row in series]
            + [1]
        ) * 1.18
        for index in range(4):
            yy = plot_y + index * plot_h / 3
            self.c.setStrokeColor(LINE)
            self.c.line(plot_x, yy, plot_x + plot_w, yy)
            self.label(br_number(index * maximum / 3, 0), plot_x - 10, yy - 3, 7, MUTED, "regular", "right")
        group_width = plot_w / max(len(series), 1)
        for index, row in enumerate(series):
            center = plot_x + group_width * (index + 0.5)
            pred = as_number(row.get("prediction"))
            actual = as_number(row.get("actual"))
            for offset, value, color in ((-19, pred, SKY), (5, actual, TEAL)):
                height = value / maximum * plot_h
                self.rect(center + offset, plot_y, 28, height, color, 6)
                self.label(br_number(value, 1), center + offset + 14, plot_y + height + 7, 7.2, INK, "bold", "center")
            self.label(month_label(row.get("month")), center, plot_y - 20, 8, MUTED, "bold", "center")
        self.c.setFillColor(SKY)
        self.c.circle(MARGIN + 375, 275, 3.5, fill=1, stroke=0)
        self.label("previsto", MARGIN + 384, 272, 7.5, MUTED, "medium")
        self.c.setFillColor(TEAL)
        self.c.circle(MARGIN + 448, 275, 3.5, fill=1, stroke=0)
        self.label("realizado", MARGIN + 457, 272, 7.5, MUTED, "medium")

        self.rect(632, 72, 280, 228, NAVY_2, 14)
        self.label("COMO USAR", 652, 275, 9, MINT, "bold")
        target = str(forecast.get("target", "produto-alvo"))
        self.paragraph(target, 652, 250, 240, 14, 17, WHITE, "bold", 2)
        notes = [
            ("1", "Manter como benchmark transparente."),
            ("2", "Repor com faixa de segurança, não ponto único."),
            ("3", "Adicionar estoque, ruptura, promoção e lead time."),
        ]
        for index, (number, note) in enumerate(notes):
            yy = 196 - index * 42
            self.c.setFillColor(TEAL if index < 2 else ORANGE)
            self.c.circle(661, yy + 4, 9, fill=1, stroke=0)
            self.label(number, 661, yy + 1, 8, WHITE, "bold", "center")
            self.paragraph(note, 680, yy + 8, 205, 8.5, 10.5, HexColor("#C5D8DE"), "medium", 2)
        self.footer("walk-forward · sem vazamento temporal")
        self.c.showPage()

    def draw_recommendations(self) -> None:
        recommendation = self.data["operations"]["recommendations"]
        ranking = recommendation.get("rows", [])
        target = str(recommendation.get("target", "produto-alvo"))
        self.start_page(
            "Recomendação e próximos passos",
            "08 · Ação",
            "O sinal de co-compra orienta teste controlado de cross-sell; desempenho deve ser medido antes de escalar para campanha ou estoque.",
        )
        self.rect(MARGIN, 106, 528, 286, PAPER, 14, LINE)
        self.label("PRODUTOS MAIS SIMILARES POR CO-COMPRA", MARGIN + 20, 366, 9, TEAL_DARK, "bold")
        self.label(f"Referência: {target}", MARGIN + 20, 345, 8.3, MUTED, "medium")
        max_similarity = max((as_number(row.get("similarity")) for row in ranking), default=1)
        for index, row in enumerate(ranking[:5]):
            y = 307 - index * 46
            self.rect(MARGIN + 18, y - 9, 27, 27, TEAL if index < 3 else SKY, 8)
            self.label(str(index + 1), MARGIN + 31.5, y - 1, 9, WHITE, "bold", "center")
            self.paragraph(row.get("product", "Produto"), MARGIN + 58, y + 8, 260, 9.2, 11, INK, "bold", 2)
            similarity = as_number(row.get("similarity"))
            self.rect(MARGIN + 325, y + 2, 112, 7, HexColor("#E5EBE8"), 3.5)
            self.rect(MARGIN + 325, y + 2, 112 * similarity / max(max_similarity, 1), 7, ORANGE, 3.5)
            self.label(f"{similarity:.3f}", MARGIN + 455, y, 8, INK, "bold")
            self.label(
                f"{as_int(row.get('commonCustomers'))} clientes em comum",
                MARGIN + 325,
                y - 15,
                6.9,
                MUTED,
                "regular",
            )

        self.rect(596, 106, 316, 286, NAVY_2, 14)
        self.label("ROTEIRO DE DECISÃO", 618, 366, 9, MINT, "bold")
        roadmap = [
            ("0—7 dias", "Definir status elegíveis, moeda e data de corte.", TEAL),
            ("30 dias", "Rodar A/B de cross-sell com holdout e margem incremental.", SKY),
            ("60—90 dias", "Backtest de demanda com estoque, ruptura e lead time.", ORANGE),
        ]
        for index, (when, action, color) in enumerate(roadmap):
            y = 318 - index * 71
            self.c.setFillColor(color)
            self.c.circle(628, y + 5, 6, fill=1, stroke=0)
            if index < len(roadmap) - 1:
                self.c.setStrokeColor(HexColor("#31515F"))
                self.c.setLineWidth(2)
                self.c.line(628, y - 4, 628, y - 57)
            self.label(when, 648, y + 5, 10, WHITE, "bold")
            self.paragraph(action, 648, y - 14, 232, 8.5, 10.5, HexColor("#C5D8DE"), "regular", 3)

        self.rect(MARGIN, 50, 864, 48, HexColor("#E8F4F2"), 10, HexColor("#BFDDD8"))
        self.label("CULTURA DATA-DRIVEN", MARGIN + 16, 78, 8, TEAL_DARK, "bold")
        self.label(
            "Hipótese → métrica → evidência → experimento → resultado → aprendizado.",
            MARGIN + 166,
            78,
            8.5,
            INK,
            "semibold",
        )
        self.label(
            "Próximo gate: aprovar o contrato das métricas antes de escalar recomendação ou previsão.",
            MARGIN + 16,
            60,
            7.5,
            MUTED,
            "medium",
        )
        self.footer("similaridade é sinal, não causalidade")
        self.c.showPage()

    def build(self) -> None:
        self.draw_cover()
        self.draw_decision_insights()
        self.draw_summary()
        self.draw_confidence()
        self.draw_commercial()
        self.draw_clients()
        self.draw_pos()
        self.draw_forecast()
        self.draw_recommendations()
        self.draw_profile()
        self.c.save()


def parse_args(arguments: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera o resumo executivo da LH Nautical em PDF.")
    parser.add_argument(
        "--dashboard",
        type=Path,
        default=DEFAULT_JSON,
        help="JSON consolidado do dashboard (fallback automático aos CSVs).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Arquivo PDF de saída.",
    )
    return parser.parse_args(arguments)


def main(arguments: Optional[Sequence[str]] = None) -> int:
    args = parse_args(arguments)
    try:
        data = load_report_data(ROOT, args.dashboard)
        report = ExecutiveReport(args.output, data)
        report.build()
    except (OSError, ValueError, KeyError, pd.errors.ParserError) as error:
        print(f"Erro ao gerar relatório: {error}", file=sys.stderr)
        return 1
    source_mode = data.get("metadata", {}).get("sourceMode", "csv_fallback")
    print(f"PDF gerado: {args.output}")
    print(f"Fonte consolidada: {source_mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
