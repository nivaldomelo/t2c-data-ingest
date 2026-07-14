export type DestinationType = "postgres" | "s3";

export interface Destination {
  id: number;
  name: string;
  description: string | null;
  destination_type: DestinationType;
  connection_id: number;
  connection_name: string | null;
  connection_type: string | null;
  target_display: string | null;
  target_schema: string | null;
  target_table: string | null;
  target_database: string | null;
  target_bucket: string | null;
  target_prefix: string | null;
  target_path: string | null;
  target_layer: string | null;
  file_format: string | null;
  write_mode: string;
  compression: string | null;
  partition_columns: string[] | null;
  primary_key_columns: string[] | null;
  staging_schema: string | null;
  staging_table: string | null;
  upsert_strategy: string | null;
  truncate_before_load: boolean;
  options: Record<string, unknown> | null;
  active: boolean;
  last_test_status: "success" | "failed" | "not_tested";
  last_test_message: string | null;
  last_tested_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface DestinationSummary {
  total: number;
  postgres: number;
  s3: number;
  active: number;
  test_failed: number;
}

export interface DestinationTestCheck {
  name: string;
  ok: boolean;
  detail?: string;
}
export interface DestinationTestResult {
  status: "success" | "failed";
  message: string;
  checks: DestinationTestCheck[];
  tested_at: string | null;
}

export const TYPE_LABEL: Record<DestinationType, string> = {
  postgres: "PostgreSQL",
  s3: "AWS S3 / Data Lake",
};

export const PG_WRITE_MODES = ["append", "overwrite", "truncate_insert", "upsert", "merge"];
export const S3_WRITE_MODES = ["append", "overwrite", "overwrite_partitions", "error_if_exists", "ignore"];
export const FILE_FORMATS = ["parquet", "csv", "json", "orc"];
export const COMPRESSIONS = ["snappy", "gzip", "none"];
export const UPSERT_STRATEGIES = ["on_conflict", "merge"];

export interface DestinationSubmit {
  name: string;
  description: string | null;
  destination_type: DestinationType;
  connection_id: number;
  write_mode: string;
  active: boolean;
  target_schema?: string | null;
  target_table?: string | null;
  primary_key_columns?: string[] | null;
  staging_schema?: string | null;
  staging_table?: string | null;
  upsert_strategy?: string | null;
  truncate_before_load?: boolean;
  target_bucket?: string | null;
  target_layer?: string | null;
  target_prefix?: string | null;
  file_format?: string | null;
  compression?: string | null;
  partition_columns?: string[] | null;
}
