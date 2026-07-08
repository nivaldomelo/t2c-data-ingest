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
  // soft delete
  deleted_at: string | null;
  deleted_by: string | null;
  delete_reason: string | null;
  archived_code_path: string | null;
  // enriched
  source_connection_name: string | null;
  target_connection_name: string | null;
  source_connection: JobConnectionInfo | null;
  target_connection: JobConnectionInfo | null;
  connection: JobConnectionInfo | null;
  executions_total: number;
  last_execution_id: number | null;
  last_status: string | null;
  last_finished_at: string | null;
  avg_duration_seconds: number | null;
  last_execution_started_at: string | null;
  last_execution_duration_seconds: number | null;
  last_execution_engine: string | null;
  last_execution_trigger: string | null;
  success_rate: number | null;
  recent_failures: number;
  running_executions: number;
  active_schedules: number;
}

export interface JobConnectionInfo {
  id: number | null;
  name: string | null;
  type: string | null;
  host: string | null;
  port: number | null;
  database: string | null;
  last_test_status: string | null;
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

// Friendly duration: 0,5s · 10s · 10,2s · 1min 20s · 1h 03min
export function fmtDuration(s: number | null | undefined): string {
  if (s == null) return "—";
  if (s < 60) {
    const r = Math.round(s * 10) / 10;
    return `${Number.isInteger(r) ? r : r.toString().replace(".", ",")}s`;
  }
  if (s < 3600) {
    const m = Math.floor(s / 60);
    const sec = Math.round(s % 60);
    return sec ? `${m}min ${String(sec).padStart(2, "0")}s` : `${m}min`;
  }
  const h = Math.floor(s / 3600);
  const m = Math.round((s % 3600) / 60);
  return `${h}h ${String(m).padStart(2, "0")}min`;
}

export function fmtDate(t: string | null | undefined): string {
  return t ? new Date(t).toLocaleString("pt-BR") : "—";
}

// Parse ["--flag","value",...] into a raw string, backslash-wrapped lines and key/value pairs.
export function parseJobArguments(args: unknown[] | null | undefined): {
  raw: string;
  lines: string[];
  pairs: { key: string; value: string }[];
} {
  const tokens = (args ?? []).map(String);
  const raw = tokens.join(" ");
  const pairs: { key: string; value: string }[] = [];
  const lines: string[] = [];
  for (let i = 0; i < tokens.length; i++) {
    const t = tokens[i];
    if (t.startsWith("--")) {
      const key = t.replace(/^--/, "");
      const next = tokens[i + 1];
      if (next && !next.startsWith("--")) {
        pairs.push({ key, value: next });
        lines.push(`${t} ${next}`);
        i++;
      } else {
        pairs.push({ key, value: "true" });
        lines.push(t);
      }
    } else {
      lines.push(t);
    }
  }
  return { raw, lines, pairs };
}
