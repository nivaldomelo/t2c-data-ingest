export interface Cluster {
  id: number;
  name: string;
  description: string | null;
  type: string;
  spark_master_url: string | null;
  status: string;
  worker_count: number | null;
  total_cores: number | null;
  total_memory: string | null;
  expected_workers: number | null;
  last_checked_at: string | null;
  last_validation_status: string | null;
  runtime_image: string | null;
  spark_version: string | null;
  python_version: string | null;
  java_version: string | null;
  scala_version: string | null;
  environment: string | null;
  environment_label: string | null;
  live: boolean;
  is_active: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ClustersSummary {
  total_clusters: number;
  active_clusters: number;
  workers_total: number;
  cores_total: number;
  memory_total: string | null;
  last_validation_status: string | null;
}

export interface ClusterWorker {
  name: string;
  status: string;
  host: string | null;
  cores: number | null;
  memory: string | null;
  last_heartbeat_at: string | null;
}

export interface ClusterWorkers {
  cluster_id: number;
  workers_expected: number;
  workers_detected: number;
  workers: ClusterWorker[];
}

export interface ClusterValidation {
  id: number;
  validation_type: string;
  status: string;
  worker_count_expected: number | null;
  worker_count_detected: number | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export const CLUSTER_STATUS: Record<string, { label: string; tone: string; dot: string }> = {
  active: { label: "Ativo", tone: "border-emerald-200 bg-emerald-50 text-emerald-700", dot: "bg-emerald-500" },
  inactive: { label: "Inativo", tone: "border-gray-200 bg-gray-100 text-gray-500", dot: "bg-gray-400" },
  error: { label: "Erro", tone: "border-red-200 bg-red-50 text-red-700", dot: "bg-red-500" },
  unreachable: { label: "Inacessível", tone: "border-red-200 bg-red-50 text-red-700", dot: "bg-red-500" },
  validating: { label: "Validando", tone: "border-brand-200 bg-brand-50 text-brand-700", dot: "bg-brand-500" },
  not_validated: { label: "Não validado", tone: "border-gray-200 bg-gray-100 text-gray-500", dot: "bg-gray-400" },
};

export const WORKER_STATUS: Record<string, { label: string; tone: string; dot: string }> = {
  active: { label: "Ativo", tone: "text-emerald-700", dot: "bg-emerald-500" },
  inactive: { label: "Inativo", tone: "text-gray-500", dot: "bg-gray-400" },
  error: { label: "Erro", tone: "text-red-600", dot: "bg-red-500" },
  no_heartbeat: { label: "Sem heartbeat", tone: "text-amber-600", dot: "bg-amber-500" },
};

export function fmtDate(t: string | null | undefined): string {
  return t ? new Date(t).toLocaleString("pt-BR") : "—";
}
