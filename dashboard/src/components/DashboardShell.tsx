import type { ReactNode } from "react";
import {
  Anchor,
  Braces,
  CalendarRange,
  ChevronRight,
  LayoutDashboard,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import type { DashboardMetadata, DashboardView } from "../types/dashboard";
import { formatDate, getPeriodLabel } from "../lib/format";

interface NavItem {
  id: DashboardView;
  label: string;
  descriptor: string;
  icon: typeof LayoutDashboard;
}

const navItems: NavItem[] = [
  {
    id: "command",
    label: "Ponte de Comando",
    descriptor: "Visão executiva",
    icon: LayoutDashboard,
  },
  {
    id: "marina",
    label: "Marina",
    descriptor: "Negócios & clientes",
    icon: TrendingUp,
  },
  {
    id: "almir",
    label: "Sr. Almir",
    descriptor: "Confiança & operação",
    icon: Anchor,
  },
  {
    id: "gabriel",
    label: "Gabriel",
    descriptor: "Método & rastreio",
    icon: Braces,
  },
];

const viewCopy: Record<DashboardView, { eyebrow: string; title: string; description: string }> = {
  command: {
    eyebrow: "Leitura consolidada",
    title: "Ponte de Comando",
    description: "O que merece atenção antes da próxima decisão.",
  },
  marina: {
    eyebrow: "Gerência de negócios",
    title: "Radar da Marina",
    description: "Clientes, valor e oportunidades em linguagem de negócio.",
  },
  almir: {
    eyebrow: "Fundamentos verificáveis",
    title: "Caderno do Sr. Almir",
    description: "Números rastreáveis, premissas abertas e operação sem caixa-preta.",
  },
  gabriel: {
    eyebrow: "Sala técnica",
    title: "Console do Gabriel",
    description: "Qualidade, linhagem e limites da solução em um só lugar.",
  },
};

export function DashboardShell({
  activeView,
  onViewChange,
  metadata,
  children,
}: {
  activeView: DashboardView;
  onViewChange: (view: DashboardView) => void;
  metadata: DashboardMetadata;
  children: ReactNode;
}) {
  const current = viewCopy[activeView];

  return (
    <div className="dashboard-shell" data-testid="dashboard-shell">
      <a className="skip-link" href="#dashboard-content">
        Ir para o conteúdo
      </a>
      <aside className="sidebar">
        <div className="brand-lockup" aria-label="LH Nautical Intelligence">
          <span className="brand-mark" aria-hidden="true">
            <span>LH</span>
          </span>
          <span className="brand-name">
            <strong>LH Nautical</strong>
            <small>Intelligence deck</small>
          </span>
        </div>

        <div className="sidebar-label">Navegação por perfil</div>
        <nav className="sidebar-nav" aria-label="Visões do dashboard" role="tablist">
          {navItems.map((item, index) => {
            const Icon = item.icon;
            const isActive = activeView === item.id;
            return (
              <button
                aria-controls={`view-${item.id}`}
                aria-selected={isActive}
                className={`nav-item ${isActive ? "nav-item--active" : ""}`}
                key={item.id}
                onClick={() => onViewChange(item.id)}
                role="tab"
                type="button"
              >
                <span className="nav-item__count">0{index + 1}</span>
                <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
                <span className="nav-item__copy">
                  <strong>{item.label}</strong>
                  <small>{item.descriptor}</small>
                </span>
                <ChevronRight className="nav-item__chevron" size={15} aria-hidden="true" />
              </button>
            );
          })}
        </nav>

        <div className="sidebar-spacer" />
        <div className="source-state">
          <div className="source-state__topline">
            <span className="live-dot" aria-hidden="true" />
            <strong>Snapshot carregado</strong>
          </div>
          <p>{getPeriodLabel(metadata.sourcePeriod)}</p>
          <div className="source-state__local">
            <ShieldCheck size={14} aria-hidden="true" />
            Arquivo local auditável
          </div>
        </div>
      </aside>

      <main className="main-stage" id="dashboard-content">
        <header className="topbar">
          <div className="topbar__copy">
            <p className="eyebrow">{current.eyebrow}</p>
            <h1>{current.title}</h1>
            <p>{current.description}</p>
          </div>
          <div className="topbar__meta">
            <div className="meta-chip">
              <CalendarRange size={16} aria-hidden="true" />
              <span>
                <small>Período-fonte</small>
                <strong>{getPeriodLabel(metadata.sourcePeriod)}</strong>
              </span>
            </div>
            <div className="meta-chip meta-chip--quiet">
              <span>
                <small>Gerado em</small>
                <strong>{formatDate(metadata.generatedAt, true)}</strong>
              </span>
            </div>
          </div>
        </header>

        <div
          className="view-container"
          id={`view-${activeView}`}
          role="tabpanel"
          tabIndex={-1}
        >
          {children}
        </div>
        <footer className="dashboard-footer">
          <span>LH Nautical · intelligence deck</span>
          <span>Leitura agregada · sem dados pessoais</span>
        </footer>
      </main>
    </div>
  );
}
