import { Download, FileText, HelpCircle } from "lucide-react";
import type { DashboardData, DashboardView } from "../types/dashboard";
import { downloadViewCsv } from "../lib/exportCsv";

const questions: Record<DashboardView, Array<{ label: string; target: string }>> = {
  command: [
    { label: "Como o valor evoluiu?", target: "command-trend" },
    { label: "Qual canal mais pesa?", target: "command-channels" },
    { label: "O que exige atenção?", target: "command-insights" },
  ],
  marina: [
    { label: "Quem priorizar?", target: "marina-priority" },
    { label: "O que oferecer?", target: "marina-offers" },
    { label: "Onde crescer?", target: "marina-growth" },
  ],
  almir: [
    { label: "Qual o pior dia?", target: "almir-worst-day" },
    { label: "Quanto a previsão errou?", target: "almir-forecast" },
    { label: "Que decisão é insegura?", target: "almir-caution" },
  ],
  gabriel: [
    { label: "Quais são as fontes?", target: "gabriel-sources" },
    { label: "Quais regras foram usadas?", target: "gabriel-rules" },
    { label: "Quais checks rodaram?", target: "gabriel-checks" },
  ],
};

export function ViewExplorer({
  data,
  view,
}: {
  data: DashboardData;
  view: DashboardView;
}) {
  const viewNames: Record<DashboardView, string> = {
    command: "Ponte de Comando",
    marina: "Marina",
    almir: "Sr. Almir",
    gabriel: "Gabriel",
  };

  function scrollTo(target: string) {
    document.getElementById(target)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function printView() {
    const originalTitle = document.title;
    const date = data.metadata.generatedAt?.slice(0, 10) ?? "snapshot";
    document.title = `LH Nautical — ${viewNames[view]} — ${date}`;
    window.print();
    document.title = originalTitle;
  }

  return (
    <div className="view-explorer" aria-label="Perguntas que esta visão responde">
      <div className="view-explorer__questions">
        <span className="view-explorer__label">
          <HelpCircle size={15} aria-hidden="true" />
          Perguntas que esta visão responde
        </span>
        <div className="question-chips">
          {questions[view].map((question) => (
            <button key={question.target} onClick={() => scrollTo(question.target)} type="button">
              {question.label}
            </button>
          ))}
        </div>
      </div>
      <div className="view-explorer__actions">
        <button className="report-button" onClick={printView} type="button">
          <FileText size={15} aria-hidden="true" />
          Gerar mini-relatório
        </button>
        <button
          className="download-button"
          onClick={() => downloadViewCsv(data, view)}
          type="button"
        >
          <Download size={15} aria-hidden="true" />
          Baixar recorte CSV
        </button>
      </div>
    </div>
  );
}
