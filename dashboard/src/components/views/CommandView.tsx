import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowUpRight, Compass, Database, Sparkles } from "lucide-react";
import type { DashboardData, Insight } from "../../types/dashboard";
import {
  formatCompact,
  formatCurrency,
  formatMonth,
  formatNumber,
  humanize,
  toNumber,
} from "../../lib/format";
import {
  CHART_COLORS,
  EmptyState,
  MetricCard,
  Panel,
  SectionHeading,
  Tag,
  chartTooltipStyle,
} from "../ui";

function insightCopy(insight: Insight | string): {
  title: string;
  description: string;
  evidence?: string;
  tone: "positive" | "attention" | "neutral";
} {
  if (typeof insight === "string") {
    return { title: "Leitura executiva", description: insight, tone: "neutral" };
  }
  const rawTone = insight.tone?.toLowerCase();
  const tone = rawTone === "positive" ? "positive" : rawTone === "attention" ? "attention" : "neutral";
  return {
    title: insight.title ?? "Leitura executiva",
    description: insight.summary ?? insight.text ?? insight.detail ?? "Insight sem descrição.",
    evidence: insight.evidence ?? insight.impact,
    tone,
  };
}

export function CommandView({ data }: { data: DashboardData }) {
  const cards = data.executive.cards ?? [];
  const insights = data.executive.insights ?? [];
  const monthly = (data.sales.monthly ?? []).map((point) => ({
    label: formatMonth(point.month ?? point.period ?? point.date),
    value: toNumber(point.revenue ?? point.sales ?? point.total),
    orders: toNumber(point.orders),
  }));
  const channels = (data.sales.channels ?? []).map((point) => ({
    name: point.name ?? point.label ?? point.channel ?? "Canal",
    value: toNumber(point.value ?? point.revenue ?? point.total ?? point.count),
  }));
  const channelTotal = channels.reduce((sum, point) => sum + point.value, 0);
  const checks = data.quality.checks ?? [];
  const passingChecks = checks.filter((check) => /pass|ok|success|valid/i.test(check.status ?? ""));

  return (
    <div className="view-stack command-view">
      <div className="command-intro">
        <div className="command-intro__signal">
          <span className="pulse-ring" aria-hidden="true">
            <Compass size={19} />
          </span>
          <div>
            <span>Briefing da operação</span>
            <strong>Visão consolidada para decidir com contexto.</strong>
          </div>
        </div>
        <div className="command-intro__facts">
          <span>
            <Database size={14} aria-hidden="true" />
            {formatNumber(data.metadata.totalRecords)} registros
          </span>
          <span>
            <Sparkles size={14} aria-hidden="true" />
            {checks.length > 0
              ? `${passingChecks.length}/${checks.length} checks aprovados`
              : "Checks não informados"}
          </span>
        </div>
      </div>

      {cards.length > 0 ? (
        <div className="metric-grid">
          {cards.map((card, index) => (
            <MetricCard card={card} index={index} key={card.id ?? `${card.label}-${index}`} />
          ))}
        </div>
      ) : (
        <EmptyState
          title="Indicadores executivos indisponíveis"
          message="A fonte foi carregada, mas não contém cards em executive.cards."
        />
      )}

      <div className="command-grid">
        <Panel className="chart-panel chart-panel--wide" id="command-trend">
          <SectionHeading
            eyebrow="Pulso comercial"
            title="Trajetória mensal"
            description="Evolução no período disponibilizado pela fonte."
            action={<Tag tone="blue">Série completa</Tag>}
          />
          {monthly.length > 0 ? (
            <div className="chart chart--hero" aria-label="Gráfico de trajetória mensal">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={monthly} margin={{ top: 12, right: 6, left: -18, bottom: 0 }}>
                  <defs>
                    <linearGradient id="salesArea" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stopColor="#245BF3" stopOpacity={0.34} />
                      <stop offset="88%" stopColor="#245BF3" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#E6E8F2" strokeDasharray="2 5" vertical={false} />
                  <XAxis
                    axisLine={false}
                    dataKey="label"
                    interval="preserveStartEnd"
                    minTickGap={36}
                    tick={{ fill: "#68708F", fontSize: 11 }}
                    tickLine={false}
                  />
                  <YAxis
                    axisLine={false}
                    tick={{ fill: "#68708F", fontSize: 11 }}
                    tickFormatter={(value) => formatCompact(value)}
                    tickLine={false}
                    width={58}
                  />
                  <Tooltip
                    contentStyle={chartTooltipStyle}
                    cursor={{ stroke: "#BBBAFB", strokeDasharray: "3 3" }}
                    formatter={(value) => [formatCurrency(Number(value)), "Valor"]}
                    labelStyle={{ color: "#AAE3E5", marginBottom: 6 }}
                  />
                  <Area
                    activeDot={{ fill: "#F9F9F9", r: 5, stroke: "#245BF3", strokeWidth: 3 }}
                    dataKey="value"
                    fill="url(#salesArea)"
                    isAnimationActive={false}
                    stroke="#245BF3"
                    strokeWidth={2.5}
                    type="monotone"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState compact message="sales.monthly não trouxe pontos para o período." />
          )}
        </Panel>

        <Panel className="chart-panel channel-panel" id="command-channels">
          <SectionHeading
            eyebrow="Composição"
            title="Canais"
            description="Participação relativa no recorte atual."
          />
          {channels.length > 0 && channelTotal > 0 ? (
            <>
              <div className="donut-wrap">
                <div className="chart chart--donut" aria-label="Distribuição por canal">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        cx="50%"
                        cy="50%"
                        data={channels}
                        dataKey="value"
                        innerRadius="64%"
                        isAnimationActive={false}
                        outerRadius="88%"
                        paddingAngle={3}
                        stroke="none"
                      >
                        {channels.map((point, index) => (
                          <Cell fill={CHART_COLORS[index % CHART_COLORS.length]} key={point.name} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={chartTooltipStyle}
                        formatter={(value) => [formatCurrency(Number(value)), "Valor"]}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="donut-center" aria-hidden="true">
                  <strong>{formatCompact(channelTotal)}</strong>
                  <span>Total</span>
                </div>
              </div>
              <div className="legend-list">
                {channels.map((channel, index) => {
                  const share = (channel.value / channelTotal) * 100;
                  return (
                    <div className="legend-row" key={channel.name}>
                      <span
                        className="legend-swatch"
                        style={{ backgroundColor: CHART_COLORS[index % CHART_COLORS.length] }}
                      />
                      <span className="legend-row__label">{humanize(channel.name)}</span>
                      <strong>{share.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%</strong>
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            <EmptyState compact message="sales.channels não trouxe valores utilizáveis." />
          )}
        </Panel>
      </div>

      <section className="insight-section" id="command-insights">
        <SectionHeading
          eyebrow="Sinais de bordo"
          title="O que os dados estão dizendo"
          description="Leituras mantidas junto da evidência e de suas ressalvas."
        />
        {insights.length > 0 ? (
          <div className="insight-grid">
            {insights.map((rawInsight, index) => {
              const insight = insightCopy(rawInsight);
              return (
                <article className="insight-card" key={`${insight.title}-${index}`}>
                  <div className="insight-card__topline">
                    <span>0{index + 1}</span>
                    <Tag tone={insight.tone}>{humanize(insight.tone)}</Tag>
                  </div>
                  <h3>{insight.title}</h3>
                  <p>{insight.description}</p>
                  {insight.evidence ? (
                    <div className="insight-card__evidence">
                      <ArrowUpRight size={15} aria-hidden="true" />
                      <span>{insight.evidence}</span>
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        ) : (
          <EmptyState compact message="executive.insights está vazio nesta geração." />
        )}
      </section>
    </div>
  );
}
