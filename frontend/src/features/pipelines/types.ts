export interface Pipeline {
  id: number;
  name: string;
  description: string | null;
  group_name: string | null;
  is_active: boolean;
  default_parameters: Record<string, unknown> | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  steps_count: number;
}

export interface PipelineDetail extends Pipeline {
  dependencies_count: number;
  last_execution_id: number | null;
  last_status: string | null;
  last_finished_at: string | null;
  avg_duration_seconds: number | null;
  executions_total: number;
}

export interface GraphNode {
  step_key: string;
  job_id: number;
  label: string | null;
  position: { x: number; y: number } | null;
  run_if: string;
  retry_count: number;
  timeout_seconds: number | null;
  parameters: Record<string, unknown> | null;
  active: boolean;
}

export interface GraphEdge {
  source_step_key: string;
  target_step_key: string;
  dependency_type: string;
}

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

export interface PipelineExecution {
  id: number;
  pipeline_id: number;
  status: string;
  trigger_type: string;
  triggered_by: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  message: string | null;
  created_at: string;
}

export interface StepExecution {
  id: number;
  step_id: number;
  job_id: number;
  execution_id: number | null;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  message: string | null;
}

export interface JobLite {
  id: number;
  name: string;
  type: string;
  engine: string | null;
  is_active: boolean;
}

export function fmtDate(t: string | null | undefined): string {
  return t ? new Date(t).toLocaleString("pt-BR") : "—";
}

export function fmtDuration(s: number | null | undefined): string {
  if (s == null) return "—";
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}
