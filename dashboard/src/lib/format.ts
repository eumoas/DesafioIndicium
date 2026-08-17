import type { NumericValue } from "../types/dashboard";

const numberFormatter = new Intl.NumberFormat("pt-BR", {
  maximumFractionDigits: 2,
});

const compactFormatter = new Intl.NumberFormat("pt-BR", {
  notation: "compact",
  maximumFractionDigits: 1,
});

const currencyFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 2,
});

const compactCurrencyFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  notation: "compact",
  maximumFractionDigits: 1,
});

export function toNumber(value: NumericValue | undefined): number {
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  if (typeof value !== "string") return 0;

  const normalized = value
    .trim()
    .replace(/[^\d,.-]/g, "")
    .replace(/\.(?=\d{3}(?:\D|$))/g, "")
    .replace(",", ".");
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function formatNumber(value: NumericValue | undefined): string {
  return numberFormatter.format(toNumber(value));
}

export function formatCompact(value: NumericValue | undefined): string {
  return compactFormatter.format(toNumber(value));
}

export function formatCurrency(
  value: NumericValue | undefined,
  compact = false,
): string {
  return (compact ? compactCurrencyFormatter : currencyFormatter).format(
    toNumber(value),
  );
}

export function formatPercent(
  value: NumericValue | undefined,
  maximumFractionDigits = 1,
): string {
  const numeric = toNumber(value);
  const normalized = Math.abs(numeric) > 1 ? numeric / 100 : numeric;
  return new Intl.NumberFormat("pt-BR", {
    style: "percent",
    maximumFractionDigits,
  }).format(normalized);
}

export function formatDate(value?: string, withTime = false): string {
  if (!value) return "Não informado";
  const dateInput = /^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T12:00:00` : value;
  const date = new Date(dateInput);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    ...(withTime
      ? { hour: "2-digit", minute: "2-digit" }
      : {}),
  }).format(date);
}

export function formatMonth(value?: string): string {
  if (!value) return "—";
  const normalized = /^\d{4}-\d{2}$/.test(value) ? `${value}-01T12:00:00` : value;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("pt-BR", {
    month: "short",
    year: "2-digit",
  })
    .format(date)
    .replace(" de ", " · ");
}

export function humanize(value?: string): string {
  if (!value) return "Não informado";
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function getPeriodLabel(
  period?: { start?: string; end?: string; min?: string; max?: string } | string,
): string {
  if (!period) return "Período não informado";
  if (typeof period === "string") return period;
  const start = period.start ?? period.min;
  const end = period.end ?? period.max;
  if (!start && !end) return "Período não informado";
  return `${formatDate(start)} — ${formatDate(end)}`;
}
