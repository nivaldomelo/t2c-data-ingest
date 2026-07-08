export interface Library {
  id: number;
  cluster_id: number | null;
  package_name: string;
  package_version: string | null;
  package_spec: string;
  source: string;
  install_scope: string;
  status: string;
  active: boolean;
  note: string | null;
  installed_at: string | null;
  installed_by: string | null;
  removed_at: string | null;
  removed_by: string | null;
  last_action_at: string | null;
  last_action_status: string | null;
  last_action_message: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface LibraryAction {
  id: number;
  library_id: number | null;
  cluster_id: number | null;
  action: string;
  package_spec: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  command_safe: string | null;
  error_message: string | null;
  requested_by: string | null;
  created_at: string;
}

export interface LibraryDetail extends Library {
  actions: LibraryAction[];
}

export interface LibrarySummary {
  installed: number;
  success: number;
  failed: number;
  running: number;
  last_installed_at: string | null;
}

export interface ValidateResponse {
  valid: boolean;
  package_name: string | null;
  version: string | null;
  normalized_spec: string | null;
  error: string | null;
}

export const LIBRARY_STATUS_LABEL: Record<string, string> = {
  pending: "Pendente",
  queued: "Na fila",
  installing: "Instalando",
  installed: "Instalado",
  failed: "Falhou",
  removed: "Removido",
};

export const ACTION_LABEL: Record<string, string> = {
  install: "Instalação",
  reinstall: "Reinstalação",
  uninstall: "Remoção",
  check: "Verificação",
};
