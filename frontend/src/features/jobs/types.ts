export interface JobDetail {
  id: number;
  name: string;
  description: string | null;
  type: string;
  engine: string | null;
  script_path: string | null;
  main_class: string | null;
  sql_statement: string | null;
  arguments: unknown[] | null;
  env_vars: Record<string, unknown> | null;
  cluster_id: number | null;
  connection_id: number | null;
  source_connection_id: number | null;
  target_connection_id: number | null;
  default_parameters: Record<string, unknown> | null;
  retry_count: number;
  timeout_seconds: number | null;
  is_active: boolean;
  created_by: string | null;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
  tags: { id: number; name: string; slug: string; color: string | null }[];
  // enriched
  source_connection_name: string | null;
  target_connection_name: string | null;
  executions_total: number;
  last_execution_id: number | null;
  last_status: string | null;
  last_finished_at: string | null;
  avg_duration_seconds: number | null;
}

export interface JobExecution {
  id: number;
  status: string;
  engine: string | null;
  triggered_by: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  final_message: string | null;
}

export interface JobCode {
  job_id: number;
  job_name: string;
  script_path: string | null;
  language: string;
  content: string;
  read_only: boolean;
}

export const JOB_TYPE_LABEL: Record<string, string> = {
  python: "Python",
  spark_python: "Spark · Python",
  spark_sql: "Spark · SQL",
  spark_submit: "Spark · Submit",
};

export function fmtDuration(s: number | null | undefined): string {
  if (s == null) return "—";
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

export function fmtDate(t: string | null | undefined): string {
  return t ? new Date(t).toLocaleString("pt-BR") : "—";
}
