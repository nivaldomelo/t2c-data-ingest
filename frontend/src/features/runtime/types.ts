export interface RuntimeLibrary {
  id: number;
  package_name: string;
  package_version: string | null;
  package_spec: string;
  source: string;
  active: boolean;
  note: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface RuntimeBuild {
  id: number;
  build_version: string;
  image_name: string;
  image_tag: string;
  image_full_name: string;
  status: string;
  is_active: boolean;
  jobs_snapshot_path: string | null;
  dockerfile_path: string | null;
  context_path: string | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  created_by: string | null;
  created_at: string;
}

export interface RuntimeBuildDetail extends RuntimeBuild {
  requirements_snapshot: string | null;
  build_logs: string | null;
}

export interface RuntimeValidation {
  id: number;
  runtime_build_id: number | null;
  validation_type: string;
  status: string;
  worker_count_expected: number | null;
  worker_count_detected: number | null;
  libraries_checked: string[] | null;
  workers_result: Record<string, unknown> | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface RuntimeValidationDetail extends RuntimeValidation {
  logs: string | null;
}

export interface RuntimeSummary {
  active_libraries: number;
  active_build: string | null;
  workers_expected: number;
  last_validation_status: string | null;
  last_validation_at: string | null;
}

export const BUILD_STATUS_LABEL: Record<string, string> = {
  queued: "Na fila", building: "Building", success: "Concluído",
  failed: "Falhou", active: "Ativa", deprecated: "Depreciada",
};

export const BUILD_STATUS_TONE: Record<string, string> = {
  queued: "border-sky-200 bg-sky-50 text-sky-700",
  building: "border-brand-200 bg-brand-50 text-brand-700",
  success: "border-emerald-200 bg-emerald-50 text-emerald-700",
  failed: "border-red-200 bg-red-50 text-red-700",
  active: "border-emerald-300 bg-emerald-100 text-emerald-800",
  deprecated: "border-gray-200 bg-gray-100 text-gray-500",
};
