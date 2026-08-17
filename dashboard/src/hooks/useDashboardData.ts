import { useCallback, useEffect, useState } from "react";
import type { DashboardData } from "../types/dashboard";

interface DashboardState {
  data: DashboardData | null;
  error: string | null;
  isLoading: boolean;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseDashboard(payload: unknown): DashboardData {
  if (!isRecord(payload)) {
    throw new Error("O arquivo não contém um objeto JSON válido.");
  }

  const requiredSections = [
    "metadata",
    "executive",
    "sales",
    "customers",
    "operations",
    "quality",
  ] as const;

  const missing = requiredSections.filter((section) => !isRecord(payload[section]));
  if (missing.length > 0) {
    throw new Error(`Seções ausentes ou inválidas: ${missing.join(", ")}.`);
  }

  return payload as unknown as DashboardData;
}

export function useDashboardData() {
  const [requestId, setRequestId] = useState(0);
  const [state, setState] = useState<DashboardState>({
    data: null,
    error: null,
    isLoading: true,
  });

  const retry = useCallback(() => {
    setRequestId((current) => current + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    async function loadDashboard() {
      setState((current) => ({ ...current, error: null, isLoading: true }));

      try {
        const dataUrl = `${import.meta.env.BASE_URL}data/dashboard.json`;
        const response = await fetch(dataUrl, {
          cache: "no-store",
          headers: { Accept: "application/json" },
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`A fonte respondeu com status ${response.status}.`);
        }

        const payload: unknown = await response.json();
        const data = parseDashboard(payload);
        setState({ data, error: null, isLoading: false });
      } catch (error) {
        if (controller.signal.aborted) return;
        const message =
          error instanceof Error ? error.message : "Falha desconhecida ao ler os dados.";
        setState({ data: null, error: message, isLoading: false });
      }
    }

    void loadDashboard();
    return () => controller.abort();
  }, [requestId]);

  return { ...state, retry };
}
