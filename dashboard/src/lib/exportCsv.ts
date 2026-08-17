import type { DashboardData, DashboardView } from "../types/dashboard";

type CsvCell = string | number | boolean | null | undefined;
type CsvRow = Record<string, CsvCell>;

function escapeCell(value: CsvCell): string {
  if (value === null || value === undefined) return "";
  const text = String(value);
  return /[;"\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function rowsForView(data: DashboardData, view: DashboardView): CsvRow[] {
  if (view === "command") {
    return [
      ...(data.executive.cards ?? []).map((card) => ({
        secao: "indicador_executivo",
        dimensao: card.label ?? card.title,
        periodo: "",
        metrica: card.format ?? "valor",
        valor: card.value,
        detalhe: card.detail ?? card.description,
      })),
      ...(data.sales.monthly ?? []).map((point) => ({
        secao: "serie_mensal",
        dimensao: "valor_bruto_registrado",
        periodo: point.month ?? point.period ?? point.date,
        metrica: "valor_bruto",
        valor: point.revenue ?? point.sales ?? point.total,
        detalhe: point.orders !== undefined ? `${point.orders} pedidos` : "",
      })),
      ...(data.sales.channels ?? []).map((point) => ({
        secao: "canal",
        dimensao: point.channel ?? point.name ?? point.label,
        periodo: "",
        metrica: "valor_bruto",
        valor: point.revenue ?? point.value ?? point.total,
        detalhe: point.orders !== undefined ? `${point.orders} pedidos` : "",
      })),
    ];
  }

  if (view === "marina") {
    return [
      ...(data.customers.eliteTop10 ?? []).map((customer, index) => ({
        secao: "ranking_elite_anonimizado",
        dimensao: customer.customerLabel ?? `Cliente elite ${String(index + 1).padStart(2, "0")}`,
        periodo: "",
        metrica: "ticket_medio",
        valor: customer.averageTicket,
        detalhe: `valor_bruto=${customer.totalRevenue ?? ""}; pedidos=${customer.frequency ?? ""}; categorias=${customer.categoryDiversity ?? ""}`,
      })),
      ...(data.customers.topEliteCategories ?? []).map((category) => ({
        secao: "categoria_elite",
        dimensao: category.category ?? category.name,
        periodo: "",
        metrica: "quantidade",
        valor: category.quantity ?? category.units ?? category.value,
        detalhe: category.sharePct !== undefined ? `participacao_pct=${category.sharePct}` : "",
      })),
      ...(data.sales.channels ?? []).map((point) => ({
        secao: "canal",
        dimensao: point.channel ?? point.name ?? point.label,
        periodo: "",
        metrica: "valor_bruto",
        valor: point.revenue ?? point.value ?? point.total,
        detalhe: `pedidos=${point.orders ?? ""}; participacao_pedidos_pct=${point.orderSharePct ?? ""}`,
      })),
    ];
  }

  if (view === "almir") {
    return [
      ...(data.operations.weekdayPos ?? []).map((point) => ({
        secao: "operacao_pos",
        dimensao: point.weekday ?? point.day,
        periodo: "",
        metrica: "valor_bruto_medio_diario",
        valor: point.averageDailySales ?? point.averageSales ?? point.average ?? point.value,
        detalhe: `dias_calendario=${point.calendarDays ?? point.days ?? ""}; dias_zero=${point.zeroSalesDays ?? point.daysWithoutSales ?? point.zeroDays ?? ""}`,
      })),
      ...(data.quality.checks ?? []).map((check) => ({
        secao: "check_qualidade",
        dimensao: check.label ?? check.name,
        periodo: "",
        metrica: check.status,
        valor: check.value,
        detalhe: check.detail ?? check.description,
      })),
    ];
  }

  const forecastRaw = data.operations.forecast;
  const forecastSeries = Array.isArray(forecastRaw)
    ? forecastRaw
    : forecastRaw?.series ?? forecastRaw?.points ?? [];
  const recommendationRaw = data.operations.recommendations;
  const recommendationItems = Array.isArray(recommendationRaw)
    ? recommendationRaw
    : recommendationRaw?.items ?? recommendationRaw?.recommendations ?? [];

  return [
    ...forecastSeries.map((point) => ({
      secao: "previsao",
      dimensao: "demanda_mensal",
      periodo: point.month ?? point.period,
      metrica: "previsao_vs_realizado",
      valor: point.prediction ?? point.predicted ?? point.forecast,
      detalhe: `realizado=${point.actual ?? point.realized ?? ""}; erro_absoluto=${point.absoluteError ?? point.error ?? ""}`,
    })),
    ...recommendationItems.map((item) => ({
      secao: "recomendacao",
      dimensao: item.product ?? item.name,
      periodo: "",
      metrica: "similaridade_cosseno",
      valor: item.similarity ?? item.score,
      detalhe: item.commonCustomers !== undefined ? `clientes_em_comum=${item.commonCustomers}` : item.reason,
    })),
    ...(data.quality.sources ?? []).map((source) => ({
      secao: "fonte",
      dimensao: source.file ?? source.name,
      periodo: "",
      metrica: source.usedForMetrics ? "usada_nas_metricas" : "inventariada",
      valor: source.rows ?? source.records,
      detalhe: source.columns !== undefined ? `${source.columns} colunas` : source.role,
    })),
  ];
}

export function downloadViewCsv(data: DashboardData, view: DashboardView): void {
  const rows = rowsForView(data, view);
  const headers = ["secao", "dimensao", "periodo", "metrica", "valor", "detalhe"];
  const csv = [
    headers.join(";"),
    ...rows.map((row) => headers.map((header) => escapeCell(row[header])).join(";")),
  ].join("\r\n");
  const blob = new Blob(["\uFEFF", csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const date = data.metadata.generatedAt?.slice(0, 10) ?? "snapshot";
  link.href = url;
  link.download = `lh-nautical-${view}-${date}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
