import { isProfileBatchExperiment, isProfileBatchRun, isProfileExperiment, isProfileRun } from "../api/types";
import type {
  AnyRunSummary,
  BacktestReport,
  ExperimentSummary,
  LegacyExperimentSummary,
  ProfileAudazExperimentSummary,
  ProfileBatchExperimentSummary,
  ProfileCyclingExperimentSummary,
  ProfileRecoveryExperimentSummary,
  ProfileV1ExperimentSummary,
} from "../api/types";

interface ResultViewModelBase {
  title: string;
  status: string;
  source: string;
  sections: readonly string[];
  actions: readonly { label: string; href: string }[];
}

export type SimulationResultViewModel = ResultViewModelBase & (
  | { family: "classic-individual"; payload: LegacyExperimentSummary }
  | { family: "historical-aggregate"; payload: BacktestReport }
  | { family: "profile-v1"; payload: ProfileV1ExperimentSummary }
  | { family: "profile-v2"; payload: ProfileCyclingExperimentSummary }
  | { family: "profile-v3"; payload: ProfileAudazExperimentSummary }
  | { family: "profile-v4"; payload: ProfileRecoveryExperimentSummary }
  | { family: "profile-batch-v5"; payload: ProfileBatchExperimentSummary }
);

const detailSections = ["Resultado", "Apuestas", "Parámetros y datos"] as const;
export const FROZEN_HISTORY_SOURCE_LABEL = "Historial congelado de Quiniela 80";

function isProfileV1(data: ExperimentSummary): data is ProfileV1ExperimentSummary {
  return isProfileExperiment(data) && data.request.schema_version === 1;
}
function isProfileV2(data: ExperimentSummary): data is ProfileCyclingExperimentSummary {
  return isProfileExperiment(data) && data.request.schema_version === 2;
}
function isProfileV3(data: ExperimentSummary): data is ProfileAudazExperimentSummary {
  return isProfileExperiment(data) && data.request.schema_version === 3;
}
function isProfileV4(data: ExperimentSummary): data is ProfileRecoveryExperimentSummary {
  return isProfileExperiment(data) && data.request.schema_version === 4;
}

export function experimentResultViewModel(data: ExperimentSummary, run: AnyRunSummary, id = data.id): SimulationResultViewModel | null {
  const statusLabels: Record<string, string> = { pending: "Pendiente", held: "Pendiente", running: "En curso", completed: "Completada", failed: "Con error", cancelled: "Cancelada", interrupted: "Interrumpida", not_run: "No iniciada" };
  const base: ResultViewModelBase = {
    title: `Ejecución ${run.ordinal + 1}`,
    status: statusLabels[run.status] ?? "Estado no disponible",
    source: "",
    sections: detailSections,
    actions: [{ label: "Comparar simulaciones", href: `/simulaciones/${encodeURIComponent(id)}/comparacion` }],
  };
  if (!isProfileExperiment(data)) {
    if (isProfileRun(run)) return null;
    return { ...base, family: "classic-individual", source: FROZEN_HISTORY_SOURCE_LABEL, payload: data };
  }
  if (isProfileBatchExperiment(data)) {
    if (!isProfileBatchRun(run)) return null;
    return { ...base, family: "profile-batch-v5", source: FROZEN_HISTORY_SOURCE_LABEL, payload: data };
  }
  const version = data.request.schema_version;
  if (!isProfileRun(run) || isProfileBatchRun(run) || (run.result && run.result.schema_version !== version)) return null;
  const source = `Dataset: ${data.request.dataset_sha256}`;
  switch (version) {
    case 1: return isProfileV1(data) ? { ...base, family: "profile-v1", source, payload: data } : null;
    case 2: return isProfileV2(data) ? { ...base, family: "profile-v2", source, payload: data } : null;
    case 3: return isProfileV3(data) ? { ...base, family: "profile-v3", source, payload: data } : null;
    case 4: return isProfileV4(data) ? { ...base, family: "profile-v4", source, payload: data } : null;
    default: return null;
  }
}

export function historicalResultViewModel(report: BacktestReport): SimulationResultViewModel {
  return {
    family: "historical-aggregate",
    title: "Informe histórico",
    status: "Histórico",
    source: report.created_at ? `Informe guardado · ${report.created_at}` : "Informe histórico guardado",
    sections: ["Resultados del escenario", "Totales de la ventana histórica", "Configuración usada"],
    actions: [],
    payload: report,
  };
}
