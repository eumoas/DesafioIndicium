import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Binary,
  Boxes,
  Braces,
  CheckCircle2,
  FileCheck2,
  GitBranch,
  Network,
  Shield,
  TerminalSquare,
  Workflow,
} from "lucide-react";
import type {
  DashboardData,
  ForecastData,
  RecommendationData,
} from "../../types/dashboard";
import {
  formatMonth,
  formatNumber,
  formatPercent,
  toNumber,
} from "../../lib/format";
import {
  EmptyState,
  InlineNotice,
  Panel,
  SectionHeading,
  Tag,
  chartTooltipStyle,
  displayStatus,
  statusTone,
} from "../ui";

export function GabrielView({ data }: { data: DashboardData }) {
  const pipeline = data.quality.pipeline ?? [];
  const forecastRaw = data.operations.forecast;
  const forecast = Array.isArray(forecastRaw) ? undefined : (forecastRaw as ForecastData | undefined);
  const forecastSeries = (Array.isArray(forecastRaw)
    ? forecastRaw
    : forecast?.series ?? forecast?.points ?? []
  ).map((point) => ({
    month: formatMonth(point.month ?? point.period),
    prediction: toNumber(point.prediction ?? point.predicted ?? point.forecast),
    actual: toNumber(point.actual ?? point.realized),
    error: toNumber(point.absoluteError ?? point.error),
  }));

  const recommendationRaw = data.operations.recommendations;
  const recommendations = Array.isArray(recommendationRaw)
    ? undefined
    : (recommendationRaw as RecommendationData | undefined);
  const recommendationItems = Array.isArray(recommendationRaw)
    ? recommendationRaw
    : recommendations?.items ?? recommendations?.recommendations ?? [];

  const sourceCount = Array.isArray(data.metadata.sourceFiles)
    ? data.metadata.sourceFiles.length
    : toNumber(data.metadata.sourceFiles);
  const usedSources = (data.quality.sources ?? []).filter((source) => source.usedForMetrics).length;
  const allChecksPass =
    (data.quality.checks?.length ?? 0) > 0 &&
    (data.quality.checks ?? []).every((check) => statusTone(check.status) === "positive");

  return (
    <div className="view-stack gabriel-view">
      <section className="persona-hero persona-hero--gabriel">
        <div className="persona-hero__copy">
          <span className="persona-icon persona-icon--violet" aria-hidden="true">
            <Braces size={21} />
          </span>
          <div>
            <p className="eyebrow eyebrow--light">Observabilidade da entrega</p>
            <h2>Contrato pequeno. Raciocínio exposto.</h2>
            <p>Um snapshot agregado, com linhagem legível e fronteiras explícitas.</p>
          </div>
        </div>
        <div className="code-stamp" aria-label="Status do contrato de dados">
          <TerminalSquare size={17} aria-hidden="true" />
          <span>
            <code>GET /data/dashboard.json</code>
            <small>{allChecksPass ? "checks publicados: pass" : "consulte os checks publicados"}</small>
          </span>
        </div>
      </section>

      <Panel className="pipeline-panel" id="gabriel-rules">
        <SectionHeading
          eyebrow="Linhagem"
          title="Da descoberta à publicação"
          description="Cada estágio declara o que fez, sem esconder transformações."
          action={<Tag tone="blue">{pipeline.length} etapas</Tag>}
        />
        {pipeline.length > 0 ? (
          <ol className="pipeline-flow">
            {pipeline.map((item, index) => {
              const tone = statusTone(item.status);
              return (
                <li key={item.id ?? `${item.label}-${index}`}>
                  <div className="pipeline-flow__node">
                    <span>{String(item.step ?? index + 1).padStart(2, "0")}</span>
                    <CheckCircle2 size={16} aria-hidden="true" />
                  </div>
                  <div className="pipeline-flow__copy">
                    <div>
                      <strong>{item.label ?? item.name ?? item.title ?? `Etapa ${index + 1}`}</strong>
                      <Tag tone={tone}>{displayStatus(item.status)}</Tag>
                    </div>
                    <p>{item.detail ?? item.description ?? "Sem descrição adicional."}</p>
                  </div>
                </li>
              );
            })}
          </ol>
        ) : (
          <EmptyState compact message="quality.pipeline não trouxe etapas." />
        )}
      </Panel>

      <div className="technical-grid">
        <Panel className="chart-panel technical-grid__forecast">
          <SectionHeading
            eyebrow="Baseline mensurável"
            title={forecast?.product ?? "Previsão de demanda"}
            description={forecast?.method ?? "Método não informado na fonte."}
            action={<Tag tone="attention">Walk-forward</Tag>}
          />
          {forecastSeries.length > 0 ? (
            <>
              <div className="forecast-kpis">
                <div>
                  <span>MAE</span>
                  <strong>{formatNumber(forecast?.mae)} un.</strong>
                  <small>erro absoluto médio</small>
                </div>
                <div>
                  <span>Previsto</span>
                  <strong>{formatNumber(forecast?.predictedTotal ?? forecast?.totalForecast)} un.</strong>
                  <small>total do teste</small>
                </div>
                <div>
                  <span>Realizado</span>
                  <strong>{formatNumber(forecast?.actualTotal ?? forecast?.totalActual)} un.</strong>
                  <small>total do teste</small>
                </div>
                <div className="forecast-kpis__attention">
                  <span>Déficit</span>
                  <strong>{formatNumber(forecast?.shortfall)} un.</strong>
                  <small>subestimação acumulada</small>
                </div>
              </div>
              <div className="chart chart--forecast" aria-label="Previsão e realizado por mês">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={forecastSeries} margin={{ top: 14, right: 8, left: -22, bottom: 0 }}>
                    <CartesianGrid stroke="#E6E8F2" strokeDasharray="2 5" vertical={false} />
                    <XAxis
                      axisLine={false}
                      dataKey="month"
                      tick={{ fill: "#68708F", fontSize: 11 }}
                      tickLine={false}
                    />
                    <YAxis
                      axisLine={false}
                      tick={{ fill: "#68708F", fontSize: 11 }}
                      tickLine={false}
                    />
                    <Tooltip
                      contentStyle={chartTooltipStyle}
                      formatter={(value, name) => [
                        `${formatNumber(Number(value))} un.`,
                        name === "prediction" ? "Previsão" : "Realizado",
                      ]}
                    />
                    <Legend
                      formatter={(value) => (value === "prediction" ? "Previsão" : "Realizado")}
                      iconType="circle"
                      wrapperStyle={{ fontSize: 11, color: "#5C6381" }}
                    />
                    <Line
                      activeDot={{ r: 5, strokeWidth: 3 }}
                      dataKey="prediction"
                      dot={{ r: 4, strokeWidth: 2 }}
                      isAnimationActive={false}
                      stroke="#3D28D9"
                      strokeDasharray="5 4"
                      strokeWidth={2.5}
                      type="monotone"
                    />
                    <Line
                      activeDot={{ r: 5, strokeWidth: 3 }}
                      dataKey="actual"
                      dot={{ r: 4, strokeWidth: 2 }}
                      isAnimationActive={false}
                      stroke="#245BF3"
                      strokeWidth={2.5}
                      type="monotone"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <InlineNotice>
                Baseline é referência comparável, não uma ordem automática de compra. Estoque e lead time não estão no alvo.
              </InlineNotice>
            </>
          ) : (
            <EmptyState compact message="operations.forecast não contém série de teste." />
          )}
        </Panel>

        <Panel className="recommendation-panel" accent>
          <SectionHeading
            eyebrow="Vizinhança de produto"
            title="Recomendações explicáveis"
            description={recommendations?.method ?? "Método não informado na fonte."}
            action={<Network size={19} color="#3D28D9" aria-hidden="true" />}
          />
          {recommendations ? (
            <div className="recommendation-seed">
              <span className="recommendation-seed__icon" aria-hidden="true">
                <Boxes size={18} />
              </span>
              <div>
                <small>Produto de referência</small>
                <strong>{recommendations.targetProduct ?? recommendations.seedProduct ?? recommendations.product}</strong>
              </div>
              {recommendations.targetCustomers ? (
                <Tag tone="neutral">{formatNumber(recommendations.targetCustomers)} clientes</Tag>
              ) : null}
            </div>
          ) : null}
          {recommendationItems.length > 0 ? (
            <ol className="recommendation-list">
              {recommendationItems.map((item, index) => {
                const score = toNumber(item.similarity ?? item.score);
                return (
                  <li key={`${item.product ?? item.name}-${index}`}>
                    <span className="recommendation-list__rank">
                      {String(item.rank ?? index + 1).padStart(2, "0")}
                    </span>
                    <div className="recommendation-list__copy">
                      <div>
                        <strong>{item.product ?? item.name ?? `Produto ${index + 1}`}</strong>
                        <span>{formatPercent(score, 2)} similar</span>
                      </div>
                      <div className="similarity-track" aria-hidden="true">
                        <span style={{ width: `${Math.min(100, score * 100)}%` }} />
                      </div>
                      <small>
                        {item.commonCustomers !== undefined
                          ? `${formatNumber(item.commonCustomers)} clientes em comum`
                          : item.reason ?? "Sem evidência adicional publicada"}
                      </small>
                    </div>
                  </li>
                );
              })}
            </ol>
          ) : (
            <EmptyState compact message="operations.recommendations.items está vazio." />
          )}
        </Panel>
      </div>

      <div className="contract-grid">
        <Panel className="contract-panel">
          <SectionHeading
            eyebrow="Contrato do front-end"
            title="Seis blocos, uma leitura"
            description="O navegador consome apenas o JSON agregado."
            action={<Binary size={19} color="#245BF3" aria-hidden="true" />}
          />
          <div className="contract-map" aria-label="Mapa do contrato JSON">
            {[
              ["metadata", "corte e premissas", FileCheck2],
              ["executive", `${data.executive.cards?.length ?? 0} indicadores`, GitBranch],
              ["sales", `${data.sales.monthly?.length ?? 0} meses`, Workflow],
              ["customers", `${data.customers.eliteTop10?.length ?? 0} posições`, Shield],
              ["operations", "previsão + recomendação", Network],
              ["quality", `${data.quality.checks?.length ?? 0} checks`, CheckCircle2],
            ].map(([name, detail, Icon]) => {
              const ContractIcon = Icon as typeof FileCheck2;
              return (
                <div key={String(name)}>
                  <ContractIcon size={16} aria-hidden="true" />
                  <span>
                    <code>{String(name)}</code>
                    <small>{String(detail)}</small>
                  </span>
                </div>
              );
            })}
          </div>
        </Panel>

        <Panel className="technical-summary" id="gabriel-sources">
          <SectionHeading
            eyebrow="Escopo materializado"
            title="O que está nesta publicação"
            description="Contagens derivadas do próprio contrato."
          />
          <div className="technical-facts">
            <div>
              <span className="technical-facts__icon"><FileCheck2 size={17} /></span>
              <span><small>Fontes inventariadas</small><strong>{formatNumber(sourceCount)}</strong></span>
            </div>
            <div>
              <span className="technical-facts__icon"><GitBranch size={17} /></span>
              <span><small>Fontes analíticas</small><strong>{formatNumber(usedSources)}</strong></span>
            </div>
            <div>
              <span className="technical-facts__icon"><Workflow size={17} /></span>
              <span><small>Etapas publicadas</small><strong>{formatNumber(pipeline.length)}</strong></span>
            </div>
            <div>
              <span className="technical-facts__icon"><Shield size={17} /></span>
              <span><small>Privacidade</small><strong>Saída agregada</strong></span>
            </div>
          </div>
          <div className="gabriel-checks" id="gabriel-checks">
            <div className="gabriel-checks__heading">
              <CheckCircle2 size={15} aria-hidden="true" />
              <strong>Checks executados</strong>
            </div>
            <div className="gabriel-checks__list">
              {(data.quality.checks ?? []).map((check, index) => (
                <span key={check.id ?? `${check.label}-${index}`}>
                  <i className={`status-dot status-dot--${statusTone(check.status)}`} />
                  {check.label ?? check.name ?? `Check ${index + 1}`}
                </span>
              ))}
            </div>
          </div>
          {data.metadata.scope ? (
            <div className="scope-note">
              <code>scope</code>
              <p>{data.metadata.scope}</p>
            </div>
          ) : null}
        </Panel>
      </div>
    </div>
  );
}
