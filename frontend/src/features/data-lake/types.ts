export interface DlConnection {
  id: number;
  name: string;
  catalog_enabled: boolean;
  catalog_mode: string;
  can_read: boolean;
  active: boolean;
}

export interface DlTreeTable {
  id: number;
  name: string;
  files_count: number | null;
  total_size_bytes: number | null;
  last_modified_at: string | null;
  status: string;
}

export interface DlTreeSchema {
  id: number;
  name: string;
  layer_name: string | null;
  bucket_name: string;
  tables: DlTreeTable[];
}

export interface DlTreeCatalog {
  id: number;
  name: string;
  connection_id: number;
  connection_name: string | null;
  last_scan_status: string | null;
  last_scan_at: string | null;
  schemas: DlTreeSchema[];
}

export interface DlTree {
  catalogs: DlTreeCatalog[];
}

export interface DlTable {
  id: number;
  schema_id: number;
  schema_name: string | null;
  layer_name: string | null;
  table_name: string;
  full_name: string | null;
  table_path: string;
  file_format: string;
  partition_columns: string[] | null;
  columns_count: number | null;
  files_count: number | null;
  total_size_bytes: number | null;
  estimated_rows: number | null;
  last_modified_at: string | null;
  last_schema_scan_at: string | null;
  status: string;
  connection_id: number | null;
  bucket_name: string | null;
}

export interface DlColumn {
  id: number;
  column_name: string;
  ordinal_position: number | null;
  spark_type: string | null;
  parquet_type: string | null;
  nullable: boolean | null;
  is_partition: boolean;
  comment: string | null;
}

export interface DlFile {
  id: number;
  partition_path: string | null;
  object_key: string;
  size_bytes: number | null;
  last_modified_at: string | null;
  storage_class: string | null;
}

export interface DlPartition {
  id: number;
  partition_path: string;
  partition_values: Record<string, string> | null;
  files_count: number | null;
  total_size_bytes: number | null;
  last_modified_at: string | null;
}

export interface DlScanRun {
  id: number;
  catalog_id: number;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  stats: Record<string, number> | null;
  message: string | null;
  error_message: string | null;
  created_at: string | null;
}

export interface DlQueryColumn {
  name: string;
  type: string;
}

export interface DlQueryResult {
  id: number;
  status: string; // queued | running | success | failed
  executed_sql: string;
  translated_sql: string | null;
  columns: DlQueryColumn[];
  rows: Record<string, unknown>[];
  rows_returned: number | null;
  limit_applied: number | null;
  duration_seconds: number | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface DlQueryHistoryItem {
  id: number;
  connection_id: number;
  table_id: number | null;
  executed_sql: string;
  status: string;
  rows_returned: number | null;
  duration_seconds: number | null;
  error_message: string | null;
  executed_by: string | null;
  created_at: string | null;
}

export function fmtBytes(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
}

export function fmtDate(t: string | null | undefined): string {
  return t ? new Date(t).toLocaleString("pt-BR") : "—";
}

export const QUERY_ACTIVE = (s: string) => s === "queued" || s === "running";
