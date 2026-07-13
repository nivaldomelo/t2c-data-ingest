export type ConnectionType = string;
export type ConnectionCategory = "database" | "storage" | "api";
export type TestStatus = "success" | "failed" | "not_tested";
export type S3AuthMode = "access_key" | "iam_role" | "instance_profile" | "environment";

/** Metadados de um campo do conector (registry backend /connections/types). */
export interface ConnectorField {
  name: string;
  label: string;
  kind: "text" | "number" | "password" | "select" | "checkbox" | "textarea";
  store: string; // col:X | password | aws:X | secret | extra
  secret: boolean;
  required: boolean;
  placeholder: string;
  help: string;
  section: string;
  options: string[];
  default: unknown;
  show_if: { field: string; in: string[] } | null;
}

export interface ConnectorMeta {
  type: string;
  category: ConnectionCategory;
  label: string;
  default_port: number | null;
  description: string;
  test_hint: string;
  fields: ConnectorField[];
}

export const CATEGORY_LABEL: Record<ConnectionCategory, string> = {
  database: "Bancos de dados",
  storage: "Data Lake / Storage",
  api: "APIs / SaaS",
};

export interface Connection {
  id: number;
  name: string;
  description: string | null;
  connection_type: ConnectionType;
  connection_category: ConnectionCategory | null;
  host: string | null;
  port: number | null;
  database_name: string | null;
  username: string | null;
  schema_name: string | null;
  extra_params: Record<string, unknown> | null;
  ssl_enabled: boolean;
  active: boolean;
  can_read: boolean;
  can_write: boolean;
  has_password: boolean;
  has_aws_access_key: boolean;
  has_aws_secret_key: boolean;
  has_aws_session_token: boolean;
  secrets_present: string[];
  last_test_status: TestStatus;
  last_test_message: string | null;
  last_tested_at: string | null;
  created_by: string | null;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConnectionSummary {
  total: number;
  postgres: number;
  mysql: number;
  s3: number;
  database: number;
  storage: number;
  api: number;
  test_success: number;
  test_failed: number;
}

export interface ConnectionTestResult {
  status: "success" | "failed";
  message: string;
  tested_at: string | null;
}

/** Shape of S3-specific config stored inside extra_params. */
export interface S3ExtraParams {
  aws_region?: string;
  bucket_name?: string;
  base_prefix?: string;
  default_layer?: string;
  auth_mode?: S3AuthMode;
  endpoint_url?: string;
  role_arn?: string;
  external_id?: string;
  ssl_enabled?: boolean;
  // Catálogo do Data Lake (explorer)
  catalog_enabled?: boolean;
  catalog_mode?: string;
  default_file_format?: string;
  partition_pattern?: string;
  layers?: { name: string; bucket: string; base_prefix?: string }[];
}

export interface S3ObjectItem {
  key: string;
  size: number | null;
  last_modified: string | null;
  storage_class: string | null;
}

export interface S3ObjectsOut {
  bucket: string | null;
  prefix: string | null;
  items: S3ObjectItem[];
}

export interface S3TestDetails {
  bucket?: string | null;
  region?: string | null;
  base_prefix?: string | null;
  auth_mode?: string | null;
  can_list?: boolean;
  can_read?: boolean;
  can_write?: boolean;
}

export interface S3TestResult {
  success: boolean;
  message: string;
  details: S3TestDetails;
}

export interface ConnectionFormValues {
  name: string;
  description: string;
  connection_type: ConnectionType;
  // DB fields
  host: string;
  port: number | "";
  database_name: string;
  username: string;
  password: string;
  schema_name: string;
  // Common
  ssl_enabled: boolean;
  active: boolean;
  can_read: boolean;
  can_write: boolean;
  extra_params: string; // JSON textarea (DB connections)
  // S3 fields
  aws_region: string;
  bucket_name: string;
  base_prefix: string;
  default_layer: string;
  auth_mode: S3AuthMode;
  endpoint_url: string;
  role_arn: string;
  external_id: string;
  aws_access_key_id: string;
  aws_secret_access_key: string;
  aws_session_token: string;
  // Catálogo Data Lake
  catalog_enabled: boolean;
  catalog_mode: string;
}

export const DEFAULT_PORTS: Record<string, number | null> = {
  postgres: 5432,
  mysql: 3306,
  s3: null,
};

const TYPE_LABELS: Record<string, string> = {
  postgres: "PostgreSQL",
  mysql: "MySQL",
  mariadb: "MariaDB",
  sqlserver: "SQL Server",
  oracle: "Oracle",
  mongodb: "MongoDB",
  s3: "AWS S3 / Data Lake",
  rest_api: "REST API Genérica",
  jira: "Jira",
  mixpanel: "Mixpanel",
  blip: "Blip",
};

// Compat: mapa direto (fallback) + resolver com o registry quando disponível.
export const TYPE_LABEL = TYPE_LABELS;

export function typeLabel(type: string, connectors?: { type: string; label: string }[]): string {
  const fromRegistry = connectors?.find((c) => c.type === type)?.label;
  return fromRegistry ?? TYPE_LABELS[type] ?? type;
}

export function categoryOf(type: string, connectors?: { type: string; category: string }[]): ConnectionCategory {
  const c = connectors?.find((x) => x.type === type)?.category as ConnectionCategory | undefined;
  if (c) return c;
  if (["s3"].includes(type)) return "storage";
  if (["rest_api", "jira", "mixpanel", "blip"].includes(type)) return "api";
  return "database";
}

export const S3_AUTH_MODE_LABEL: Record<S3AuthMode, string> = {
  access_key: "Access Key (chave de acesso)",
  iam_role: "IAM Role (assumir role)",
  instance_profile: "Instance Profile / Pod (EKS)",
  environment: "Variáveis de ambiente",
};
