import { useState, type ReactNode } from "react";
import { AlertTriangle, DatabaseZap, RefreshCw } from "lucide-react";
import { DashboardShell } from "./components/DashboardShell";
import { AlmirView } from "./components/views/AlmirView";
import { CommandView } from "./components/views/CommandView";
import { GabrielView } from "./components/views/GabrielView";
import { MarinaView } from "./components/views/MarinaView";
import { ViewExplorer } from "./components/ViewExplorer";
import { useDashboardData } from "./hooks/useDashboardData";
import type { DashboardView } from "./types/dashboard";

function LoadingScreen() {
  return (
    <main className="loading-screen" data-testid="dashboard-loading" aria-busy="true">
      <div className="loading-sidebar">
        <div className="skeleton skeleton--brand" />
        {[0, 1, 2, 3].map((item) => (
          <div className="skeleton skeleton--nav" key={item} />
        ))}
      </div>
      <div className="loading-content">
        <div className="loading-content__header">
          <div>
            <div className="skeleton skeleton--eyebrow" />
            <div className="skeleton skeleton--title" />
            <div className="skeleton skeleton--text" />
          </div>
          <div className="skeleton skeleton--chip" />
        </div>
        <div className="loading-cards">
          {[0, 1, 2, 3].map((item) => (
            <div className="skeleton skeleton--card" key={item} />
          ))}
        </div>
        <div className="loading-panels">
          <div className="skeleton skeleton--panel" />
          <div className="skeleton skeleton--panel skeleton--panel-small" />
        </div>
        <p className="loading-label">
          <DatabaseZap size={16} aria-hidden="true" />
          Lendo o snapshot analítico…
        </p>
      </div>
    </main>
  );
}

function ErrorScreen({ error, onRetry }: { error: string; onRetry: () => void }) {
  return (
    <main className="error-screen" data-testid="dashboard-error">
      <div className="error-screen__grid" aria-hidden="true" />
      <section className="error-card">
        <span className="error-card__icon" aria-hidden="true">
          <AlertTriangle size={24} />
        </span>
        <p className="eyebrow">Fonte indisponível</p>
        <h1>Não foi possível montar o painel.</h1>
        <p>
          Nenhum número substituto foi exibido. Verifique se o arquivo
          <code>/data/dashboard.json</code> está acessível e tente novamente.
        </p>
        <div className="error-detail" role="alert">
          {error}
        </div>
        <button className="primary-button" onClick={onRetry} type="button">
          <RefreshCw size={16} aria-hidden="true" />
          Tentar novamente
        </button>
      </section>
    </main>
  );
}

export default function App() {
  const [activeView, setActiveView] = useState<DashboardView>("command");
  const { data, error, isLoading, retry } = useDashboardData();

  if (isLoading) return <LoadingScreen />;
  if (error || !data) {
    return <ErrorScreen error={error ?? "Resposta vazia."} onRetry={retry} />;
  }

  const views = {
    command: <CommandView data={data} />,
    marina: <MarinaView data={data} />,
    almir: <AlmirView data={data} />,
    gabriel: <GabrielView data={data} />,
  } satisfies Record<DashboardView, ReactNode>;

  return (
    <DashboardShell
      activeView={activeView}
      metadata={data.metadata}
      onViewChange={setActiveView}
    >
      <ViewExplorer data={data} view={activeView} />
      {views[activeView]}
    </DashboardShell>
  );
}
