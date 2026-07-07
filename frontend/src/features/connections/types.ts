export type ConnectionType = "postgres" | "mysql";
export type TestStatus = "success" | "failed" | "not_tested";

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
  has_password: boolean;
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
  test_success: number;
  test_failed: number;
}

export interface ConnectionTestResult {
  status: "success" | "failed";
  message: string;
  tested_at: string | null;
}

export interface ConnectionFormValues {
  name: string;
  description: string;
  connection_type: ConnectionType;
  host: string;
  port: number | "";
  database_name: string;
  username: string;
  password: string;
  schema_name: string;
  ssl_enabled: boolean;
  active: boolean;
  extra_params: string; // JSON textarea
}

export const DEFAULT_PORTS: Record<ConnectionType, number> = {
  postgres: 5432,
  mysql: 3306,
};

export const TYPE_LABEL: Record<ConnectionType, string> = {
  postgres: "PostgreSQL",
  mysql: "MySQL",
};
