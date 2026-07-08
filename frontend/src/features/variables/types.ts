export interface Variable {
  id: number;
  name: string;
  description: string | null;
  value: string | null;
  masked_value: string | null;
  has_value: boolean;
  variable_type: string;
  scope: string;
  environment: string | null;
  is_secret: boolean;
  active: boolean;
  created_by: number | null;
  updated_by: number | null;
  created_at: string;
  updated_at: string | null;
}

export interface VariableDetail extends Variable {
  usage: { python: string; spark: string };
}

export interface VariableSummary {
  total: number;
  active: number;
  secret: number;
  global_scope: number;
  with_environment: number;
}

export const VARIABLE_TYPES = ["string", "integer", "decimal", "boolean", "date", "datetime", "json", "secret"];
export const VARIABLE_SCOPES = ["global", "job", "pipeline", "environment"];
export const ENVIRONMENTS = ["local", "dev", "hml", "prd"];

export function normalizeName(raw: string): string {
  return (raw || "")
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
}

export function fmtDate(t: string | null | undefined): string {
  return t ? new Date(t).toLocaleString("pt-BR") : "—";
}
