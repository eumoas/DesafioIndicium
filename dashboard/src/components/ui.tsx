import type { CSSProperties, ReactNode } from "react";
import { AlertCircle, ArrowDownRight, ArrowUpRight, Inbox } from "lucide-react";
import type { ExecutiveCard } from "../types/dashboard";
import { formatCompact, formatCurrency, formatNumber, humanize, toNumber } from "../lib/format";

export const CHART_COLORS = [
  "#245BF3",
  "#3D28D9",
  "#0957CF",
  "#AAE3E5",
  "#BBBAFB",
  "#7A8CBF",
] as const;

export const chartTooltipStyle: CSSProperties = {
  background: "rgba(5, 7, 63, 0.96)",
  border: "1px solid rgba(187, 186, 251, 0.26)",
  borderRadius: "12px",
  boxShadow: "0 14px 36px rgba(5, 7, 63, 0.2)",
  color: "#F9F9F9",
  fontFamily: "Inter, sans-serif",
  fontSize: "12px",
};

export function Panel({
  children,
  className = "",
  accent = false,
  id,
}: {
  children: ReactNode;
  className?: string;
  accent?: boolean;
  id?: string;
}) {
  return (
    <section className={`panel ${accent ? "panel--accent" : ""} ${className}`} id={id}>
      {children}
    </section>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="section-heading">
      <div>
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h2>{title}</h2>
        {description ? <p className="section-description">{description}</p> : null}
      </div>
      {action ? <div className="section-action">{action}</div> : null}
    </div>
  );
}

export function Tag({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "positive" | "attention" | "danger" | "blue";
}) {
  return <span className={`tag tag--${tone}`}>{children}</span>;
}

function inferCardValue(card: ExecutiveCard): string {
  if (card.displayValue) return card.displayValue;
  const value = card.value;
  if (value === null || value === undefined || value === "") return "—";

  const format = card.format?.toLowerCase();
  if (format === "currency") {
    return formatCurrency(value, Math.abs(toNumber(value)) >= 1_000_000);
  }
  if (format === "percent") return `${formatNumber(value)}%`;
  if (format === "integer") return formatNumber(value);

  const descriptor = `${card.unit ?? ""} ${card.label ?? ""} ${card.title ?? ""}`.toLowerCase();
  if (/r\$|brl|receita|faturamento|lucro|ticket|valor/.test(descriptor)) {
    return formatCurrency(value, Math.abs(toNumber(value)) >= 1_000_000);
  }
  if (/%|percent|taxa/.test(descriptor)) return `${formatNumber(value)}%`;
  return Math.abs(toNumber(value)) >= 1_000_000 ? formatCompact(value) : formatNumber(value);
}

export function MetricCard({
  card,
  index,
}: {
  card: ExecutiveCard;
  index: number;
}) {
  const trend = card.trend?.toLowerCase();
  const change = card.change === null || card.change === undefined ? null : toNumber(card.change);
  const isDown = trend === "down" || (change !== null && change < 0);
  const TrendIcon = isDown ? ArrowDownRight : ArrowUpRight;
  const label = card.label ?? card.title ?? `Indicador ${index + 1}`;

  return (
    <article className="metric-card" data-testid={`metric-card-${index}`}>
      <div className="metric-card__rail" aria-hidden="true" />
      <div className="metric-card__header">
        <span>{label}</span>
        <span className="metric-card__index">0{index + 1}</span>
      </div>
      <strong>{inferCardValue(card)}</strong>
      <div className="metric-card__footer">
        <p>{card.detail ?? card.description ?? card.source ?? "Indicador consolidado"}</p>
        {change !== null ? (
          <span className={`metric-trend ${isDown ? "metric-trend--down" : ""}`}>
            <TrendIcon size={13} aria-hidden="true" />
            {formatNumber(Math.abs(change))}{card.unit === "%" ? "%" : ""}
          </span>
        ) : null}
      </div>
    </article>
  );
}

export function EmptyState({
  title = "Sem dados para exibir",
  message = "Esta seção não recebeu registros na fonte atual.",
  compact = false,
}: {
  title?: string;
  message?: string;
  compact?: boolean;
}) {
  return (
    <div className={`empty-state ${compact ? "empty-state--compact" : ""}`}>
      <span className="empty-state__icon" aria-hidden="true">
        <Inbox size={18} />
      </span>
      <div>
        <strong>{title}</strong>
        <p>{message}</p>
      </div>
    </div>
  );
}

export function InlineNotice({
  children,
  tone = "attention",
}: {
  children: ReactNode;
  tone?: "attention" | "info";
}) {
  return (
    <div className={`inline-notice inline-notice--${tone}`}>
      <AlertCircle size={17} aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}

export function statusTone(status?: string): "positive" | "attention" | "danger" | "neutral" {
  const normalized = status?.toLowerCase() ?? "";
  if (/pass|ok|success|complete|valid|pronto/.test(normalized)) return "positive";
  if (/warn|attention|review|pending|ressalva/.test(normalized)) return "attention";
  if (/fail|error|invalid|bloqueado/.test(normalized)) return "danger";
  return "neutral";
}

export function displayStatus(status?: string): string {
  return status ? humanize(status) : "Informativo";
}
