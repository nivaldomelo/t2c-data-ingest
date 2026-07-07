export type ScheduleType = "cron" | "hourly" | "daily" | "weekly" | "monthly" | "manual";

export interface Schedule {
  id: number;
  job_id: number;
  job_name: string | null;
  name: string;
  description: string | null;
  schedule_type: ScheduleType;
  cron_expression: string | null;
  timezone: string;
  start_at: string | null;
  end_at: string | null;
  parameters: Record<string, unknown> | null;
  active: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  last_status: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScheduleRun {
  id: number;
  schedule_id: number;
  job_id: number;
  execution_id: number | null;
  scheduled_for: string;
  triggered_at: string | null;
  status: string;
  message: string | null;
  created_at: string;
}

export interface ScheduleSummary {
  total: number;
  active: number;
  inactive: number;
  next_runs_today: number;
  last_error: number;
}

export interface CronValidateResponse {
  valid: boolean;
  error?: string | null;
  next_runs: string[];
}

export const CRON_TEMPLATES: { label: string; cron: string; type: ScheduleType }[] = [
  { label: "A cada 15 minutos", cron: "*/15 * * * *", type: "cron" },
  { label: "A cada 30 minutos", cron: "*/30 * * * *", type: "cron" },
  { label: "De hora em hora", cron: "0 * * * *", type: "hourly" },
  { label: "A cada 2 horas", cron: "0 */2 * * *", type: "cron" },
  { label: "Diariamente às 08:00", cron: "0 8 * * *", type: "daily" },
  { label: "Diariamente às 00:00", cron: "0 0 * * *", type: "daily" },
  { label: "Segunda a sexta às 08:00", cron: "0 8 * * 1-5", type: "weekly" },
  { label: "Seg a sex, de hora em hora, 08h–18h", cron: "0 8-18 * * 1-5", type: "cron" },
  { label: "Cron personalizado", cron: "", type: "cron" },
];

export const TIMEZONES = [
  "America/Sao_Paulo",
  "America/Manaus",
  "America/New_York",
  "UTC",
];

export function fmtDateTime(t: string | null | undefined): string {
  return t ? new Date(t).toLocaleString("pt-BR") : "—";
}
