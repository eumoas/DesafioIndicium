import { useState, type CSSProperties } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Crown, EyeOff, Radio, ShoppingBag, Target, Users } from "lucide-react";
import type { DashboardData, NumericValue } from "../../types/dashboard";
import {
  formatCompact,
  formatCurrency,
  formatNumber,
  formatPercent,
  toNumber,
} from "../../lib/format";
import {
  CHART_COLORS,
  EmptyState,
  InlineNotice,
  Panel,
  SectionHeading,
  Tag,
  chartTooltipItemStyle,
  chartTooltipLabelStyle,
  chartTooltipStyle,
} from "../ui";

function indexedNumber(record: Record<string, unknown>, keys: string[]): number {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "number" || typeof value === "string" || value === null) {
      return toNumber(value as NumericValue);
    }
  }
  return 0;
}

export function MarinaView({ data }: { data: DashboardData }) {
  const [channelMetric, setChannelMetric] = useState<"value" | "orders">("value");
  const elite = (data.customers.eliteTop10 ?? []).map((customer, index) => ({
    name: customer.customerLabel ?? `Cliente elite ${String(customer.rank ?? index + 1).padStart(2, "0")}`,
    value: toNumber(customer.averageTicket),
    grossValue: toNumber(customer.totalRevenue ?? customer.revenue),
    orders: toNumber(customer.frequency ?? customer.orders ?? customer.orderCount),
    ticket: toNumber(customer.averageTicket),
    months: toNumber(customer.months ?? customer.activeMonths),
  }));
  const categories = (data.customers.topEliteCategories ?? []).map((category) => ({
    name: category.category ?? category.name ?? "Categoria",
    value: toNumber(category.units ?? category.quantity ?? category.value),
  }));
  const channels = (data.sales.channels ?? []).map((channel) => ({
    name: channel.channel ?? channel.name ?? channel.label ?? "Canal",
    value: toNumber(channel.revenue ?? channel.value ?? channel.total),
    orders: toNumber(channel.orders ?? channel.count),
    valueShare: toNumber(channel.revenueSharePct ?? channel.percentage),
    orderShare: toNumber(channel.orderSharePct),
  }));

  const eligibilityRaw = data.customers.eligibility;
  const eligibility = !Array.isArray(eligibilityRaw) ? eligibilityRaw : undefined;
  const eligible = eligibility
    ? indexedNumber(eligibility, ["eligibleCustomers", "eligible", "eliteCustomers", "elite"])
    : 0;
  const customers = eligibility
    ? indexedNumber(eligibility, ["registeredCustomers", "totalCustomers", "total", "customers"])
    : 0;
  const explicitShare = eligibility
    ? indexedNumber(eligibility, ["eligibleSharePct", "percentage", "share", "eligiblePercentage"])
    : 0;
  const share = explicitShare || (customers > 0 ? eligible / customers : 0);
  const criteria = eligibility?.criteria ?? eligibility?.rules ?? (eligibility?.rule ? [eligibility.rule] : []);
  const topCategory = categories[0];

  return (
    <div className="view-stack marina-view">
      <section className="persona-hero persona-hero--marina">
        <div className="persona-hero__copy">
          <span className="persona-icon" aria-hidden="true">
            <Target size={21} />
          </span>
          <div>
            <p className="eyebrow eyebrow--light">Radar de oportunidade</p>
            <h2>Do número à próxima conversa comercial.</h2>
            <p>Uma leitura agregada da base, sem expor nomes ou identificadores de clientes.</p>
          </div>
        </div>
        <div className="persona-hero__stats">
          <div>
            <span>Elite no ranking</span>
            <strong>{elite.length > 0 ? elite.length : "—"}</strong>
          </div>
          <div>
            <span>Categoria líder</span>
            <strong>{topCategory?.name ?? "Não informada"}</strong>
          </div>
        </div>
      </section>

      <div className="business-grid">
        <Panel className="chart-panel business-grid__ranking" id="marina-priority">
          <SectionHeading
            eyebrow="Valor por relacionamento"
            title="Top 10 por ticket médio"
            description="Rótulos anonimizados na apresentação; apenas métricas agregadas."
            action={
              <Tag tone="positive">
                <EyeOff size={12} aria-hidden="true" /> Sem PII
              </Tag>
            }
          />
          {elite.length > 0 ? (
            <div className="chart chart--ranking" aria-label="Ranking anonimizado dos clientes elite">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={elite}
                  layout="vertical"
                  margin={{ top: 2, right: 18, left: 4, bottom: 2 }}
                >
                  <CartesianGrid horizontal={false} stroke="#E6E8F2" strokeDasharray="2 5" />
                  <XAxis
                    axisLine={false}
                    tick={{ fill: "#59617E", fontSize: 12, fontWeight: 550 }}
                    tickFormatter={(value) => formatCompact(value)}
                    tickLine={false}
                    type="number"
                  />
                  <YAxis
                    axisLine={false}
                    dataKey="name"
                    tick={{ fill: "#303554", fontSize: 12, fontFamily: "Roboto Mono", fontWeight: 550 }}
                    tickLine={false}
                    type="category"
                    width={112}
                  />
                  <Tooltip
                    contentStyle={chartTooltipStyle}
                    cursor={{ fill: "rgba(36, 91, 243, 0.06)" }}
                    formatter={(value) => [formatCurrency(Number(value)), "Ticket médio"]}
                    itemStyle={chartTooltipItemStyle}
                    labelStyle={chartTooltipLabelStyle}
                  />
                  <Bar dataKey="value" isAnimationActive={false} radius={[0, 7, 7, 0]}>
                    {elite.map((customer, index) => (
                      <Cell
                        fill={index < 3 ? CHART_COLORS[index] : "#A9B7D7"}
                        key={customer.name}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState compact message="customers.eliteTop10 não contém registros." />
          )}
        </Panel>

        <Panel className="eligibility-panel" accent>
          <SectionHeading
            eyebrow="Cobertura do critério"
            title="Quem entra na elite?"
            description="O denominador e as regras permanecem visíveis."
          />
          {eligibility ? (
            <>
              <div className="eligibility-score">
                <div
                  className="eligibility-score__ring"
                  style={{ "--score": `${Math.max(0, Math.min(100, share > 1 ? share : share * 100)) * 3.6}deg` } as CSSProperties}
                >
                  <span>
                    <strong>{formatPercent(share)}</strong>
                    <small>da base</small>
                  </span>
                </div>
                <div className="eligibility-score__copy">
                  <div>
                    <Users size={17} aria-hidden="true" />
                    <span>Elegíveis</span>
                    <strong>{eligible > 0 ? formatNumber(eligible) : "—"}</strong>
                  </div>
                  <div>
                    <ShoppingBag size={17} aria-hidden="true" />
                    <span>Clientes avaliados</span>
                    <strong>{customers > 0 ? formatNumber(customers) : "—"}</strong>
                  </div>
                </div>
              </div>
              {criteria.length > 0 ? (
                <div className="criteria-list">
                  <p>Critérios considerados</p>
                  {criteria.map((criterion, index) => (
                    <div key={`${criterion}-${index}`}>
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      <p>{criterion}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <InlineNotice>Os totais estão disponíveis, mas os critérios não vieram descritos.</InlineNotice>
              )}
            </>
          ) : (
            <EmptyState compact message="customers.eligibility não está disponível como resumo." />
          )}
        </Panel>
      </div>

      <div className="business-grid business-grid--lower">
        <Panel className="chart-panel" id="marina-offers">
          <SectionHeading
            eyebrow="Afinidade da elite"
            title="Categorias mais compradas"
            description="Quantidade observada dentro do segmento elegível."
            action={<Crown size={18} color="#3D28D9" aria-hidden="true" />}
          />
          {categories.length > 0 ? (
            <div className="category-bars">
              {categories.map((category, index) => {
                const max = Math.max(...categories.map((point) => point.value), 1);
                return (
                  <div className="category-row" key={`${category.name}-${index}`}>
                    <span className="category-row__rank">{String(index + 1).padStart(2, "0")}</span>
                    <div className="category-row__main">
                      <div className="category-row__label">
                        <span>{category.name}</span>
                        <strong>{formatNumber(category.value)} un.</strong>
                      </div>
                      <div className="progress-track" aria-hidden="true">
                        <span
                          style={{
                            width: `${Math.max(2, (category.value / max) * 100)}%`,
                            backgroundColor: CHART_COLORS[index % CHART_COLORS.length],
                          }}
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <EmptyState compact message="customers.topEliteCategories está vazio." />
          )}
        </Panel>

        <Panel className="status-panel" id="marina-growth">
          <SectionHeading
            eyebrow="Espaço de crescimento"
            title="Comparativo por canal"
            description="Alterne a lente sem mudar o recorte de dados."
            action={<Radio size={18} color="#245BF3" aria-hidden="true" />}
          />
          <div className="metric-toggle" role="group" aria-label="Métrica do comparativo por canal">
            <button
              aria-pressed={channelMetric === "value"}
              className={channelMetric === "value" ? "is-active" : ""}
              onClick={() => setChannelMetric("value")}
              type="button"
            >
              Valor bruto
            </button>
            <button
              aria-pressed={channelMetric === "orders"}
              className={channelMetric === "orders" ? "is-active" : ""}
              onClick={() => setChannelMetric("orders")}
              type="button"
            >
              Pedidos
            </button>
          </div>
          {channels.length > 0 ? (
            <div className="channel-compare">
              {channels.map((channel, index) => {
                const currentValue = channelMetric === "value" ? channel.value : channel.orders;
                const maximum = Math.max(
                  ...channels.map((item) => (channelMetric === "value" ? item.value : item.orders)),
                  1,
                );
                const shareValue = channelMetric === "value" ? channel.valueShare : channel.orderShare;
                return (
                  <div className="channel-compare__row" key={`${channel.name}-${index}`}>
                    <div className="channel-compare__label">
                      <span>{channel.name === "pos" ? "Lojas físicas" : "E-commerce"}</span>
                      <strong>
                        {channelMetric === "value"
                          ? formatCurrency(currentValue, true)
                          : `${formatNumber(currentValue)} pedidos`}
                      </strong>
                    </div>
                    <div className="channel-compare__track" aria-hidden="true">
                      <span
                        style={{
                          backgroundColor: CHART_COLORS[index % CHART_COLORS.length],
                          width: `${(currentValue / maximum) * 100}%`,
                        }}
                      />
                    </div>
                    <small>{formatPercent(shareValue)} do recorte</small>
                  </div>
                );
              })}
              <InlineNotice>
                O comparativo descreve a base; decidir investimento exige custos, margem e capacidade por canal.
              </InlineNotice>
            </div>
          ) : (
            <EmptyState compact message="sales.channels não trouxe uma composição utilizável." />
          )}
        </Panel>
      </div>
    </div>
  );
}
