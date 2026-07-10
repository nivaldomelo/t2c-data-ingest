export type ConnectionType = "postgres" | "mysql" | "s3";
export type TestStatus = "success" | "failed" | "not_tested";
export type S3AuthMode = "access_key" | "iam_role" | "instance_profile" | "environment";

export interface Connection {
  id: number;
  name: string;
  description: string | null;
  connection_type: ConnectionType;
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
}

export const DEFAULT_PORTS: Record<ConnectionType, number | null> = {
  postgres: 5432,
  mysql: 3306,
  s3: null,
};

export const TYPE_LABEL: Record<ConnectionType, string> = {
  postgres: "PostgreSQL",
  mysql: "MySQL",
  s3: "AWS S3 / Data Lake",
};

export const S3_AUTH_MODE_LABEL: Record<S3AuthMode, string> = {
  access_key: "Access Key (chave de acesso)",
  iam_role: "IAM Role (assumir role)",
  instance_profile: "Instance Profile / Pod (EKS)",
  environment: "Variáveis de ambiente",
};
