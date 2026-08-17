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
import {
  Anchor,
  Check,
  ChevronDown,
  CircleAlert,
  Database,
  FileJson2,
  HardDrive,
  Scale,
  ShieldCheck,
} from "lucide-react";
import type { DashboardData } from "../../types/dashboard";
import { formatCompact, formatCurrency, formatNumber, toNumber } from "../../lib/format";
import {
  EmptyState,
  InlineNotice,
  Panel,
  SectionHeading,
  Tag,
  chartTooltipItemStyle,
  chartTooltipLabelStyle,
  chartTooltipStyle,
  displayStatus,
  statusTone,
} from "../ui";

export function AlmirView({ data }: { data: DashboardData }) {
  const [weekdayMetric, setWeekdayMetric] = useState<"average" | "zeros">("average");
  const weekdays = (data.operations.weekdayPos ?? []).map((point) => ({
    name: point.weekday ?? point.day ?? "Dia",
    value: toNumber(point.averageDailySales ?? point.averageSales ?? point.average ?? point.value),
    days: toNumber(point.calendarDays ?? point.days),
    zeroDays: toNumber(point.zeroSalesDays ?? point.zeroDays ?? point.daysWithoutSales),
    isLowest: point.isLowest ?? false,
  }));
  const lowest = weekdays.length > 0
    ? weekdays.find((point) => point.isLowest) ?? weekdays.reduce((current, point) => (point.value < current.value ? point : current))
    : null;
  const forecastRaw = data.operations.forecast;
  const forecast = Array.isArray(forecastRaw) ? undefined : forecastRaw;
  const checks = data.quality.checks ?? [];
  const assumptions = (data.metadata.assumptions ?? []).map((assumption, index) =>
    typeof assumption === "string"
      ? { id: `assumption-${index}`, title: "Premissa documentada", detail: assumption }
      : {
          id: assumption.id ?? `assumption-${index}`,
          title: assumption.title ?? "Premissa documentada",
          detail: assumption.detail ?? "Sem detalhe adicional.",
        },
  );
  const sources = data.quality.sources ?? [];
  const passingChecks = checks.filter((check) => statusTone(check.status) === "positive").length;
  const trustPercent = checks.length > 0 ? (passingChecks / checks.length) * 100 : 0;

  return (
    <div className="view-stack almir-view">
      <section className="persona-hero persona-hero--almir">
        <div className="persona-hero__copy">
          <span className="persona-icon persona-icon--cyan" aria-hidden="true">
            <Anchor size={21} />
          </span>
          <div>
            <p className="eyebrow eyebrow--light">Prestação de contas</p>
            <h2>O número, a origem e a ressalva.</h2>
            <p>O painel lê um snapshot local e preserva o caminho de volta até a evidência.</p>
          </div>
        </div>
        <div className="almir-proof">
          <HardDrive size={18} aria-hidden="true" />
          <span>
            <small>Modo de leitura</small>
            <strong>Arquivo local · sem conexão operacional</strong>
          </span>
        </div>
      </section>

      <div className="trust-strip">
        <div className="trust-strip__score">
          <span className="trust-icon" aria-hidden="true">
            <ShieldCheck size={23} />
          </span>
          <div>
            <small>Checks aprovados</small>
            <strong>{checks.length > 0 ? `${passingChecks} de ${checks.length}` : "Não informados"}</strong>
          </div>
        </div>
        <div className="trust-strip__bar" aria-label={`${trustPercent.toFixed(0)}% dos checks aprovados`}>
          <span style={{ width: `${trustPercent}%` }} />
        </div>
        <p>Indicador de execução dos checks publicados — não é certificação contábil.</p>
      </div>

      <div className="almir-answer-grid">
        <article id="almir-worst-day">
          <span className="almir-answer-grid__index">01</span>
          <div>
            <small>Menor média observada</small>
            <strong>{lowest?.name ?? "Não informada"}</strong>
            <p>{lowest ? formatCurrency(lowest.value) : "Sem dados no recorte"}</p>
          </div>
        </article>
        <article id="almir-forecast">
          <span className="almir-answer-grid__index">02</span>
          <div>
            <small>Erro do baseline</small>
            <strong>{forecast?.mae !== undefined ? `${formatNumber(forecast.mae)} un.` : "Não informado"}</strong>
            <p>{forecast?.shortfall !== undefined ? `${formatNumber(forecast.shortfall)} un. de déficit no teste` : "Sem déficit publicado"}</p>
          </div>
        </article>
        <article id="almir-caution">
          <span className="almir-answer-grid__index">03</span>
          <div>
            <small>Decisão insegura</small>
            <strong>Fechar loja só pela média</strong>
            <p>Faltam custos, margem e leitura por unidade.</p>
          </div>
        </article>
      </div>

      <div className="operations-grid">
        <Panel className="chart-panel operations-grid__chart">
          <SectionHeading
            eyebrow="Operação física"
            title={weekdayMetric === "average" ? "Valor bruto médio por dia" : "Dias sem venda registrada"}
            description="Alterne entre resultado médio e composição dos zeros do calendário."
            action={lowest ? <Tag tone="attention">Menor: {lowest.name}</Tag> : undefined}
          />
          <div className="metric-toggle" role="group" aria-label="Métrica operacional por dia da semana">
            <button
              aria-pressed={weekdayMetric === "average"}
              className={weekdayMetric === "average" ? "is-active" : ""}
              onClick={() => setWeekdayMetric("average")}
              type="button"
            >
              Média diária
            </button>
            <button
              aria-pressed={weekdayMetric === "zeros"}
              className={weekdayMetric === "zeros" ? "is-active" : ""}
              onClick={() => setWeekdayMetric("zeros")}
              type="button"
            >
              Dias zerados
            </button>
          </div>
          {weekdays.length > 0 ? (
            <div className="chart chart--weekday" aria-label="Média de vendas por dia da semana">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={weekdays} margin={{ top: 18, right: 8, left: -12, bottom: 0 }}>
                  <CartesianGrid stroke="#E6E8F2" strokeDasharray="2 5" vertical={false} />
                  <XAxis
                    axisLine={false}
                    dataKey="name"
                    tick={{ fill: "#505878", fontSize: 12, fontWeight: 550 }}
                    tickFormatter={(value) => String(value).replace("-feira", "").slice(0, 3)}
                    tickLine={false}
                  />
                  <YAxis
                    axisLine={false}
                    tick={{ fill: "#59617E", fontSize: 12, fontWeight: 550 }}
                    tickFormatter={(value) => weekdayMetric === "average" ? formatCompact(value) : formatNumber(value)}
                    tickLine={false}
                    width={62}
                  />
                  <Tooltip
                    contentStyle={chartTooltipStyle}
                    cursor={{ fill: "rgba(170, 227, 229, 0.18)" }}
                    formatter={(value) => [
                      weekdayMetric === "average" ? formatCurrency(Number(value)) : `${formatNumber(Number(value))} dias`,
                      weekdayMetric === "average" ? "Valor bruto médio" : "Dias zerados",
                    ]}
                    itemStyle={chartTooltipItemStyle}
                    labelStyle={chartTooltipLabelStyle}
                  />
                  <Bar
                    dataKey={weekdayMetric === "average" ? "value" : "zeroDays"}
                    isAnimationActive={false}
                    radius={[8, 8, 2, 2]}
                  >
                    {weekdays.map((day) => (
                      <Cell
                        fill={day.name === lowest?.name ? "#3D28D9" : "#AAE3E5"}
                        key={day.name}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState compact message="operations.weekdayPos não contém pontos." />
          )}
          {lowest ? (
            <InlineNotice>
              <strong>{lowest.name}</strong> tem o menor valor no recorte ({formatCurrency(lowest.value)}),
              mas essa comparação isolada não determina fechamento de loja.
            </InlineNotice>
          ) : null}
        </Panel>

        <Panel className="method-panel" accent>
          <SectionHeading
            eyebrow="Conta aberta"
            title="Como a média nasce"
            description="Quatro movimentos simples, sem algoritmo opaco."
          />
          <ol className="method-steps">
            <li>
              <span>01</span>
              <div>
                <strong>Separar o canal físico</strong>
                <p>Usar a definição de canal publicada na fonte.</p>
              </div>
            </li>
            <li>
              <span>02</span>
              <div>
                <strong>Somar por data</strong>
                <p>Vários pedidos do mesmo dia viram um total diário.</p>
              </div>
            </li>
            <li>
              <span>03</span>
              <div>
                <strong>Completar o calendário</strong>
                <p>Dias sem venda aparecem explicitamente com zero.</p>
              </div>
            </li>
            <li>
              <span>04</span>
              <div>
                <strong>Calcular a média</strong>
                <p>O denominador considera todos os dias do período.</p>
              </div>
            </li>
          </ol>
        </Panel>
      </div>

      <div className="evidence-grid">
        <Panel className="check-panel">
          <SectionHeading
            eyebrow="Evidência de qualidade"
            title="Checklist publicado"
            description="Cada item mantém seu estado e explicação original."
          />
          {checks.length > 0 ? (
            <div className="check-list">
              {checks.map((check, index) => {
                const tone = statusTone(check.status);
                const Icon = tone === "positive" ? Check : CircleAlert;
                return (
                  <article className={`check-row check-row--${tone}`} key={check.id ?? `${check.name}-${index}`}>
                    <span className="check-row__icon" aria-hidden="true">
                      <Icon size={15} />
                    </span>
                    <div>
                      <strong>{check.label ?? check.name ?? `Check ${index + 1}`}</strong>
                      <p>{check.detail ?? check.description ?? "Sem descrição adicional."}</p>
                    </div>
                    <Tag tone={tone}>{displayStatus(check.status)}</Tag>
                  </article>
                );
              })}
            </div>
          ) : (
            <EmptyState compact message="quality.checks está vazio." />
          )}
        </Panel>

        <Panel className="source-panel">
          <SectionHeading
            eyebrow="Fontes utilizadas"
            title="Arquivos no convés"
            description="Somente contagens e funções — nenhum dado pessoal."
          />
          {sources.length > 0 ? (
            <div className="source-list">
              {sources.map((source, index) => (
                <div className="source-row" key={`${source.file ?? source.name}-${index}`}>
                  <span className="source-row__icon" aria-hidden="true">
                    <FileJson2 size={16} />
                  </span>
                  <div>
                    <strong>{source.file ?? source.name ?? `Fonte ${index + 1}`}</strong>
                    <small>{source.role ?? "Fonte analítica"}</small>
                  </div>
                  <span>{formatNumber(source.records ?? source.rows)} linhas</span>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState compact message="quality.sources não lista arquivos nesta geração." />
          )}
          <div className="source-summary">
            <Database size={17} aria-hidden="true" />
            <span>
              <small>Total informado</small>
              <strong>{formatNumber(data.metadata.totalRecords)} registros</strong>
            </span>
          </div>
        </Panel>
      </div>

      <Panel className="assumption-panel">
        <SectionHeading
          eyebrow="Antes de decidir"
          title="Premissas e limites"
          description="Abra cada linha para revisar o que o dado ainda não resolve sozinho."
          action={<Scale size={19} color="#3D28D9" aria-hidden="true" />}
        />
        {assumptions.length > 0 ? (
          <div className="assumption-list">
            {assumptions.map((assumption, index) => (
              <details key={assumption.id}>
                <summary>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <strong>{assumption.title}</strong>
                  <ChevronDown size={16} aria-hidden="true" />
                </summary>
                <p>{assumption.detail}</p>
              </details>
            ))}
          </div>
        ) : (
          <EmptyState compact message="metadata.assumptions não contém itens." />
        )}
      </Panel>
    </div>
  );
}
import { useState } from "react";
