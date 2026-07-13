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

export interface DlLatestPartition {
  path: string;
  files_count: number | null;
  total_size_bytes: number | null;
  last_modified_at: string | null;
}

export interface DlLastIngestion {
  job_name: string | null;
  pipeline_name: string | null;
  status: string | null;
  records_written: number | null;
  executed_at: string | null;
}

export interface DlQuality {
  last_status: string | null;
  score: number | null;
  validated_at: string | null;
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
  last_catalog_scan_at: string | null;
  status: string;
  connection_id: number | null;
  connection_name: string | null;
  bucket_name: string | null;
  base_prefix: string | null;
  latest_partition: DlLatestPartition | null;
  last_ingestion: DlLastIngestion | null;
  quality: DlQuality | null;
}

export const TABLE_STATUS: Record<string, { label: string; cls: string }> = {
  active: { label: "Ativa", cls: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
  inactive: { label: "Inativa", cls: "bg-gray-100 text-gray-600 ring-gray-200" },
  error: { label: "Erro", cls: "bg-red-50 text-red-700 ring-red-200" },
  scanning: { label: "Atualizando", cls: "bg-amber-50 text-amber-700 ring-amber-200" },
  not_scanned: { label: "Não escaneada", cls: "bg-gray-100 text-gray-600 ring-gray-200" },
};

export function statusBadge(status: string | null | undefined) {
  return TABLE_STATUS[status ?? "active"] ?? TABLE_STATUS.active;
}

/** Estado geral do catálogo, a partir de last_scan_status + last_scan_at. */
export function catalogHealth(
  scanStatus: string | null | undefined,
  scanAt: string | null | undefined,
): { label: string; cls: string } {
  if (scanStatus === "failed") return { label: "Erro na última varredura", cls: "bg-red-50 text-red-700 ring-red-200" };
  if (scanStatus === "running" || scanStatus === "queued")
    return { label: "Atualizando catálogo", cls: "bg-amber-50 text-amber-700 ring-amber-200" };
  if (!scanAt) return { label: "Nunca escaneado", cls: "bg-gray-100 text-gray-600 ring-gray-200" };
  const ageMs = Date.now() - new Date(scanAt).getTime();
  if (ageMs > 7 * 24 * 3600 * 1000)
    return { label: "Catálogo desatualizado", cls: "bg-amber-50 text-amber-700 ring-amber-200" };
  return { label: "Catálogo atualizado", cls: "bg-emerald-50 text-emerald-700 ring-emerald-200" };
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
